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
    if coordinator.value(COOLING_FUNCTION_CODE) is not None:
        # Gate on the device actually REPORTING H05, not on is_radiator: heat
        # pumps carry the flag too (their cooling modes are inert without it),
        # and a radiator added via manual device_code (no productId) still gets
        # its cooling gate this way.
        # Deliberately a SEPARATE switch (not a climate hvac mode): enabling the
        # cooling function must be an explicit two-step act, so a stray tap on
        # the thermostat card can never start cooling on uninsulated pipes.
        entities.append(WarmlinkCoolingFunctionSwitch(coordinator, entry))
    # Silent mode (mute). Prefer the dedicated H22 code; fall back to the
    # hanControl bitmask only on models that don't expose H22. A given unit
    # reports one path or the other, so this yields exactly one Silent Mode
    # switch (the elif keeps units that report both from getting two).
    if coordinator.value(SILENT_MODE_CODE) is not None:
        entities.append(WarmlinkSilentSwitch(coordinator, entry))
    elif coordinator.value(HAN_CONTROL_CODE) is not None:
        entities.append(WarmlinkSilentMaskSwitch(coordinator, entry))
    # Weather-compensation enable flag (H36). Only created on units that report
    # it, so radiators and units without the AT curve are unaffected.
    if coordinator.value(WEATHER_COMP_ENABLE_CODE) is not None:
        entities.append(WarmlinkWeatherCompSwitch(coordinator, entry))
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
        self._attr_name = "Cooling Function"
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


# Silent mode (mute). Two control paths exist across WarmLink/LinkedGo models:
#  - H22 (enable_silent_mode): a dedicated 1/0 code, same shape as the H05
#    cooling gate. Preferred -- no cross-model bit-mapping risk, and it is what
#    this maintainer's own Zealux "Winter friend" unit uses (its hanControl
#    register reads all-zeros while H22 carries the real mute flag, alongside
#    the separate silent on/off timer codes).
#  - hanControl: a 16-bit manual-control mask where bit index 14 is the mute
#    bit (reverse-engineered on FoxAIR/Phnix units). Fallback only, for models
#    that do NOT expose H22.
SILENT_MODE_CODE = "H22"
HAN_CONTROL_CODE = "hanControl"
MUTE_BIT_INDEX = 14


class WarmlinkSilentSwitch(WarmlinkPowerSwitch):
    """Silent mode (mute) via the dedicated H22 code (preferred path)."""

    def __init__(self, coordinator, entry):
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_silent_mode_switch"
        self._attr_name = "Silent Mode"
        self._attr_icon = "mdi:volume-mute"

    def _power_value(self):
        """Return the raw H22 value (overrides the Power lookup)."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == SILENT_MODE_CODE:
                    return item.get("value")
        return None

    async def _set_power(self, turn_on: bool) -> None:
        """Write H22 (1 = silent on, 0 = off)."""
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set silent mode")
            return
        value = "1" if turn_on else "0"
        LOGGER.info(f"WarmLink: Requesting silent mode H22={value}")
        await self.coordinator.api.set_value(device_code, SILENT_MODE_CODE, value)
        await self.coordinator.async_request_refresh()


class WarmlinkSilentMaskSwitch(WarmlinkPowerSwitch):
    """Silent mode fallback for models without H22: bit 14 of hanControl.

    Only created when the device does not report H22 (see async_setup_entry),
    so the two silent-mode switches are mutually exclusive on any one unit.
    """

    def __init__(self, coordinator, entry):
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_silent_mode_switch"
        self._attr_name = "Silent Mode"
        self._attr_icon = "mdi:volume-mute"

    @property
    def is_on(self):
        """Return True if the mute bit of the hanControl mask is set."""
        val = self.coordinator.value(HAN_CONTROL_CODE)
        if val is not None and len(str(val)) == 16:
            return str(val)[MUTE_BIT_INDEX] == "1"
        return None

    async def _set_power(self, turn_on: bool) -> None:
        """Flip only the mute bit, preserving every other control flag."""
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set silent mode")
            return
        current = self.coordinator.value(HAN_CONTROL_CODE)
        # Clobber-guard: only edit a mask we can actually read. The naive
        # fallback (rebuild a zeroed 16-char mask) would wipe any other active
        # bits on units that carry them, so bail out with a warning instead.
        if current is None or len(str(current)) != 16:
            LOGGER.warning(
                "WarmLink: hanControl is not a valid 16-char mask (%r); "
                "skipping silent-mode write to avoid clobbering other bits",
                current,
            )
            return
        bits = list(str(current))
        bits[MUTE_BIT_INDEX] = "1" if turn_on else "0"
        mask = "".join(bits)
        LOGGER.info(f"WarmLink: Requesting silent mode hanControl={mask}")
        await self.coordinator.api.set_value(device_code, HAN_CONTROL_CODE, mask)
        await self.coordinator.async_request_refresh()


# Weather-compensation enable flag (H36). 1 = the unit follows its AT/weather
# curve, so a manual heating target is inert; 0 = the manual target applies.
# Exposing this as a writable switch (same 1/0 shape as H05/H22) lets an
# automation drop to a manual target during cheap electricity and hand control
# back to the curve afterwards -- the price-/comfort-based tuning asked for in
# issue #40. The slope and offset are already writable via the number platform.
WEATHER_COMP_ENABLE_CODE = "H36"


class WarmlinkWeatherCompSwitch(WarmlinkPowerSwitch):
    """Enable/disable the weather-compensation curve (H36)."""

    def __init__(self, coordinator, entry):
        """Initialize the switch."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_weather_comp_enable_switch"
        self._attr_name = "Weather Compensation"
        self._attr_icon = "mdi:weather-partly-cloudy"

    def _power_value(self):
        """Return the raw H36 value (overrides the Power lookup)."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == WEATHER_COMP_ENABLE_CODE:
                    return item.get("value")
        return None

    async def _set_power(self, turn_on: bool) -> None:
        """Write H36 (1 = weather comp on, 0 = off)."""
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set weather compensation")
            return
        value = "1" if turn_on else "0"
        LOGGER.info(f"WarmLink: Requesting weather compensation H36={value}")
        await self.coordinator.api.set_value(device_code, WEATHER_COMP_ENABLE_CODE, value)
        await self.coordinator.async_request_refresh()
