"""Climate platform for WarmLink smart radiators.

Only set up for devices whose productId is in RADIATOR_PRODUCT_IDS (LinkedGo
smart radiators, e.g. Scantherm panels). Heat pumps keep their existing
sensor/switch/select entities and are not affected.

Protocol (verified against real hardware via app capture):
  Power             "1"/"0"        on/off
  R02               float          target temperature (°C, writable)
  T1                float          current room temperature (°C)
  Fan_Speed_Setting "1".."6"       heat level (writable)
  R05 / R01         float          min (anti-freeze) / max temperature limits
  2013              float          current power draw (kW) -> hvac_action
"""
import logging

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

POWER_CODE = "Power"
HEAT_TARGET_CODE = "R02"   # heating setpoint (panel SET TEMP in heating mode)
COOL_TARGET_CODE = "R03"   # cooling setpoint (panel SET TEMP in cooling mode)
CURRENT_CODE = "T1"
HEAT_LEVEL_CODE = "Fan_Speed_Setting"
MIN_TEMP_CODE = "R05"
MAX_TEMP_CODE = "R01"      # limit for the heating dial (raising it widens the app/panel range)
POWER_KW_CODE = "2013"

# Mode enum — verified on hardware 2026-08-15 (panel LEDs while switching):
#   "1" = COOLING, "4" = HEATING. Other values unobserved.
MODE_CODE = "Mode"
MODE_COOL = "1"
MODE_HEAT = "4"

HEAT_LEVELS = ["1", "2", "3", "4", "5", "6"]


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the radiator climate entity (radiators only)."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.is_radiator:
        LOGGER.debug("WarmLink: Not a radiator — skipping climate platform")
        return
    async_add_entities([WarmlinkRadiatorClimate(coordinator, entry)])
    LOGGER.info("WarmLink: Added radiator climate entity")


class WarmlinkRadiatorClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for a LinkedGo/WarmLink smart radiator."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.OFF]
    _attr_fan_modes = HEAT_LEVELS
    _attr_target_temperature_step = 0.5
    _attr_supported_features = (
        ClimateEntityFeature.TARGET_TEMPERATURE
        | ClimateEntityFeature.FAN_MODE
        | ClimateEntityFeature.TURN_ON
        | ClimateEntityFeature.TURN_OFF
    )

    def __init__(self, coordinator, entry):
        """Initialize the climate entity."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_radiator_climate"
        self._attr_name = None  # use the device name
        # Cache the last known device limits so a poll that happens to miss
        # R05/R01 doesn't make the UI flap back to the hardcoded defaults.
        self._min_temp = 5.0
        self._max_temp = 30.0

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (matches the sensors/switch device)."""
        device_name = "WarmLink"
        device_model = "Radiator"

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

    def _float(self, code):
        """Coordinator value as float, or None."""
        v = self.coordinator.value(code)
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    @property
    def available(self) -> bool:
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    def _is_cooling_mode(self):
        return str(self.coordinator.value(MODE_CODE)) == MODE_COOL

    @property
    def hvac_mode(self):
        v = self.coordinator.value(POWER_CODE)
        if v is None:
            return None
        if str(v).strip() in ("0", "0.0"):
            return HVACMode.OFF
        mode = str(self.coordinator.value(MODE_CODE))
        if mode == MODE_COOL:
            return HVACMode.COOL
        if mode == MODE_HEAT:
            return HVACMode.HEAT
        return None  # unobserved mode value — don't guess

    @property
    def hvac_action(self):
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        kw = self._float(POWER_KW_CODE)
        if kw is None:
            return None
        if kw <= 0:
            return HVACAction.IDLE
        return HVACAction.COOLING if self._is_cooling_mode() else HVACAction.HEATING

    @property
    def current_temperature(self):
        return self._float(CURRENT_CODE)

    @property
    def target_temperature(self):
        # The panel's SET TEMP follows the active mode: R03 in cooling, R02 in
        # heating — mirror that so HA always shows what the display shows.
        code = COOL_TARGET_CODE if self._is_cooling_mode() else HEAT_TARGET_CODE
        return self._float(code)

    @property
    def min_temp(self):
        if self._is_cooling_mode():
            return 5.0  # cooling dial limits are unmapped — permissive static range
        v = self._float(MIN_TEMP_CODE)
        if v is not None:
            self._min_temp = v
        return self._min_temp

    @property
    def max_temp(self):
        if self._is_cooling_mode():
            return 35.0  # cooling dial limits are unmapped — permissive static range
        v = self._float(MAX_TEMP_CODE)
        if v is not None:
            self._max_temp = v
        return self._max_temp

    @property
    def fan_mode(self):
        v = self.coordinator.value(HEAT_LEVEL_CODE)
        if v is None:
            return None
        v = str(int(float(v))) if str(v).replace(".", "").isdigit() else str(v)
        return v if v in HEAT_LEVELS else None

    async def _set(self, code, value):
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot control radiator")
            return
        await self.coordinator.api.set_value(device_code, code, value)
        await self.coordinator.async_request_refresh()

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        code = COOL_TARGET_CODE if self._is_cooling_mode() else HEAT_TARGET_CODE
        await self._set(code, f"{float(temp):.1f}")

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode in HEAT_LEVELS:
            await self._set(HEAT_LEVEL_CODE, fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            await self._set(POWER_CODE, "0")
            return
        target = MODE_COOL if hvac_mode == HVACMode.COOL else MODE_HEAT
        if str(self.coordinator.value(MODE_CODE)) != target:
            await self._set(MODE_CODE, target)
        await self._set(POWER_CODE, "1")

    async def async_turn_on(self):
        await self._set(POWER_CODE, "1")

    async def async_turn_off(self):
        await self._set(POWER_CODE, "0")
