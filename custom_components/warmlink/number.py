"""Number platform for WarmLink — writable weather-compensation curve.

Exposes the heat pump's weather-compensation **offset** (and **slope**) as
writable ``number`` entities.

The unit has no room sensor of its own, so it runs its ambient-compensation
curve open-loop (water target = f(outdoor temp) from slope + offset). The
*offset* shifts that whole curve up/down, which makes it the natural actuator
for closing the loop from Home Assistant: HA measures the actual room
temperature and nudges the offset to hold a setpoint. The *slope* is the curve's
gradient (roughly °C of water per °C of outdoor change) and is normally set once
for the building.

Both write the same protocolCode strings we read back on the corresponding
sensors (``compensate_offset`` / ``compensate_slope``) via the linked-go/
AquaTemp control endpoint — the exact path already used for Mode / R01 / Power.

``mode = box`` on purpose: a slider would emit one cloud write per drag step and
race over the slow round-trip. A typed box (and automation ``set_value``) is a
single, unambiguous write per change.
"""
import logging

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

LOGGER = logging.getLogger(__name__)

OFFSET_CODE = "compensate_offset"
SLOPE_CODE = "compensate_slope"
# P01 = circulation-pump operation mode (ENUM 0-2): 0 = always-on (continuous
# circulation -> real-time buffer sensing -> VP restarts heating in real-time,
# no stuck-idle), 2 = interval (circulates only every P02 min). Exposed writable
# so a demand-gated automation can set 0 during heat/DHW demand and 2 when idle.
# ONLY P01 is writable (Soeren 2026-09-19); all other P-values stay read-only
# sensors to avoid pressure faults.
P01_CODE = "P01"
# R04/R05 = the heat pump's HEATING hysteresis differentials (Soeren's Winter
# friend). R04 (temp_diff_power_on_heating) is the restart differential: the
# compressor turns on when the water falls to target - R04. R05
# (temp_diff_standby_heating) is the standby differential above target before it
# stops. Widening them lengthens compressor cycles (less short-cycling under low
# load) but risks the cold-house dead-band we fixed on 2026-09-19 by narrowing
# them to 3 -> tune measured, watching the cold-house watchdog. Exposed writable
# on Soeren's direct grant (2026-09-25). NOTE: the SAME code "R05" means
# min/anti-freeze temp on the LinkedGo *radiator* device (see climate.py) — a
# different product; on this heat pump it is the standby-heating differential.
R04_CODE = "R04"
R05_CODE = "R05"

# C-group = compressor-frequency settings (the app's technician-code-66 page).
# ALL are HARD-CLAMPED to 30-90 Hz (Søren 2026-10-04: "30Hz er minimum, 90Hz er
# maksimum. uanset hvad") — the compressor's safe operating band. The device may
# accept wider, but we never expose outside the band; too low/high stresses the
# compressor. The clamp is enforced both via the entity min/max AND in _format,
# so even a programmatic set_value cannot escape it ("uanset hvad").
#
# Deliberately EXCLUDED:
#   C01 "Manual Comp Frequency" — value 0 = manual-mode OFF (auto); a 30-90 clamp
#       would block turning it off. Needs a {0} ∪ 30-90 range — pending Søren.
#   C04 "Model Selection" — an enum (not a frequency); a wrong write reconfigures
#       the unit. Never exposed as a 30-90 number.
#
# (code, friendly name, unique_id suffix)
COMP_FREQ_SPECS = [
    ("C02", "Min Comp Frequency", "c02_min_comp_freq"),
    ("C03", "Max Comp Frequency", "c03_max_comp_freq"),
    ("C05", "Min Comp Freq Cool Low AT", "c05_min_comp_freq_cool_low_at"),
    ("C07", "Resonance Point 1", "c07_resonance_1"),
    ("C08", "Resonance Point 2", "c08_resonance_2"),
    ("C09", "Resonance Point 3", "c09_resonance_3"),
    ("C10", "Min Comp Freq Heat Low AT", "c10_min_comp_freq_heat_low_at"),
    ("C11", "Max Comp Freq Cool High AT", "c11_max_comp_freq_cool_high_at"),
    ("C12", "Max Comp Freq DHW", "c12_max_comp_freq_dhw"),
]
COMP_FREQ_MIN = 30
COMP_FREQ_MAX = 90


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up WarmLink number entities."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    entities = [
        WarmlinkWeatherCompOffsetNumber(coordinator, entry),
        WarmlinkWeatherCompSlopeNumber(coordinator, entry),
        WarmlinkCircPumpModeNumber(coordinator, entry),
        WarmlinkPowerOnDiffHeatingNumber(coordinator, entry),
        WarmlinkStandbyDiffHeatingNumber(coordinator, entry),
    ]
    entities += [
        WarmlinkCompFreqNumber(coordinator, entry, code, name, uid)
        for code, name, uid in COMP_FREQ_SPECS
    ]
    async_add_entities(entities)
    LOGGER.info(
        "WarmLink: Added weather-comp offset + slope + P01 pump-mode + R04/R05 "
        "heating-hysteresis + %d comp-freq (C-group, 30-90 Hz clamp) numbers",
        len(COMP_FREQ_SPECS),
    )


class _WarmlinkBaseNumber(CoordinatorEntity, NumberEntity):
    """Shared plumbing for the weather-comp number entities."""

    _attr_mode = NumberMode.BOX
    _code = None  # protocolCode to read/write; set by subclass

    def __init__(self, coordinator, entry):
        """Initialize the number."""
        super().__init__(coordinator)
        self._entry = entry

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

    @property
    def available(self) -> bool:
        """Available as long as the coordinator has data."""
        return bool(self.coordinator.data) and self.coordinator.last_update_success

    @property
    def native_value(self):
        """Return the current value of this register, or None."""
        v = self._code_value(self._code)
        if v in (None, "", "null"):
            return None
        try:
            return float(v)
        except (TypeError, ValueError):
            return None

    def _format(self, value: float) -> str:
        """Format the outgoing value string (subclass decides int/decimal)."""
        raise NotImplementedError

    async def async_set_native_value(self, value: float) -> None:
        """Write the new value to the device."""
        device_code = None
        if self.coordinator.device_info:
            device_code = self.coordinator.device_info.get("device_code")
        if not device_code:
            LOGGER.error("WarmLink: No device_code available, cannot set %s", self._code)
            return

        out = self._format(value)
        LOGGER.info("WarmLink: Requesting %s=%s (number)", self._code, out)
        resp = await self.coordinator.api.set_value(device_code, self._code, out)
        LOGGER.info("WarmLink: %s=%s response: %s", self._code, out, resp)
        # Optimistically reflect the new value so the UI updates instantly; the
        # next scheduled poll reconciles (and corrects if the device clamps).
        if self.coordinator.data:
            for item in self.coordinator.data:
                if item.get("code") == self._code:
                    item["value"] = out
                    break
            self.coordinator.async_set_updated_data(self.coordinator.data)


class WarmlinkWeatherCompOffsetNumber(_WarmlinkBaseNumber):
    """Writable weather-compensation offset (``compensate_offset``).

    Shifts the whole ambient-compensation curve up/down — the actuator HA uses
    to hold a room-temperature setpoint the unit itself cannot (no room sensor).
    """

    _code = OFFSET_CODE
    _attr_name = "Weather Comp Offset"
    _attr_icon = "mdi:arrow-up-down-bold"
    _attr_native_min_value = 20
    # Max 75 (was 60): the vinter-trim computes off_new up to the water-cap
    # wc = 48 + slope*ambient (~68-74 in mild weather) so the offset must be
    # settable that high; a 60 clamp silently stuck it at 58 -> water starved
    # (Søren 2026-10-06). The ACTUAL water stays <=48 C via the wc cap in the
    # trim, so this only removes the artificial clamp, it does not raise water.
    _attr_native_max_value = 75
    _attr_native_step = 1

    def __init__(self, coordinator, entry):
        """Initialize the offset number."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_weather_comp_offset"

    def _format(self, value: float) -> str:
        """Offset is a whole number; match the device's reported decimal style."""
        n = int(round(value))
        raw = self._code_value(self._code)
        if raw is not None and "." in str(raw):
            return f"{n}.0"
        return str(n)


class WarmlinkWeatherCompSlopeNumber(_WarmlinkBaseNumber):
    """Writable weather-compensation slope (``compensate_slope``).

    The curve gradient (°C water per °C outdoor). Normally set once for the
    building; exposed so it can be tuned (or learned) from data.
    """

    _code = SLOPE_CODE
    _attr_name = "Weather Comp Slope"
    _attr_icon = "mdi:chart-line-variant"
    _attr_native_min_value = 0.1
    _attr_native_max_value = 3.0
    _attr_native_step = 0.1

    def __init__(self, coordinator, entry):
        """Initialize the slope number."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_weather_comp_slope"

    def _format(self, value: float) -> str:
        """Slope is a one-decimal value (e.g. 0.8)."""
        return f"{value:.1f}"


class WarmlinkCircPumpModeNumber(_WarmlinkBaseNumber):
    """Writable circulation-pump operation mode (``P01``, ENUM 0-2).

    The unit's *internal* circulation pump (the one that produces
    ``water_flow_t39`` and lets the unit sense the buffer water). ``0`` runs it
    always-on, so the unit sees the buffer coasting in real time and restarts
    heating without waiting for the next ``P02`` sampling interval; ``2`` runs it
    on that interval only. A demand-gated HA automation writes ``0`` while there
    is heat/DHW demand and ``2`` when idle.

    This is the **only** P-value exposed as writable (Søren 2026-09-19). Every
    other pump/pressure register stays a read-only sensor — a wrong P-value can
    trip the unit on pressure. ``1`` is inside the device's own range but unused
    by our control; the range is kept honest at 0-2 so a fat-fingered write is
    clamped by the unit rather than rejected.
    """

    _code = P01_CODE
    _attr_name = "Circ Pump Operation Mode"
    _attr_icon = "mdi:pump"
    _attr_native_min_value = 0
    _attr_native_max_value = 2
    _attr_native_step = 1

    def __init__(self, coordinator, entry):
        """Initialize the P01 pump-mode number."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_p01_circ_pump_mode"

    def _format(self, value: float) -> str:
        """P01 is a whole-number ENUM; the device reports it plain (no decimal)."""
        return str(int(round(value)))


class _WarmlinkHeatingDiffNumber(_WarmlinkBaseNumber):
    """Shared plumbing for the R04/R05 heating-hysteresis differentials.

    Both are whole-degree differentials the device reports dot-decimal (e.g.
    ``3.0``); the formatter matches that style so the optimistic write and the
    polled read-back agree instead of flapping.
    """

    _attr_icon = "mdi:thermometer-lines"
    # A hysteresis differential; 1-10 °C keeps a fat-fingered write inside the
    # unit's sane range rather than rejected. Tuning lives in the 3-6 band.
    _attr_native_min_value = 1
    _attr_native_max_value = 10
    _attr_native_step = 1

    def _format(self, value: float) -> str:
        """Whole number; match the device's reported decimal style."""
        n = int(round(value))
        raw = self._code_value(self._code)
        if raw is not None and "." in str(raw):
            return f"{n}.0"
        return str(n)


class WarmlinkPowerOnDiffHeatingNumber(_WarmlinkHeatingDiffNumber):
    """Writable restart differential (``R04``, temp_diff_power_on_heating).

    The compressor turns on when the water falls to ``target - R04``. Larger =
    the water coasts further down before a restart = longer off periods, but a
    target raised right after a stop can land below ``target - R04`` and stall
    the restart (the cold-house dead-band of 2026-09-19). Kept at 3 for that
    reason; widen only measured, watching the cold-house watchdog.
    """

    _code = R04_CODE
    _attr_name = "Temp Diff Power-on Heating"

    def __init__(self, coordinator, entry):
        """Initialize the R04 number."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_r04_power_on_diff_heating"


class WarmlinkStandbyDiffHeatingNumber(_WarmlinkHeatingDiffNumber):
    """Writable standby differential (``R05``, temp_diff_standby_heating).

    How far above target the water rises before the compressor stops. Larger =
    the run heats further past target before shutting off = longer on-runs (the
    lever against low-load short-cycling), at the cost of bigger water-temp
    swings.
    """

    _code = R05_CODE
    _attr_name = "Temp Diff Standby Heating"

    def __init__(self, coordinator, entry):
        """Initialize the R05 number."""
        super().__init__(coordinator, entry)
        self._attr_unique_id = f"{entry.entry_id}_r05_standby_diff_heating"


class WarmlinkCompFreqNumber(_WarmlinkBaseNumber):
    """Writable compressor-frequency setpoint (C-group), clamped 30-90 Hz.

    One class parameterised for each C-code in ``COMP_FREQ_SPECS`` (min/max comp
    frequency, the conditional cool/heat/DHW limits, and the three resonance
    points). All share the same hard 30-90 Hz band — Søren's absolute limit for
    the compressor, enforced here regardless of how the value arrives.
    """

    _attr_icon = "mdi:sine-wave"
    _attr_native_min_value = COMP_FREQ_MIN
    _attr_native_max_value = COMP_FREQ_MAX
    _attr_native_step = 1
    _attr_native_unit_of_measurement = "Hz"

    def __init__(self, coordinator, entry, code, name, uid):
        """Initialize a comp-frequency number for one C-code."""
        super().__init__(coordinator, entry)
        self._code = code
        self._attr_name = name
        self._attr_unique_id = f"{entry.entry_id}_{uid}"

    def _format(self, value: float) -> str:
        """Whole-Hz value, HARD-CLAMPED 30-90 (uanset hvad); match decimal style."""
        n = int(round(value))
        n = max(COMP_FREQ_MIN, min(COMP_FREQ_MAX, n))
        raw = self._code_value(self._code)
        if raw is not None and "." in str(raw):
            return f"{n}.0"
        return str(n)
