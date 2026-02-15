"""Button platform for WarmLink integration."""
import logging
from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink button entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    
    # Add refresh button
    async_add_entities([WarmlinkRefreshButton(coordinator, entry)])
    LOGGER.info("WarmLink: Added refresh button")

class WarmlinkRefreshButton(CoordinatorEntity, ButtonEntity):
    """Button to manually refresh WarmLink data."""
    
    def __init__(self, coordinator, entry):
        """Initialize the button."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_refresh_button"
        self._attr_name = "Refresh Data"
        self._attr_icon = "mdi:refresh"
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
        device_name = "WarmLink"
        device_model = "Heat Pump"
        
        if self.coordinator.device_info:
            nick = self.coordinator.device_info.get("device_nick_name")
            cust_model = self.coordinator.device_info.get("cust_model")
            
            if nick and nick.strip():
                device_name = nick
            elif cust_model and cust_model.strip():
                device_name = cust_model
            
            if cust_model and cust_model.strip():
                device_model = cust_model
        
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            name=device_name,
            manufacturer="WarmLink",
            model=device_model,
        )
    
    async def async_press(self) -> None:
        """Handle button press - refresh data from API."""
        LOGGER.info("WarmLink: Manual refresh requested via button")
        await self.coordinator.async_request_refresh()
        LOGGER.info("WarmLink: Manual refresh completed")
