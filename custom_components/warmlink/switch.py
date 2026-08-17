"""Switch platform for WarmLink integration."""
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

# Control code for turning the heat pump on/off.
# Same protocolCode is used by the linked-go/AquaTemp control endpoint.
POWER_CODE = "Power"


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink switch entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [WarmlinkPowerSwitch(coordinator, entry)]
    if getattr(coordinator, "is_radiator", False):
        # Deliberately a SEPARATE switch (not a climate hvac mode): enabling the
        # cooling function must be an explicit two-step act, so a stray tap on
        # the thermostat card can never start cooling on uninsulated pipes.
        entities.append(WarmlinkCoolingFunctionSwitch(coordinator, entry))
    async_add_entities(entities)
    LOGGER.info("WarmLink: Added %d switch(es)", len(entities))


class WarmlinkPowerSwitch(CoordinatorEntity, SwitchEntity):
    """Switch to turn the WarmLink heat pump on/off via the Power code."""

    def __init__(self, coordinator, entry):
        """Initialize the switch."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_power_switch"
        self._attr_name = "Power"
        self._attr_icon = "mdi:power"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (matches the sensors/button device)."""
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

    def _power_value(self):
        """Return the raw value of the Power code, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == POWER_CODE:
                    return item.get("value")
        return None

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def is_on(self):
        """Return True if the heat pump is on.

        The Power code reads back as "1" (on) / "0" (off). We treat any
        non-zero/non-empty value as on so this still works if the value
        turns out to be a numeric power reading instead of a flag.
        """
        value = self._power_value()
        if value in (None, "", "null"):
            return None
        return str(value).strip() not in ("0", "0.0")

    async def _set_power(self, turn_on: bool) -> None:
        """Send the Power control command to the device."""
        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set power")
            return

        value = "1" if turn_on else "0"
        LOGGER.info(f"WarmLink: Requesting Power={value}")
        resp = await self.coordinator.api.set_value(device_code, POWER_CODE, value)
        LOGGER.info(f"WarmLink: Power={value} command response: {resp}")
        # Refresh so the switch reflects the new state from the API
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the heat pump on."""
        await self._set_power(True)

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the heat pump off."""
        await self._set_power(False)


# Radiator cooling-function gate. H05=0 keeps the device heat-only (the app's
# cooling button is dead); H05=1 unlocks cooling. Write-verified on hardware.
COOLING_FUNCTION_CODE = "H05"


class WarmlinkCoolingFunctionSwitch(WarmlinkPowerSwitch):
    """Explicit enable/disable of the radiator's cooling function (H05)."""

    def __init__(self, coordinator, entry):
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_cooling_function_switch"
        self._attr_name = "Kølefunktion"
        self._attr_icon = "mdi:snowflake"

    def _power_value(self):
        """Return the raw H05 value (overrides the Power lookup)."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == COOLING_FUNCTION_CODE:
                    return item.get("value")
        return None

    async def _set_power(self, turn_on: bool) -> None:
        """Write H05 instead of Power."""
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set cooling function")
            return
        value = "1" if turn_on else "0"
        LOGGER.info(f"WarmLink: Requesting cooling function H05={value}")
        await self.coordinator.api.set_value(device_code, COOLING_FUNCTION_CODE, value)
        await self.coordinator.async_request_refresh()
