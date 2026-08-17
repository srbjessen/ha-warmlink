"""Select platform for WarmLink integration.

Exposes the heat pump's operating Mode as a writable ``select`` entity so it can
be driven from Home Assistant automations. The main use case is the summer
anti-thermosiphon trick: parking the 3-way diverter off the DHW tank by writing
``Mode = Heating + DHW`` after a reheat completes breaks the passive convection
loop that otherwise bleeds tank heat out through the (cold) outdoor unit.

Only the modes we have *confirmed* on real hardware are exposed, on purpose:
writing an unconfirmed Mode value risks selecting an unintended mode. The
confirmed set is DHW only / Heating / Cooling / Heating + DHW / Cooling + DHW
(raw values 0/1/2/3/4 — see MODE_OPTIONS). Add more options here once they are
calibrated against the unit's own panel.
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

# Operating modes confirmed on real hardware (label -> raw protocol value).
#   0 = DHW only        -> 3-way valve to the tank
#   1 = Heating         -> valve fully off the tank (DHW port closed); the ideal
#                          anti-siphon park: no DHW component, so no periodic
#                          forced switch back to the tank (unlike Heating + DHW).
#   2 = Cooling         -> cooling only; setpoint is the Cooling Target (R03),
#                          range R08/R09 — separate from the heating/DHW ranges.
#   3 = Heating + DHW   -> valve toward heating, but the unit forces a switch
#                          back to DHW on a timer (H32, ~90 min) to service the tank.
#   4 = Cooling + DHW   -> cooling with periodic DHW service (cooling setpoint R03,
#                          DHW setpoint R01); the DHW half behaves like mode 3.
# Cooling modes (2/4) only actually engage when H05 (Enable Cooling Function) = 1
# on the unit; otherwise the firmware ignores the write, same as in the app.
# Values verified per issue #17.
MODE_OPTIONS = {
    "DHW only": "0",
    "Heating": "1",
    "Cooling": "2",
    "Heating + DHW": "3",
    "Cooling + DHW": "4",
}
VALUE_TO_LABEL = {v: k for k, v in MODE_OPTIONS.items()}


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink select entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if getattr(coordinator, "is_radiator", False):
        # Radiators have no DHW tank or diverter valve, and their Mode values
        # have different semantics — the climate entity covers their controls.
        LOGGER.debug("WarmLink: Radiator — skipping heat-pump mode/DHW selects")
        return
    async_add_entities([
        WarmlinkModeSelect(coordinator, entry),
        WarmlinkDHWTargetSelect(coordinator, entry),
        WarmlinkCoolingTargetSelect(coordinator, entry),
        WarmlinkHeatingTargetSelect(coordinator, entry),
    ])
    LOGGER.info("WarmLink: Added operating mode + DHW/cooling/heating target selects")


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


# DHW target temperature as a discrete °C dropdown (writes the R01 code).
# The selectable range is read live from the device's own min/max registers
# (R36 = min, R37 = max), so it matches each unit's configured range and tracks
# changes made in the WarmLink app. Falls back to 47..60 if not reported.
DHW_TARGET_CODE = "R01"
DHW_MIN_CODE = "R36"
DHW_MAX_CODE = "R37"
DEFAULT_MIN = 47
DEFAULT_MAX = 60


class WarmlinkDHWTargetSelect(CoordinatorEntity, SelectEntity):
    """Writable DHW target temperature as a discrete °C dropdown (R01).

    A dropdown of whole-degree options is a single, unambiguous write per
    change — unlike a stepper/box, which sends one cloud write per increment
    and races over the slow cloud round-trip.
    """

    def __init__(self, coordinator, entry):
        """Initialize the DHW target select."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_dhw_target_select"
        self._attr_name = "DHW Target Temperature"
        self._attr_icon = "mdi:thermometer-water"
        # options are computed dynamically from the device range (see `options`)

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

    def _code_value(self, code):
        """Return the raw value of a protocol code, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    return item.get("value")
        return None

    def _range(self):
        """Return (min, max) °C from the device's R36/R37, else the defaults."""
        lo, hi = DEFAULT_MIN, DEFAULT_MAX
        try:
            v = self._code_value(DHW_MIN_CODE)
            if v not in (None, "", "null"):
                lo = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        try:
            v = self._code_value(DHW_MAX_CODE)
            if v not in (None, "", "null"):
                hi = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        if lo > hi:  # guard against an implausible / partial report
            lo, hi = DEFAULT_MIN, DEFAULT_MAX
        return lo, hi

    @property
    def options(self):
        """Whole-degree options across the device's reported range (live)."""
        lo, hi = self._range()
        return [str(t) for t in range(lo, hi + 1)]

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def current_option(self):
        """Return the current DHW target as a dropdown option (rounded to °C)."""
        value = self._code_value(DHW_TARGET_CODE)
        if value in (None, "", "null"):
            return None
        try:
            opt = str(int(round(float(value))))
        except (TypeError, ValueError):
            return None
        return opt if opt in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Write the chosen DHW target temperature to the device."""
        try:
            target = int(round(float(option)))
        except (ValueError, TypeError):
            LOGGER.error("WarmLink: Unrecognised DHW target option %s", option)
            return
        if str(target) not in self.options:
            lo, hi = self._range()
            LOGGER.error("WarmLink: DHW target %s out of device range %s-%s", target, lo, hi)
            return

        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set DHW target")
            return

        out = f"{target}.0"
        LOGGER.info("WarmLink: Requesting DHW target R01=%s (select)", out)
        resp = await self.coordinator.api.set_value(device_code, DHW_TARGET_CODE, out)
        LOGGER.info("WarmLink: R01=%s select response: %s", out, resp)
        # Optimistically reflect the new value so the dropdown updates instantly;
        # the next scheduled poll reconciles (and corrects if the device clamps).
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == DHW_TARGET_CODE:
                    item["value"] = out
                    break
            self.coordinator.async_set_updated_data(self.coordinator.data)


# Cooling target temperature as a discrete °C dropdown (writes the R03 code).
# Mirrors the DHW target select exactly, with cooling codes swapped in:
#   R03 = Cooling Target Temp (write)   R08 = Min Cooling Target   R09 = Max Cooling Target
# The selectable range is read live from R08/R09, so it matches each unit's own
# configured range and tracks changes made in the WarmLink app. Falls back to
# 7..30 if the range registers are not reported.
COOL_TARGET_CODE = "R03"
COOL_MIN_CODE = "R08"
COOL_MAX_CODE = "R09"
DEFAULT_COOL_MIN = 7
DEFAULT_COOL_MAX = 30


class WarmlinkCoolingTargetSelect(CoordinatorEntity, SelectEntity):
    """Writable cooling target temperature as a discrete °C dropdown (R03).

    Resolves the cooling half of issue #17. Like the DHW target, a dropdown of
    whole-degree options is a single, unambiguous write per change — unlike a
    stepper/box, which sends one cloud write per increment and races over the
    slow cloud round-trip. The write only takes effect on the unit while it is
    in a cooling mode (H05 = Enable Cooling Function = 1); otherwise the value
    is stored/ignored by the firmware, same as setting it in the app.
    """

    def __init__(self, coordinator, entry):
        """Initialize the cooling target select."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_cooling_target_select"
        self._attr_name = "Cooling Target Temperature"
        self._attr_icon = "mdi:snowflake-thermometer"
        # options are computed dynamically from the device range (see `options`)

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

    def _code_value(self, code):
        """Return the raw value of a protocol code, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    return item.get("value")
        return None

    def _range(self):
        """Return (min, max) °C from the device's R08/R09, else the defaults."""
        lo, hi = DEFAULT_COOL_MIN, DEFAULT_COOL_MAX
        try:
            v = self._code_value(COOL_MIN_CODE)
            if v not in (None, "", "null"):
                lo = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        try:
            v = self._code_value(COOL_MAX_CODE)
            if v not in (None, "", "null"):
                hi = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        if lo > hi:  # guard against an implausible / partial report
            lo, hi = DEFAULT_COOL_MIN, DEFAULT_COOL_MAX
        return lo, hi

    @property
    def options(self):
        """Whole-degree options across the device's reported range (live)."""
        lo, hi = self._range()
        return [str(t) for t in range(lo, hi + 1)]

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def current_option(self):
        """Return the current cooling target as a dropdown option (rounded to °C)."""
        value = self._code_value(COOL_TARGET_CODE)
        if value in (None, "", "null"):
            return None
        try:
            opt = str(int(round(float(value))))
        except (TypeError, ValueError):
            return None
        return opt if opt in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Write the chosen cooling target temperature to the device."""
        try:
            target = int(round(float(option)))
        except (ValueError, TypeError):
            LOGGER.error("WarmLink: Unrecognised cooling target option %s", option)
            return
        if str(target) not in self.options:
            lo, hi = self._range()
            LOGGER.error("WarmLink: Cooling target %s out of device range %s-%s", target, lo, hi)
            return

        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set cooling target")
            return

        out = f"{target}.0"
        LOGGER.info("WarmLink: Requesting cooling target R03=%s (select)", out)
        resp = await self.coordinator.api.set_value(device_code, COOL_TARGET_CODE, out)
        LOGGER.info("WarmLink: R03=%s select response: %s", out, resp)
        # Optimistically reflect the new value so the dropdown updates instantly;
        # the next scheduled poll reconciles (and corrects if the device clamps).
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == COOL_TARGET_CODE:
                    item["value"] = out
                    break
            self.coordinator.async_set_updated_data(self.coordinator.data)


# Heating (space-heating) target temperature as a discrete °C dropdown (R02).
# Mirrors the DHW/cooling target selects with heating codes swapped in:
#   R02 = Heating Target Temp (write)   R10 = Min Heating Target   R11 = Max Heating Target
# Range is read live from R10/R11 and is independent of the cooling (R08/R09) and
# DHW (R36/R37) ranges. Applies while the unit is in a heating mode (Heating or
# Heating + DHW). Completes the writable-target set requested in issue #17.
HEAT_TARGET_CODE = "R02"
HEAT_MIN_CODE = "R10"
HEAT_MAX_CODE = "R11"
DEFAULT_HEAT_MIN = 20
DEFAULT_HEAT_MAX = 60


class WarmlinkHeatingTargetSelect(CoordinatorEntity, SelectEntity):
    """Writable heating target temperature as a discrete °C dropdown (R02)."""

    def __init__(self, coordinator, entry):
        """Initialize the heating target select."""
        super().__init__(coordinator)
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_heating_target_select"
        self._attr_name = "Heating Target Temperature"
        self._attr_icon = "mdi:radiator"
        # options are computed dynamically from the device range (see `options`)

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

    def _code_value(self, code):
        """Return the raw value of a protocol code, or None if unavailable."""
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == code:
                    return item.get("value")
        return None

    def _range(self):
        """Return (min, max) °C from the device's R10/R11, else the defaults."""
        lo, hi = DEFAULT_HEAT_MIN, DEFAULT_HEAT_MAX
        try:
            v = self._code_value(HEAT_MIN_CODE)
            if v not in (None, "", "null"):
                lo = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        try:
            v = self._code_value(HEAT_MAX_CODE)
            if v not in (None, "", "null"):
                hi = int(round(float(v)))
        except (TypeError, ValueError):
            pass
        if lo > hi:  # guard against an implausible / partial report
            lo, hi = DEFAULT_HEAT_MIN, DEFAULT_HEAT_MAX
        return lo, hi

    @property
    def options(self):
        """Whole-degree options across the device's reported range (live)."""
        lo, hi = self._range()
        return [str(t) for t in range(lo, hi + 1)]

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def current_option(self):
        """Return the current heating target as a dropdown option (rounded to °C)."""
        value = self._code_value(HEAT_TARGET_CODE)
        if value in (None, "", "null"):
            return None
        try:
            opt = str(int(round(float(value))))
        except (TypeError, ValueError):
            return None
        return opt if opt in self.options else None

    async def async_select_option(self, option: str) -> None:
        """Write the chosen heating target temperature to the device."""
        try:
            target = int(round(float(option)))
        except (ValueError, TypeError):
            LOGGER.error("WarmLink: Unrecognised heating target option %s", option)
            return
        if str(target) not in self.options:
            lo, hi = self._range()
            LOGGER.error("WarmLink: Heating target %s out of device range %s-%s", target, lo, hi)
            return

        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set heating target")
            return

        out = f"{target}.0"
        LOGGER.info("WarmLink: Requesting heating target R02=%s (select)", out)
        resp = await self.coordinator.api.set_value(device_code, HEAT_TARGET_CODE, out)
        LOGGER.info("WarmLink: R02=%s select response: %s", out, resp)
        # Optimistically reflect the new value so the dropdown updates instantly;
        # the next scheduled poll reconciles (and corrects if the device clamps).
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == HEAT_TARGET_CODE:
                    item["value"] = out
                    break
            self.coordinator.async_set_updated_data(self.coordinator.data)
