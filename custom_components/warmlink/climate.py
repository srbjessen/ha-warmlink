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
TARGET_CODE = "R02"
CURRENT_CODE = "T1"
HEAT_LEVEL_CODE = "Fan_Speed_Setting"
MIN_TEMP_CODE = "R05"
MAX_TEMP_CODE = "R01"
POWER_KW_CODE = "2013"

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
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.OFF]
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

    @property
    def hvac_mode(self):
        v = self.coordinator.value(POWER_CODE)
        if v is None:
            return None
        return HVACMode.OFF if str(v).strip() in ("0", "0.0") else HVACMode.HEAT

    @property
    def hvac_action(self):
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        kw = self._float(POWER_KW_CODE)
        if kw is None:
            return None
        return HVACAction.HEATING if kw > 0 else HVACAction.IDLE

    @property
    def current_temperature(self):
        return self._float(CURRENT_CODE)

    @property
    def target_temperature(self):
        return self._float(TARGET_CODE)

    @property
    def min_temp(self):
        return self._float(MIN_TEMP_CODE) or 5.0

    @property
    def max_temp(self):
        return self._float(MAX_TEMP_CODE) or 30.0

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
        await self._set(TARGET_CODE, f"{float(temp):.1f}")

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode in HEAT_LEVELS:
            await self._set(HEAT_LEVEL_CODE, fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        await self._set(POWER_CODE, "0" if hvac_mode == HVACMode.OFF else "1")

    async def async_turn_on(self):
        await self._set(POWER_CODE, "1")

    async def async_turn_off(self):
        await self._set(POWER_CODE, "0")
