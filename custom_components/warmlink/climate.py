"""Climate platform for WarmLink integration.

Wraps the *space-conditioning* side of the heat pump (heating and cooling) as a
single Home Assistant ``climate`` entity, so it renders as a thermostat card:

  hvac_mode OFF   -> heat pump Power off
  hvac_mode HEAT  -> Power on + Mode = Heating (1);  target writes Heating Target (R02)
  hvac_mode COOL  -> Power on + Mode = Cooling (2);  target writes Cooling Target (R03)

  current_temperature = Outlet Water Temp (T02) — the process temperature the unit
                        actually regulates for space heating/cooling.

Notes / scope:
- This entity governs *space conditioning* only. Domestic hot water has its own
  ``water_heater`` entity (DHW setpoint R01). The combined "+ DHW" operating modes
  (3/4) are read back as HEAT/COOL here; to explicitly select a "+ DHW" combo, use
  the Operating Mode select.
- Setting a temperature while OFF is ignored (no active heating/cooling target).
- Changing hvac_mode writes the whole-unit Power switch, which will also trigger any
  automations bound to it (e.g. the underfloor-pump sync).
"""
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

POWER_CODE = "Power"
MODE_CODE = "Mode"
OUTLET_TEMP_CODE = "T02"

HEAT_TARGET_CODE = "R02"
HEAT_MIN_CODE = "R10"
HEAT_MAX_CODE = "R11"
COOL_TARGET_CODE = "R03"
COOL_MIN_CODE = "R08"
COOL_MAX_CODE = "R09"

# Raw Mode values (confirmed on hardware, see select.py).
MODE_HEATING = "1"
MODE_COOLING = "2"
HEATING_MODES = {"1", "3"}   # Heating, Heating + DHW
COOLING_MODES = {"2", "4"}   # Cooling, Cooling + DHW

DEFAULT_HEAT_MIN, DEFAULT_HEAT_MAX = 20, 60
DEFAULT_COOL_MIN, DEFAULT_COOL_MAX = 7, 30


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the WarmLink space-conditioning climate entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WarmlinkClimate(coordinator, entry)])
    LOGGER.info("WarmLink: Added space-conditioning climate entity")


class WarmlinkClimate(CoordinatorEntity, ClimateEntity):
    """Space heating/cooling as a climate entity (Power + Mode + R02/R03)."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.OFF, HVACMode.HEAT, HVACMode.COOL]
    _attr_target_temperature_step = 1
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )
    # We implement async_turn_on/off ourselves; opt out of the legacy shim.
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, entry):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_climate"
        self._attr_name = "Space Conditioning"

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (matches the other WarmLink entities)."""
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

    # -- helpers --------------------------------------------------------------
    def _raw(self, code):
        """Return a protocol code's raw value (string), or None."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    v = item.get("value")
                    return None if v in (None, "", "null") else str(v).strip()
        return None

    def _num(self, code):
        """Return a protocol code's value as float, or None."""
        v = self._raw(code)
        if v is None:
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _is_on(self):
        """True if the heat pump Power reads on."""
        v = self._raw(POWER_CODE)
        return v is not None and v not in ("0", "0.0")

    # -- state ----------------------------------------------------------------
    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def hvac_mode(self):
        """OFF if powered off or in DHW-only, else HEAT/COOL by operating mode."""
        if not self._is_on():
            return HVACMode.OFF
        mode = self._raw(MODE_CODE)
        if mode in COOLING_MODES:
            return HVACMode.COOL
        if mode in HEATING_MODES:
            return HVACMode.HEAT
        return HVACMode.OFF  # e.g. DHW only — no space conditioning

    @property
    def current_temperature(self):
        """Outlet water temperature (T02)."""
        return self._num(OUTLET_TEMP_CODE)

    def _active_target_codes(self):
        """Return (target, min, max, default_min, default_max) codes for the
        current mode, or None when no space-conditioning target applies."""
        mode = self._raw(MODE_CODE)
        if mode in COOLING_MODES:
            return (COOL_TARGET_CODE, COOL_MIN_CODE, COOL_MAX_CODE,
                    DEFAULT_COOL_MIN, DEFAULT_COOL_MAX)
        if mode in HEATING_MODES:
            return (HEAT_TARGET_CODE, HEAT_MIN_CODE, HEAT_MAX_CODE,
                    DEFAULT_HEAT_MIN, DEFAULT_HEAT_MAX)
        return None

    @property
    def target_temperature(self):
        """Current active space-conditioning setpoint (R02 heat / R03 cool)."""
        codes = self._active_target_codes()
        if not codes:
            return None
        return self._num(codes[0])

    @property
    def min_temp(self):
        """Lower bound of the active setpoint (heat R10 / cool R08)."""
        codes = self._active_target_codes()
        if not codes:
            return DEFAULT_HEAT_MIN
        v = self._num(codes[1])
        return v if v is not None else codes[3]

    @property
    def max_temp(self):
        """Upper bound of the active setpoint (heat R11 / cool R09)."""
        codes = self._active_target_codes()
        if not codes:
            return DEFAULT_HEAT_MAX
        v = self._num(codes[2])
        return v if v is not None else codes[4]

    # -- writes ---------------------------------------------------------------
    def _device_code(self):
        if self.coordinator.device_info:
            return self.coordinator.device_info.get("device_code")
        return None

    async def _write(self, code, value):
        """Send one control write and optimistically reflect it locally."""
        device_code = self._device_code()
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot write %s", code)
            return
        LOGGER.info("WarmLink: climate write %s=%s", code, value)
        resp = await self.coordinator.api.set_value(device_code, code, value)
        LOGGER.debug("WarmLink: climate %s=%s response: %s", code, value, resp)
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    item["value"] = value
                    break

    async def async_set_temperature(self, **kwargs):
        """Write the active setpoint (heat -> R02, cool -> R03)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        codes = self._active_target_codes()
        if not codes:
            LOGGER.warning("WarmLink: set_temperature ignored — no active heat/cool mode")
            return
        target = int(round(float(temp)))
        lo, hi = int(round(self.min_temp)), int(round(self.max_temp))
        target = max(lo, min(hi, target))
        await self._write(codes[0], f"{target}.0")
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(self.coordinator.data)

    async def async_set_hvac_mode(self, hvac_mode):
        """Map OFF/HEAT/COOL to Power + Mode writes."""
        if hvac_mode == HVACMode.OFF:
            await self._write(POWER_CODE, "0")
        elif hvac_mode == HVACMode.HEAT:
            await self._write(POWER_CODE, "1")
            await self._write(MODE_CODE, MODE_HEATING)
        elif hvac_mode == HVACMode.COOL:
            await self._write(POWER_CODE, "1")
            await self._write(MODE_CODE, MODE_COOLING)
        else:
            LOGGER.warning("WarmLink: unsupported hvac_mode %s", hvac_mode)
            return
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(self.coordinator.data)
        await self.coordinator.async_request_refresh()

    async def async_turn_on(self):
        """Turn on — resume heating (safe default)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        """Turn off the heat pump."""
        await self.async_set_hvac_mode(HVACMode.OFF)
