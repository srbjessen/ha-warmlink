"""Climate platform for the WarmLink integration.

Two device families share this platform, selected at setup time by
``coordinator.is_radiator``:

* **Heat pumps** -> :class:`WarmlinkClimate` — the *space-conditioning* side
  (Power + Mode + R02/R03), rendered as a thermostat for the outlet-water loop.
  Domestic hot water is a separate ``water_heater`` entity.
* **Radiators** -> :class:`WarmlinkRadiatorClimate` — LinkedGo smart radiators
  (Scantherm LT fan coils): target/current temp, heat levels, full mode enum.

IMPORTANT: the two families use DIFFERENT raw ``Mode`` values (heat pump:
1=heating, 2=cooling; radiator: 1=cooling, 4=heating), so each class keeps its
own Mode constants below — they are intentionally not shared.
"""
import logging
import time

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, UPDATE_INTERVAL

LOGGER = logging.getLogger(__name__)

# Protocol codes that mean the same thing on both device families.
POWER_CODE = "Power"
MODE_CODE = "Mode"
HEAT_TARGET_CODE = "R02"   # heating setpoint (°C)
COOL_TARGET_CODE = "R03"   # cooling setpoint (°C)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up the climate entity — radiator or heat pump, by device type.

    Routing fails CLOSED: the two families use conflicting raw Mode enums, so
    a device we cannot positively identify (manual device_code with an empty
    cloud device list — no productId — and no T02 outlet sensor in the first
    refresh) gets NO climate entity, rather than the heat-pump one showing and
    writing inverted modes on what is actually a radiator.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    if getattr(coordinator, "is_radiator", False):
        async_add_entities([WarmlinkRadiatorClimate(coordinator, entry)])
        LOGGER.info("WarmLink: Added radiator climate entity")
    elif getattr(coordinator, "is_heat_pump", False):
        async_add_entities([WarmlinkClimate(coordinator, entry)])
        LOGGER.info("WarmLink: Added space-conditioning climate entity")
    else:
        LOGGER.warning(
            "WarmLink: Could not identify the device family (no known productId,"
            " no T02 outlet sensor) — not creating a climate entity, because the"
            " two families interpret Mode values differently. Power stays"
            " controllable via the switch; please report the device model so it"
            " can be mapped."
        )


# =============================================================================
# Heat pump — space conditioning (heating/cooling).  From #19 (richard-pm).
#
#   hvac_mode OFF   -> Power off
#   hvac_mode HEAT  -> Power on + Mode = Heating (1);  target writes R02
#   hvac_mode COOL  -> Power on + Mode = Cooling (2);  target writes R03
#   current_temperature = Outlet Water Temp (T02) — the process temperature the
#                         unit regulates for space heating/cooling.
# =============================================================================

OUTLET_TEMP_CODE = "T02"
COMPRESSOR_FREQ_CODE = "T30"   # compressor frequency (Hz); >0 = actually running
HEAT_MIN_CODE = "R10"
HEAT_MAX_CODE = "R11"
COOL_MIN_CODE = "R08"
COOL_MAX_CODE = "R09"

# Raw Mode values for HEAT PUMPS (confirmed on hardware, see select.py).
MODE_HEATING = "1"
MODE_COOLING = "2"
MODE_HEATING_DHW = "3"
MODE_COOLING_DHW = "4"
HEATING_MODES = {"1", "3"}   # Heating, Heating + DHW
COOLING_MODES = {"2", "4"}   # Cooling, Cooling + DHW
DHW_COMPONENT_MODES = {"0", "3", "4"}   # modes that service the DHW tank

DEFAULT_HEAT_MIN, DEFAULT_HEAT_MAX = 20, 60
DEFAULT_COOL_MIN, DEFAULT_COOL_MAX = 7, 30


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

    @property
    def hvac_action(self):
        """Real activity, from the compressor — not just the selected mode.

        OFF when powered off (or in DHW-only, which has no space-conditioning
        component); otherwise HEATING/COOLING only while the compressor is
        actually running (T30 > 0 Hz), else IDLE. This lets the thermostat card
        show the live active state (dial colour + Heating/Cooling/Idle label)
        rather than just the selected mode.
        """
        if not self._is_on():
            return HVACAction.OFF
        mode = self._raw(MODE_CODE)
        running = (self._num(COMPRESSOR_FREQ_CODE) or 0) > 0
        if mode in COOLING_MODES:
            return HVACAction.COOLING if running else HVACAction.IDLE
        if mode in HEATING_MODES:
            return HVACAction.HEATING if running else HVACAction.IDLE
        return HVACAction.OFF  # DHW only — no space conditioning

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
        """Map OFF/HEAT/COOL to Power + Mode writes.

        HEAT/COOL preserve the DHW component: when the current mode services
        the tank (0/3/4), write the combined mode (3/4) instead of the plain
        one (1/2). Otherwise picking HEAT on the thermostat card would
        silently stop hot-water production — with nothing in the UI saying so.
        """
        if hvac_mode == HVACMode.OFF:
            await self._write(POWER_CODE, "0")
        elif hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            keep_dhw = self._raw(MODE_CODE) in DHW_COMPONENT_MODES
            if hvac_mode == HVACMode.HEAT:
                mode = MODE_HEATING_DHW if keep_dhw else MODE_HEATING
            else:
                mode = MODE_COOLING_DHW if keep_dhw else MODE_COOLING
            await self._write(POWER_CODE, "1")
            await self._write(MODE_CODE, mode)
        else:
            LOGGER.warning("WarmLink: unsupported hvac_mode %s", hvac_mode)
            return
        if self.coordinator.data:
            self.coordinator.async_set_updated_data(self.coordinator.data)
        # No async_request_refresh() here: the optimistic update above already
        # reflects the change, and the cloud write lags 2–15 min — an immediate
        # poll would re-read the stale value and roll the UI back for minutes.
        # The scheduled 120 s poll reconciles (matches the DHW/target selects).

    async def async_turn_on(self):
        """Turn on — resume heating (safe default)."""
        await self.async_set_hvac_mode(HVACMode.HEAT)

    async def async_turn_off(self):
        """Turn off the heat pump."""
        await self.async_set_hvac_mode(HVACMode.OFF)


# =============================================================================
# Radiator — LinkedGo smart radiator (Scantherm LT fan coils).  From #20
# (Kristian-KK).  Protocol verified against real LT-8500-V hardware via app
# capture and a panel sweep with the owner watching:
#   Power             "1"/"0"        on/off
#   R02 / R03         float          heating / cooling setpoint (°C, writable)
#   T1                float          current room temperature (°C)
#   Fan_Speed_Setting "1".."6"       heat level (writable)
#   R05 / R01         float          min (anti-freeze) / max temperature limits
#   O2                float          ~1600 while the fan spins, 0 at rest
# =============================================================================

RAD_CURRENT_CODE = "T1"
RAD_HEAT_LEVEL_CODE = "Fan_Speed_Setting"
RAD_MIN_TEMP_CODE = "R05"
RAD_MAX_TEMP_CODE = "R01"      # limit for the heating dial (raising it widens the range)
RAD_FAN_RUNNING_CODE = "O2"    # ~1600 while the fan spins, 0 at rest.
                               # NOTE: "2013" reads a constant 1.2 (rated value, NOT
                               # live draw) — do not use it for activity detection.

# Radiator Mode enum — verified on hardware 2026-08-15 (panel LEDs/display during
# a controlled sweep with the owner watching): 0=auto, 1=cooling, 2=dehumidify
# ("dEH" on the display), 3=fan-only (ventilation), 4=heating. Value 5 is rejected
# by the device (snaps back to 0).
RAD_MODE_AUTO = "0"
RAD_MODE_COOL = "1"
RAD_MODE_DRY = "2"
RAD_MODE_FAN = "3"
RAD_MODE_HEAT = "4"

RAD_HEAT_LEVELS = ["1", "2", "3", "4", "5", "6"]

# How long an optimistic (pending) mode may stand in for the polled one before
# we conclude the device never took the write. Two poll cycles: one for the
# cloud's write lag, one for the next poll to actually read it back.
RAD_PENDING_MODE_TTL = 2 * UPDATE_INTERVAL


def _control_accepted(resp):
    """True when a control response looks like the cloud accepted the write.

    The response must actually be checked: a dead cloud session still answers,
    and treating any answer as "OK" has been seen on hardware to wave through
    a whole test phase of Mode writes that never reached the device.
    """
    if not isinstance(resp, dict):
        return False
    if resp.get("error_code") not in (None, "0"):
        return False
    return resp.get("isReusltSuc") is not False


class WarmlinkRadiatorClimate(CoordinatorEntity, ClimateEntity):
    """Climate entity for a LinkedGo/WarmLink smart radiator."""

    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    # DRY is advertised (not just reported): the panel can be put in dehumidify,
    # so HA must list it to render that state without an "invalid mode" warning.
    _attr_hvac_modes = [HVACMode.HEAT, HVACMode.COOL, HVACMode.DRY, HVACMode.FAN_ONLY, HVACMode.AUTO, HVACMode.OFF]
    _attr_fan_modes = RAD_HEAT_LEVELS
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
        # Optimistic mode after a mode write, so an immediate set_temperature
        # targets the RIGHT register instead of racing the 120 s poll.
        # Bounded by RAD_PENDING_MODE_TTL — see _device_mode().
        self._pending_mode = None
        self._pending_mode_expiry = 0.0

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

    def _device_mode(self):
        """Effective mode: optimistic pending value until the poll confirms it.

        The pending value is dropped when the poll confirms it — or when it
        expires unconfirmed (write lost or rejected by the device). Without
        the expiry, a failed write would latch the UI on a mode the device
        never entered, and set_temperature would keep targeting the wrong
        register (R02 vs R03) until a restart.
        """
        polled = str(self.coordinator.value(MODE_CODE))
        if self._pending_mode is not None:
            if polled == self._pending_mode:
                self._pending_mode = None  # confirmed by device
            elif time.monotonic() >= self._pending_mode_expiry:
                LOGGER.warning(
                    "WarmLink: Mode=%s was not confirmed by the device within %d s"
                    " — reverting to the polled mode (%s)",
                    self._pending_mode, RAD_PENDING_MODE_TTL, polled,
                )
                self._pending_mode = None
            else:
                return self._pending_mode
        return polled

    def _is_cooling_mode(self):
        return self._device_mode() == RAD_MODE_COOL

    @property
    def hvac_mode(self):
        v = self.coordinator.value(POWER_CODE)
        if v is None:
            return None
        if str(v).strip() in ("0", "0.0"):
            return HVACMode.OFF
        mode = self._device_mode()
        return {
            RAD_MODE_AUTO: HVACMode.AUTO,
            RAD_MODE_COOL: HVACMode.COOL,
            RAD_MODE_DRY: HVACMode.DRY,
            RAD_MODE_FAN: HVACMode.FAN_ONLY,
            RAD_MODE_HEAT: HVACMode.HEAT,
        }.get(mode)

    @property
    def hvac_action(self):
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        rpm = self._float(RAD_FAN_RUNNING_CODE)
        if rpm is None:
            return None
        if rpm <= 0:
            return HVACAction.IDLE
        mode = self._device_mode()
        if mode == RAD_MODE_COOL:
            return HVACAction.COOLING
        if mode == RAD_MODE_HEAT:
            return HVACAction.HEATING
        if mode == RAD_MODE_DRY:
            return HVACAction.DRYING  # dehumidify is not ventilation — say so
        if mode == RAD_MODE_FAN:
            return HVACAction.FAN
        return None  # auto/unmapped while spinning — direction unknown, don't guess

    @property
    def current_temperature(self):
        return self._float(RAD_CURRENT_CODE)

    @property
    def target_temperature(self):
        # The panel's SET TEMP follows the active mode: R03 in cooling, R02 in
        # heating — mirror that so HA always shows what the display shows.
        # Fan-only has no setpoint.
        if self._device_mode() == RAD_MODE_FAN:
            return None
        code = COOL_TARGET_CODE if self._is_cooling_mode() else HEAT_TARGET_CODE
        return self._float(code)

    @property
    def min_temp(self):
        if self._is_cooling_mode():
            return 5.0  # cooling dial limits are unmapped — permissive static range
        v = self._float(RAD_MIN_TEMP_CODE)
        if v is not None:
            self._min_temp = v
        return self._min_temp

    @property
    def max_temp(self):
        if self._is_cooling_mode():
            return 35.0  # cooling dial limits are unmapped — permissive static range
        v = self._float(RAD_MAX_TEMP_CODE)
        if v is not None:
            self._max_temp = v
        return self._max_temp

    @property
    def fan_mode(self):
        v = self.coordinator.value(RAD_HEAT_LEVEL_CODE)
        if v is None:
            return None
        v = str(int(float(v))) if str(v).replace(".", "").isdigit() else str(v)
        return v if v in RAD_HEAT_LEVELS else None

    async def _set(self, code, value):
        device_code = (self.coordinator.device_info or {}).get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot control radiator")
            return None
        resp = await self.coordinator.api.set_value(device_code, code, value)
        await self.coordinator.async_request_refresh()
        return resp

    async def async_set_temperature(self, **kwargs):
        temp = kwargs.get(ATTR_TEMPERATURE)
        if temp is None:
            return
        if self._device_mode() == RAD_MODE_FAN:
            LOGGER.debug("WarmLink: Ignoring set_temperature in fan-only mode")
            return
        code = COOL_TARGET_CODE if self._is_cooling_mode() else HEAT_TARGET_CODE
        await self._set(code, f"{float(temp):.1f}")

    async def async_set_fan_mode(self, fan_mode):
        if fan_mode in RAD_HEAT_LEVELS:
            await self._set(RAD_HEAT_LEVEL_CODE, fan_mode)

    async def async_set_hvac_mode(self, hvac_mode):
        if hvac_mode == HVACMode.OFF:
            # Powering off makes any optimistic mode moot; clear it so it
            # can't outlive the OFF and repoint a later set_temperature at
            # the wrong register.
            self._pending_mode = None
            await self._set(POWER_CODE, "0")
            return
        target = {
            HVACMode.COOL: RAD_MODE_COOL,
            HVACMode.DRY: RAD_MODE_DRY,
            HVACMode.FAN_ONLY: RAD_MODE_FAN,
            HVACMode.AUTO: RAD_MODE_AUTO,
        }.get(hvac_mode, RAD_MODE_HEAT)
        if self._device_mode() != target:
            self._pending_mode = target
            self._pending_mode_expiry = time.monotonic() + RAD_PENDING_MODE_TTL
            try:
                resp = await self._set(MODE_CODE, target)
            except Exception:
                self._pending_mode = None  # write never reached the cloud
                raise
            if not _control_accepted(resp):
                LOGGER.warning(
                    "WarmLink: Mode=%s write was not accepted (%s) — dropping"
                    " the optimistic mode", target, resp,
                )
                self._pending_mode = None
        await self._set(POWER_CODE, "1")

    async def async_turn_on(self):
        await self._set(POWER_CODE, "1")

    async def async_turn_off(self):
        self._pending_mode = None
        await self._set(POWER_CODE, "0")
