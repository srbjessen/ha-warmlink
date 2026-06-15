
import hashlib
import logging
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from ..common.endpoints import Endpoints

LOGGER = logging.getLogger(__name__)

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

class WarmlinkAPI:
    """API client for WarmLink."""
    
    def __init__(self, username, password, hass):
        """Initialize the API client."""
        self.username = username
        self.password = password
        self.base_url = "https://cloud.linked-go.com:449/crmservice/api"
        self.session = async_get_clientsession(hass)
        self.token = None
    
    async def login(self):
        """Login to the API."""
        LOGGER.debug(f"WarmLink API: Attempting login for user {self.username}")
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
            return False
        except Exception as e:
            LOGGER.error(f"WarmLink API: Login exception - {e}")
            return False
    
    async def post(self, path, payload):
        """Make a POST request to the API."""
        if not self.token:
            await self.login()
        headers = {"x-token": self.token}
        try:
            async with self.session.post(f"{self.base_url}/{path}", json=payload, headers=headers) as r:
                data = await r.json()
                # Check for token expiration (-100 = "Please log in again")
                if r.status == 401 or data.get("error_code") == "401" or data.get("error_code") == "-100":
                    LOGGER.debug("WarmLink API: Token expired, re-authenticating")
                    await self.login()
                    headers = {"x-token": self.token}
                    async with self.session.post(f"{self.base_url}/{path}", json=payload, headers=headers) as r2:
                        return await r2.json()
                return data
        except Exception as e:
            LOGGER.error(f"WarmLink API: Request failed to {path}: {e}")
            raise
    
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
