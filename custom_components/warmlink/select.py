"""Select platform for WarmLink integration.

Exposes the heat pump's operating Mode as a writable ``select`` entity so it can
be driven from Home Assistant automations. The main use case is the summer
anti-thermosiphon trick: parking the 3-way diverter off the DHW tank by writing
``Mode = Heating + DHW`` after a reheat completes breaks the passive convection
loop that otherwise bleeds tank heat out through the (cold) outdoor unit.

Only the modes we have *confirmed* on real hardware are exposed, on purpose:
writing an unconfirmed Mode value risks selecting a cooling mode. Add more
options here once they are calibrated against the unit's own panel.
"""
import logging

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

# Control code for the operating mode (same protocolCode used by the
# linked-go/AquaTemp control endpoint and read back on the Mode sensor).
MODE_CODE = "Mode"

# Confirmed-safe modes only (label -> raw protocol value).
#   0 = DHW only        -> 3-way valve to the tank
#   1 = Heating         -> valve fully off the tank (DHW port closed); the ideal
#                          anti-siphon park: no DHW component, so no periodic
#                          forced switch back to the tank (unlike Heating + DHW).
#   3 = Heating + DHW   -> valve toward heating, but the unit forces a switch
#                          back to DHW on a timer (H32, ~90 min) to service the tank.
# 2/4/5... are NOT confirmed (possible cooling) and are deliberately omitted.
MODE_OPTIONS = {
    "DHW only": "0",
    "Heating": "1",
    "Heating + DHW": "3",
}
VALUE_TO_LABEL = {v: k for k, v in MODE_OPTIONS.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WarmlinkModeSelect(coordinator, entry)])
    LOGGER.info("WarmLink: Added operating mode select")


class WarmlinkModeSelect(CoordinatorEntity, SelectEntity):
    """Writable operating-mode selector (Mode code)."""

    def __init__(self, coordinator, entry):
        """Initialize the select."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_mode_select"
        self._attr_name = "Operating Mode"
        self._attr_icon = "mdi:water-boiler"
        self._attr_options = list(MODE_OPTIONS.keys())

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (matches the sensors/switch/button device)."""
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

    def _mode_value(self):
        """Return the raw value of the Mode code, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == MODE_CODE:
                    return item.get("value")
        return None

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def current_option(self):
        """Return the current mode label.

        Returns ``None`` if the unit reports a mode we have not confirmed, so
        the UI shows "unknown" rather than misrepresenting an unverified value.
        """
        value = self._mode_value()
        if value in (None, "", "null"):
            return None
        return VALUE_TO_LABEL.get(str(value).strip())

    async def async_select_option(self, option: str) -> None:
        """Write the selected mode to the device."""
        value = MODE_OPTIONS.get(option)
        if value is None:
            LOGGER.error("WarmLink: Unknown mode option %s", option)
            return

        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set mode")
            return

        LOGGER.info("WarmLink: Requesting Mode=%s (%s)", value, option)
        resp = await self.coordinator.api.set_value(device_code, MODE_CODE, value)
        LOGGER.info("WarmLink: Mode=%s command response: %s", value, resp)
        # Refresh so the select reflects the new state from the API.
        await self.coordinator.async_request_refresh()
