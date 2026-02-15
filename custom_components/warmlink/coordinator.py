
from datetime import timedelta
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from .managers.warmlink_api import WarmlinkAPI
from .const import DOMAIN, UPDATE_INTERVAL
import json, os, logging

LOGGER = logging.getLogger(__name__)

# Load codes once at module level (not in async context)
_CODES_PATH = os.path.join(os.path.dirname(__file__), "codes.json")
try:
    with open(_CODES_PATH) as f:
        _CODES = json.load(f)
    LOGGER.info(f"WarmLink: Loaded {len(_CODES)} codes from codes.json")
except Exception as e:
    _CODES = []
    LOGGER.error(f"WarmLink: Failed to load codes.json: {e}")

class WarmlinkCoordinator(DataUpdateCoordinator):
    """Coordinator for WarmLink data updates."""
    
    def __init__(self, hass, entry):
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self.api = WarmlinkAPI(entry.data["username"], entry.data["password"], hass)
        self.codes = _CODES
        self.device_info = None
        self._device_code = None
        self._logged_unknown_codes = set()  # Track unknown codes we've already logged
        self._logged_missing_codes = set()  # Track missing codes we've already logged
        super().__init__(
            hass,
            LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=UPDATE_INTERVAL)
        )
        LOGGER.info(f"WarmLink: Coordinator initialized with {UPDATE_INTERVAL}s update interval")
    
    async def _async_update_data(self):
        """Fetch data from API."""
        LOGGER.info(f"WarmLink: Starting scheduled update at {self.hass.loop.time()}")
        try:
            # Only fetch device list if we don't have device_code cached
            if not self._device_code:
                LOGGER.debug("WarmLink: Fetching device list...")
                devs = await self.api.get_devices()
                
                if not devs or "objectResult" not in devs or not devs["objectResult"]:
                    LOGGER.error("WarmLink: No devices returned from API")
                    raise UpdateFailed("No devices returned from API")
                device = devs["objectResult"][0]
                
                # Cache device info
                self._device_code = device.get("deviceCode")
                self.device_info = {
                    "device_code": device.get("deviceCode"),
                    "device_nick_name": device.get("deviceNickName"),
                    "product_id": device.get("productId"),
                    "device_id": device.get("deviceId"),
                    "cust_model": device.get("custModel"),
                    "model": device.get("model"),
                    "sn": device.get("sn"),
                }
                LOGGER.info(f"WarmLink: Connected to device {self.device_info.get('device_nick_name')} ({self.device_info.get('cust_model')})")
            
            # Fetch property data in batches
            results = []
            codes_requested = set()
            codes_received = set()
            batch_errors = []
            
            for i in range(0, len(self.codes), 20):
                batch = self.codes[i:i+20]
                codes_requested.update(batch)
                
                try:
                    resp = await self.api.get_props_batch(self._device_code, batch)
                    
                    # Check for API errors
                    if resp.get("error_code") != "0":
                        error_msg = resp.get("error_msg", "Unknown error")
                        batch_errors.append(f"Batch {i//20 + 1}: {error_msg}")
                        LOGGER.warning(f"WarmLink: API error for batch {i//20 + 1}: {error_msg}")
                        continue
                    
                    if resp.get("objectResult"):
                        batch_results = resp.get("objectResult", [])
                        results.extend(batch_results)
                        
                        # Track received codes
                        for item in batch_results:
                            code = item.get("code")
                            if code:
                                codes_received.add(code)
                                
                                # Log unknown codes (codes returned but not in our codes.json)
                                if code not in self.codes and code not in self._logged_unknown_codes:
                                    self._logged_unknown_codes.add(code)
                                    LOGGER.info(f"WarmLink: Discovered new code from API: {code} = {item.get('value')}")
                    
                except Exception as batch_error:
                    batch_errors.append(f"Batch {i//20 + 1}: {str(batch_error)}")
                    LOGGER.error(f"WarmLink: Error fetching batch {i//20 + 1}: {batch_error}")
            
            # Log codes that were requested but not returned
            missing_codes = codes_requested - codes_received
            new_missing = missing_codes - self._logged_missing_codes
            if new_missing:
                self._logged_missing_codes.update(new_missing)
                LOGGER.info(f"WarmLink: Codes requested but not returned by API: {sorted(new_missing)}")
            
            # Find codes with empty/null values
            empty_codes = [item.get("code") for item in results if item.get("value") in (None, "", "null")]
            if empty_codes and not hasattr(self, '_logged_empty_codes'):
                self._logged_empty_codes = True
                LOGGER.debug(f"WarmLink: Codes with empty values: {empty_codes}")
            
            # Log summary
            LOGGER.debug(f"WarmLink: Update complete. Requested: {len(codes_requested)}, Received: {len(codes_received)}, Missing: {len(missing_codes)}")
            
            # Log any codes returned that have unexpected format
            for item in results:
                code = item.get("code", "")
                if code and not any([
                    code.startswith(prefix) for prefix in 
                    ["A", "C", "D", "E", "F", "G", "H", "O", "P", "R", "S", "T", "Z", "KG", "DP", "M", "W", "SG", "Timer", "Fault", "Zone", "Power", "Mode", "han", "app", "comp", "code", "Main", "1", "2"]
                ]) and code not in self._logged_unknown_codes:
                    self._logged_unknown_codes.add(code)
                    LOGGER.info(f"WarmLink: Unknown code format: {code} = {item.get('value')}")
            
            if batch_errors:
                LOGGER.warning(f"WarmLink: {len(batch_errors)} batch errors occurred during update")
            
            # If we got no results but have old data, keep the old data
            if not results and self.data:
                LOGGER.warning("WarmLink: No new data received, keeping previous data")
                return self.data
            
            # If we got results, return them
            if results:
                return results
            
            # No data at all - this should only happen on first setup failure
            raise UpdateFailed("No data received from API")
            
        except UpdateFailed:
            # If we have old data, keep it instead of failing
            if self.data:
                LOGGER.warning("WarmLink: Update failed but keeping previous data")
                return self.data
            raise
        except Exception as e:
            LOGGER.error(f"WarmLink: Unexpected error during update: {e}", exc_info=True)
            # If we have old data, keep it instead of failing
            if self.data:
                LOGGER.warning("WarmLink: Unexpected error but keeping previous data")
                return self.data
            raise UpdateFailed(f"Error communicating with API: {e}")
