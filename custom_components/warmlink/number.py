"""Number platform for WarmLink integration.

Exposes the DHW (domestic hot water) target temperature as a writable
``number`` entity, so the hot-water setpoint can be set from Home Assistant —
on a schedule, by electricity price, or as part of an automation. Requested in
issue #9 ("missing set DHW temp").

Writes the ``R01`` protocol code (DHW Target Temp) through the same control
endpoint already used by the Power switch and the operating-mode select.
"""
import logging

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberMode,
)
from homeassistant.const import UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

# Control code for the DHW target temperature (same protocolCode read back on
# the "DHW Target Temp [R01]" sensor and accepted by the control endpoint).
DHW_TARGET_CODE = "R01"

# Fallback bounds if the device doesn't report its own range. On this hardware
# the min/max DHW target registers (R36/R37) are 47 / 60 °C.
DEFAULT_MIN = 47.0
DEFAULT_MAX = 60.0


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([WarmlinkDHWTargetNumber(coordinator, entry)])
    LOGGER.info("WarmLink: Added DHW target temperature number")


class WarmlinkDHWTargetNumber(CoordinatorEntity, NumberEntity):
    """Writable DHW target temperature (R01 code)."""

    _attr_device_class = NumberDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.CELSIUS
    _attr_native_step = 1.0
    _attr_mode = NumberMode.BOX

    def __init__(self, coordinator, entry):
        """Initialize the number."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dhw_target"
        self._attr_name = "DHW Target Temperature"
        self._attr_icon = "mdi:thermometer-water"
        # Prefer the device-reported range; fall back to sane defaults.
        rmin, rmax = self._reported_range()
        self._attr_native_min_value = rmin
        self._attr_native_max_value = rmax

    def _r01_item(self):
        """Return the raw R01 coordinator item, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == DHW_TARGET_CODE:
                    return item
        return None

    def _reported_range(self):
        """Return (min, max) from the device's reported range, else defaults."""
        rmin, rmax = DEFAULT_MIN, DEFAULT_MAX
        item = self._r01_item()
        if item:
            try:
                if item.get("rangeStart") not in (None, ""):
                    rmin = float(item.get("rangeStart"))
                if item.get("rangeEnd") not in (None, ""):
                    rmax = float(item.get("rangeEnd"))
            except (TypeError, ValueError):
                pass
        return rmin, rmax

    @property
    def device_info(self) -> DeviceInfo:
        """Return device info (matches the sensors/switch/select device)."""
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

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return the current DHW target temperature."""
        item = self._r01_item()
        if not item:
            return None
        value = item.get("value")
        if value in (None, "", "null"):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    async def async_set_native_value(self, value: float) -> None:
        """Write the new DHW target temperature to the device."""
        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set DHW target")
            return

        # Match the "55.0"-style value the API reads back / accepts.
        out = f"{value:.1f}"
        LOGGER.info("WarmLink: Requesting DHW target R01=%s", out)
        resp = await self.coordinator.api.set_value(device_code, DHW_TARGET_CODE, out)
        LOGGER.info("WarmLink: R01=%s command response: %s", out, resp)
        # Refresh so the number reflects the new value from the API.
        await self.coordinator.async_request_refresh()
