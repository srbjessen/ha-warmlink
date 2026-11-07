
import asyncio
import hashlib
import logging
import aiohttp
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from ..common.endpoints import Endpoints

LOGGER = logging.getLogger(__name__)

# Transient-error retry (issue #42). cloud.linked-go.com drops the occasional
# single request -- a timeout or a connection reset -- while the surrounding
# cycles succeed, which blanks ~20 entities for a whole 120 s poll and leaves
# history gaps. These are the delays (seconds) BETWEEN attempts, so the client
# tries len(_RETRY_BACKOFFS)+1 times in all; worst-case ~11 s stays well below
# the 120 s update interval.
_RETRY_BACKOFFS = (1, 3, 7)

# Transport-level failures worth retrying. aiohttp.ClientError is the base for
# connection resets/OS errors/response-decode errors; asyncio.TimeoutError
# (incl. aiohttp.ServerTimeoutError) covers read/connect timeouts.
_TRANSIENT_EXC = (asyncio.TimeoutError, aiohttp.ClientError)


class _TransientCloudError(aiohttp.ClientError):
    """A retryable HTTP status (429 / 5xx) from the cloud.

    Subclasses ClientError so the retry loop catches it like any other
    transient transport failure -- but, because it means the server *did*
    receive the request, it is deliberately NOT a connect-phase error, so a
    non-idempotent write is never retried on it (the write may have applied).
    """

# Product IDs from the WarmLink/AquaTemp ecosystem
PRODUCT_IDS = [
    "1194901186696777728", "1239430558124097536", "1255021944487620608",
    "1280068488723034112", "1339750000640499712", "1605555198352117760",
    "1531069503612518401", "1334333994707222528", "1314389730321776640",
    "1534426457089150976", "1430840899188973568", "1151012720393330688",
    "1390463737449857024", "1442056800068329472", "1787637595964661762",
    "1904737978748719105", "1659079112307445760", "1898923361595772930",
    "1631478423544852480", "1802975574960046081", "1501438265440362496",
    "1713838037212577792", "1899374754815238145", "1544970221549498368",
    "1559733647991496705", "1506552523736190976", "1473911871244337152",
    "1552190345066967040", "1534450342119510016", "1480699335514533888"
]

class WarmlinkAuthError(Exception):
    """The cloud explicitly rejected the credentials (not a transport error)."""


class WarmlinkAPI:
    """API client for WarmLink."""

    def __init__(self, username, password, hass):
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.base_url = "https://cloud.linked-go.com:449/crmservice/api"
        self.session = async_get_clientsession(hass)
        self.token = None
        # True after a login attempt the cloud explicitly rejected (both plain
        # and MD5 password variants). Distinguishes "wrong password" — which
        # never fixes itself and should surface a reauth — from transient
        # transport failures, which should just be retried.
        self.auth_failed = False
        # The cloud only allows ONE active token per account: every new login
        # invalidates the previous token (verified empirically — old token gets
        # error_code -100). Serialise logins so concurrent coordinators sharing
        # this client don't stampede and invalidate each other's fresh tokens.
        self._login_lock = asyncio.Lock()

    async def login(self):
        """Login to the API (serialised — see _login_lock note)."""
        async with self._login_lock:
            return await self._login_inner()

    async def ensure_token(self, bad_token=None):
        """Make sure a usable token exists, re-logging in only when needed.

        Waiters queued on the lock piggyback on the winner's fresh token
        instead of logging in again themselves — every login invalidates the
        previous token (one active token per account), so N queued logins used
        to end with N-1 dead tokens and another round of -100s (token
        ping-pong). ``bad_token`` is the token the caller just saw rejected;
        holding a DIFFERENT one means somebody already re-authenticated.
        """
        async with self._login_lock:
            if self.token and self.token != bad_token:
                return True
            return await self._login_inner()

    async def _login_inner(self):
        LOGGER.debug(f"WarmLink API: Attempting login for user {self.username}")
        # Never leave a stale token around while re-authenticating: a failed
        # login used to keep the old (invalid) token, so every later request
        # retried it, got -100, failed the re-login, and looped — silently —
        # until an HA restart.
        self.token = None
        self.auth_failed = False
        payload = {"userName": self.username, "password": self.password}
        try:
            async with self.session.post(f"{self.base_url}/{Endpoints.Login}", json=payload) as r:
                data = await r.json()
            if not data.get("isReusltSuc"):
                LOGGER.debug("WarmLink API: Plain password login failed, trying MD5")
                md5 = hashlib.md5(self.password.encode()).hexdigest()
                payload["password"] = md5
                async with self.session.post(f"{self.base_url}/{Endpoints.Login}", json=payload) as r:
                    data = await r.json()
            if data.get("isReusltSuc") and data.get("objectResult"):
                self.token = data["objectResult"]["x-token"]
                LOGGER.info("WarmLink API: Login successful")
                return True
            LOGGER.error(f"WarmLink API: Login failed - {data.get('error_msg', 'Unknown error')}")
            self.auth_failed = True
            return False
        except Exception as e:
            LOGGER.error(f"WarmLink API: Login exception - {e}")
            return False

    def _raise_login_failure(self, path):
        """Turn a failed (re)login into the right exception for the caller."""
        if self.auth_failed:
            raise WarmlinkAuthError(
                f"WarmLink cloud rejected the credentials for {self.username}"
            )
        raise ConnectionError(f"Could not log in to the WarmLink cloud ({path})")

    async def post(self, path, payload, idempotent=True):
        """Make a POST request to the API, retrying transient cloud failures.

        The cloud drops the occasional single request (timeout / connection
        reset / 429 / 5xx) while the next cycle succeeds, so those are retried
        with a short bounded backoff (issue #42). Non-transient failures are
        never retried: a rejected login surfaces as ``WarmlinkAuthError``, and
        a valid JSON response carrying an API ``error_code`` is returned to the
        caller unchanged (it is data, not an exception, so the loop never sees
        it).

        ``idempotent`` guards writes. A safe-to-repeat read retries on any
        transient transport error. A write (device/control) is NOT idempotent,
        so it is retried ONLY when the request certainly never reached the
        server -- i.e. the connection could not be established -- and never
        after a timeout, reset, or 5xx, any of which could double-apply it.
        """
        if not self.token:
            if not await self.ensure_token():
                self._raise_login_failure(path)

        attempts = len(_RETRY_BACKOFFS) + 1
        for attempt in range(attempts):
            try:
                return await self._post_once(path, payload)
            except WarmlinkAuthError:
                raise
            except _TRANSIENT_EXC as e:
                # A write is only safe to retry when the connection was never
                # established (ClientConnectorError) -- the request provably
                # never reached the server, so it cannot have been applied.
                retryable = idempotent or isinstance(e, aiohttp.ClientConnectorError)
                is_last = attempt == attempts - 1
                if is_last or not retryable:
                    LOGGER.error("WarmLink API: Request failed to %s: %r", path, e)
                    raise
                delay = _RETRY_BACKOFFS[attempt]
                LOGGER.warning(
                    "WarmLink API: transient error on %s (%s), retry %d/%d in %ds: %r",
                    path, type(e).__name__, attempt + 1, attempts - 1, delay, e,
                )
                await asyncio.sleep(delay)

    async def _post_once(self, path, payload):
        """One POST attempt, with the existing token-expiry re-auth handling.

        Raises ``_TransientCloudError`` on 429/5xx so the caller's retry loop
        treats a transient server-side status the same as a dropped connection.
        """
        headers = {"x-token": self.token}
        async with self.session.post(f"{self.base_url}/{path}", json=payload, headers=headers) as r:
            if r.status == 429 or r.status >= 500:
                raise _TransientCloudError(f"HTTP {r.status} from {path}")
            data = await r.json()
            # Check for token expiration (-100 = "Please log in again")
            if r.status == 401 or data.get("error_code") == "401" or data.get("error_code") == "-100":
                LOGGER.debug("WarmLink API: Token expired, re-authenticating")
                if not await self.ensure_token(bad_token=headers["x-token"]):
                    self._raise_login_failure(path)
                headers = {"x-token": self.token}
                async with self.session.post(f"{self.base_url}/{path}", json=payload, headers=headers) as r2:
                    if r2.status == 429 or r2.status >= 500:
                        raise _TransientCloudError(f"HTTP {r2.status} from {path}")
                    return await r2.json()
            return data
    
    async def get_devices(self):
        """Get list of devices."""
        LOGGER.debug("WarmLink API: Fetching device list")
        payload = {
            "productIds": PRODUCT_IDS,
            "pageIndex": "1",
            "pageSize": "999"
        }
        result = await self.post(Endpoints.DeviceList, payload)
        device_count = len(result.get("objectResult", []))
        LOGGER.debug(f"WarmLink API: Found {device_count} device(s)")
        return result
    
    async def get_props_batch(self, device_code, codes):
        """Get properties for a device."""
        LOGGER.debug(f"WarmLink API: Fetching {len(codes)} properties")
        payload = {"deviceCode": device_code, "protocalCodes": codes}
        return await self.post(Endpoints.DeviceProperty, payload)

    async def set_value(self, device_code, protocol_code, value):
        """Write a single control value to the device (e.g. Power, Mode, R01).

        Uses the linked-go/AquaTemp control endpoint. The protocolCode strings
        match the same codes we read back (Power = on/off, R01 = DHW target,
        Mode = operating mode).
        """
        LOGGER.info(f"WarmLink API: Setting {protocol_code}={value} on device")
        payload = {
            "appId": "16",
            "param": [
                {
                    "deviceCode": device_code,
                    "protocolCode": protocol_code,
                    "value": str(value),
                }
            ],
        }
        # idempotent=False: a control write must not be auto-retried after an
        # ambiguous failure (timeout/reset/5xx) -- it may already have applied.
        result = await self.post(Endpoints.DeviceControl, payload, idempotent=False)
        LOGGER.debug(f"WarmLink API: Control response for {protocol_code}={value}: {result}")
        return result
