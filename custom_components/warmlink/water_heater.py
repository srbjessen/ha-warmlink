"""Water heater platform for WarmLink integration.

Exposes the domestic-hot-water (DHW) side of the heat pump as a standard Home
Assistant ``water_heater`` entity, so it renders as a proper hot-water tank card
with a temperature dial:

  current_temperature = DHW tank temp  (T08)
  target_temperature  = DHW setpoint   (R01, writable via the cloud control API)
  min/max             = device's own DHW range (R36 / R37, read live)

This is complementary to the DHW Target *select*: same underlying R01 write, but
a nicer card and a first-class target for the HA UI/voice/automations.
"""
import logging

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

DHW_TARGET_CODE = "R01"
DHW_MIN_CODE = "R36"
DHW_MAX_CODE = "R37"
DHW_TANK_TEMP_CODE = "T08"
DEFAULT_MIN = 47
DEFAULT_MAX = 60


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the WarmLink DHW water heater entity."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WarmlinkDHWWaterHeater(coordinator, entry)])
    LOGGER.info("WarmLink: Added DHW water heater entity")


class WarmlinkDHWWaterHeater(CoordinatorEntity, WaterHeaterEntity):
    """DHW tank as a water_heater entity (writes R01)."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_supported_features = WaterHeaterEntityFeature.TARGET_TEMPERATURE
    _attr_target_temperature_step = 1

    def __init__(self, coordinator, entry):
        """Initialize the water heater."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dhw_water_heater"
        self._attr_name = "Hot Water"
        self._attr_icon = "mdi:water-boiler"

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

    def _num(self, code):
        """Return a protocol code's value as float, or None if unusable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    v = item.get("value")
                    if v in (None, "", "null"):
                        return None
                    try:
                        return float(v)
                    except (TypeError, ValueError):
                        return None
        return None

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def min_temp(self):
        """Lower bound of the DHW setpoint (live from R36)."""
        v = self._num(DHW_MIN_CODE)
        return v if v is not None else DEFAULT_MIN

    @property
    def max_temp(self):
        """Upper bound of the DHW setpoint (live from R37)."""
        v = self._num(DHW_MAX_CODE)
        return v if v is not None else DEFAULT_MAX

    @property
    def current_temperature(self):
        """Current DHW tank temperature (T08)."""
        return self._num(DHW_TANK_TEMP_CODE)

    @property
    def target_temperature(self):
        """Current DHW setpoint (R01)."""
        return self._num(DHW_TARGET_CODE)

    async def async_set_temperature(self, **kwargs):
        """Write a new DHW setpoint (whole degrees)."""
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        target = int(round(float(temp)))
        lo, hi = int(round(self.min_temp)), int(round(self.max_temp))
        target = max(lo, min(hi, target))  # clamp into the device range

        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set DHW target")
            return

        out = f"{target}.0"
        LOGGER.info("WarmLink: Requesting DHW target R01=%s (water_heater)", out)
        resp = await self.coordinator.api.set_value(device_code, DHW_TARGET_CODE, out)
        LOGGER.info("WarmLink: R01=%s water_heater response: %s", out, resp)
        # Optimistic local update; the next poll reconciles.
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == DHW_TARGET_CODE:
                    item["value"] = out
                    break
            self.coordinator.async_set_updated_data(self.coordinator.data)
