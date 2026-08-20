# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [76.0] - 2026-08-20

The climate release — a unified climate platform covering both heat pumps and LinkedGo smart radiators, plus cooling, DHW as a water heater, live compressor-based status, and a round of robustness hardening. Heat-pump behaviour is unchanged unless you use the new controls.

### Added
- **Smart radiator support** — LinkedGo/WarmLink panel radiators (e.g. Scantherm) are now first-class devices. They speak an 18-code protocol routed by `productId`; the integration auto-detects them and exposes a radiator climate entity (target temp, current temp, heat levels 1–6, on/off, live `hvac_action`). (#22)
- **Cooling** — heat-pump cooling modes are controllable, gated behind the H05 cooling-function switch so a stray tap can't start cooling on uninsulated pipes. (#22)
- **DHW water heater** — the hot-water tank is exposed as a proper `water_heater` entity. (#22)
- **`hvac_action`** — the thermostat card shows live Heating / Cooling / Idle, driven by the actual compressor frequency (T30) rather than just the selected mode. (#22)
- **Re-authentication flow** — a rejected password now raises a reauth prompt in Home Assistant instead of silently serving stale data. (#22)

### Fixed
- **Mode routing fails closed** — a device that can't be positively identified as a heat pump no longer receives heat-pump-only entities that would write inverted Mode values on a radiator. (#22)
- **DHW preserved on HEAT/COOL** — choosing Heat or Cool on the thermostat card no longer drops the DHW component of the current mode. (#22)
- **One token per account** — multiple config entries on the same account now share a single pooled API client with serialised logins, ending the `-100` token fights. (#22)
- **Radiator optimistic mode** — bounded by a TTL and verified against the control response, so a lost or rejected write can't latch the UI on the wrong register. (#22)

### Thanks
This release was a genuine collective effort — thanks to **@Kristian-KK** (radiator hardware and a thorough robustness review) and **@richard-pm** (live cooling verification and the `hvac_action` contribution).

## [75.0] - 2026-08-17

Packaging release preparing the repository for the HACS default store.

### Added
- **CI validation** — the HACS repository check and Home Assistant `hassfest` manifest validation now run on push, PRs, and on a daily schedule. (#27)

### Fixed
- **`hassfest` compliance** — the internal code→icon map was named `icons.json`, a name HA reserves for its own icon schema; renamed to `code_icons.json` (referenced only by `sensor.py`). Added a `CONFIG_SCHEMA` (config-entry-only) since the integration implements `async_setup`. No user-facing change. (#27)

## [74.0] - 2026-08-17

Documentation and packaging release — no functional changes to the integration.

### Changed
- **COP example** in the README now splits **single-phase** and **three-phase** power (single-phase is the default, power factor ~0.95). The previous version hardcoded the three-phase factor (`× 1.732`), which overstated input power by ~73% and understated COP on single-phase units. Thanks to @j5bart. (#18, #21)
- **Confirmed-compatible devices** — added **WarmFlow Zeno (AS02-R32)** to the README (same LinkedGo cloud platform). (#18, #21)
- **Summer Anti-Thermosiphon** is now surfaced in the feature list, linking to the existing guide. (#23)
- **Ko-fi** moved to a single line under *Contributing* as an optional "non-code way to help". (#24)
- **`manifest.json`** now includes `documentation`, `issue_tracker`, and `iot_class` (`cloud_polling`), with `codeowners` set to `@srbjessen` — HACS default-store compliance. (#25)

## [73.0] - 2026-06-25

### Changed
- **DHW target range now follows the device's own min/max** (registers `R36`/`R37`) instead of a fixed 47–60 °C — read live, so the dropdown matches each unit's configured range (e.g. 15–55 °C on some models) and tracks changes made in the WarmLink app. Selecting a value validates against the live range. Addresses the range feedback in #9. ⚠️ Running the tank low for price/solar optimisation is useful, but a tank sitting ~32–45 °C is where Legionella grows fastest — keep a weekly disinfection cycle to ≥60 °C on if you do (see the release notes).

## [72.0] - 2026-06-25

### Added
- **Reconfigure support** — change the account or device code on an existing install (the WarmLink entry → **Reconfigure**) without removing and re-adding it. The same config entry is updated in place, so all entities, their IDs, and any dashboard/automation references are preserved.

### Fixed
- **Shared / "member" accounts can now be set up** — added an optional **Device code** field to the config flow. WarmLink member accounts receive an empty device list from the cloud, so auto-detection failed and setup never completed; supplying the device code lets the integration address the heat pump directly. Login and device access are validated during setup with clear error messages. Resolves #1.

## [71.0] - 2026-06-24

### Added
- **Writable controls** — the integration can now *set* values, not just read them, via the WarmLink cloud control endpoint:
  - **Power switch** (`switch`) — turn the heat pump on/off.
  - **Operating Mode select** (`select`) — DHW only / Heating / Heating + DHW. Only confirmed-safe modes are exposed, to avoid accidentally selecting a cooling mode.
  - **DHW Target Temperature select** (`select`) — set the hot-water setpoint from Home Assistant as a whole-degree dropdown (47–60 °C). A dropdown is one unambiguous write per change, unlike a stepper/box that sends a cloud write per increment and races over the slow round-trip. Useful as an automation target/trigger. Resolves #9.
- **Anti-thermosiphon guide + example** (`examples/automation_anti_thermosiphon.yaml`) — optional use of the Operating Mode select as a software "check valve" to stop summer DHW tank drain by parking the 3-way diverter off the tank after a reheat. Explains when it applies and why pipe geometry (a vertical primary riser off the top of the tank) can worsen the siphon.

### Changed
- Update interval reduced from 5 minutes to 2 minutes for more responsive data.

## [70.0] - 2025-02-15

### Changed (BREAKING)
- **Entity ID Auto-generation**: Removed manual entity_id setting to comply with Home Assistant best practices
  - 61 sensors with spaces in codes now have auto-generated entity IDs
  - Entity IDs for sensors like "M1 Mode", "Zone 2 Mixing Temp", etc. will change
  - Migration required: Update dashboards and automations to use new entity IDs
  - See migration guide in release notes

### Fixed
- Fixed 79 "invalid entity ID" warnings for sensors with spaces in codes
- Complies with Home Assistant 2027.x+ requirements
- Follows entity.should_not_set_entity_id guideline

### Technical
- Removed `self.entity_id` manual setting in sensor.py
- Uses `code_friendly` in unique_id for consistency
- Lets Home Assistant auto-generate entity_id from name + unique_id

## [69.0] - 2025-02-14

### Fixed
- Fixed blocking I/O warning during startup
- Translation files now loaded asynchronously using executor jobs
- Eliminates "Detected blocking call to open" warnings

### Technical
- Added `_load_sensor_translations_sync()` synchronous helper function
- Added `async_load_sensor_translations()` async wrapper
- Updated `async_setup_entry()` to await translation loading
- Uses `hass.async_add_executor_job()` pattern for file operations
- Improved startup performance (~50ms faster)

## [68.0] - 2025-02-03

### Added
- **41 new fault code sensors** including critical E035 (High Pressure Switch Protection)
- Full fault code support: E001-E045, Fault2-Fault8
- Danish and English translations for all fault codes
- Alert icons (mdi:alert-circle) for all fault codes

### Fault Codes Added
**High/Low Pressure:**
- E001: High Pressure Protection
- E002: Low Pressure Protection
- E035: High Pressure Switch Protection ⭐
- E036: Low Pressure Switch Protection

**Compressor:**
- E003: Compressor Overload
- E025: Compressor Current Sensor Error
- E028: Compressor Running Time Exceeded
- E040: Compressor Phase Current Unbalance
- E043: Compressor Stall

**Temperature:**
- E005: Outdoor Temperature Sensor Error
- E006: Indoor Temperature Sensor Error
- E015: Water Temperature Too High
- E016: Water Temperature Too Low
- E020: Discharge Temperature Sensor Error
- E021: Discharge Temperature Too High
- E022: Suction Temperature Sensor Error
- E023: Outdoor Coil Temperature Sensor Error
- E024: Indoor Coil Temperature Sensor Error
- E029: Antifreeze Protection
- E031: Exhaust Superheat Too High
- E032: Suction Superheat Too Low

**Flow/Pump:**
- E004: Water Flow Switch Error
- E030: Water Pump Alarm

**Electrical:**
- E012: Phase Sequence/Phase Loss
- E026: High Voltage Protection
- E027: Low Voltage Protection
- E041: DC Bus Voltage Too High
- E042: DC Bus Voltage Too Low

**Communication:**
- E011: Communication Error
- E038: Inverter Communication Error

**Inverter/Driver:**
- E033: EEV Driver Error
- E037: Inverter Module Protection
- E039: PFC Module Protection
- E044: Inverter IPM Protection
- E045: Inverter Overheating Protection

**Other:**
- E034: Oil Return Protection
- Fault2, Fault3, Fault4, Fault7, Fault8

### Technical
- Total sensors: 391 (350 → 391)
- Updated codes.json with all fault codes
- Added comprehensive translations in sensor_da.json and sensor_en.json
- Added fault code icons in icons.json

## [67.0] - 2025-02-01

### Added
- Manual refresh button entity
- Allows on-demand data refresh without reload integration
- Completes in 3-5 seconds
- Uses same intelligent caching as automatic updates

### Features
- Button entity: `button.warmlink_refresh_data`
- Can be used in dashboards and automations
- Calls `coordinator.async_request_refresh()` directly

### Technical
- New button.py platform created
- Added "button" to PLATFORMS in __init__.py
- Full coordinator integration

## [66.0] - 2025-02-01

### Fixed
- **Critical**: Eliminated data gaps during updates
- Sensors now remain available during entire update cycle
- Perfect continuous graphs without holes

### Technical
- Improved `available` property: Always returns True if cache exists
- Enhanced `native_value` property: Retains cache if API returns empty/null
- Added `_handle_coordinator_update()` override with callback decorator
- Intelligent caching prevents unavailable states

## [65.0] - 2025-01-31

### Fixed
- ValueError crashes when API returns empty strings for numeric sensors
- 250+ occurrences eliminated

### Technical
- Converts empty strings ('', 'null') to None in native_value property
- Home Assistant gracefully accepts None for sensors with units
- Prevents crashes from malformed API responses

## [64.0] - 2025-01-30

### Fixed
- Auto-update not triggering every 5 minutes
- Added explicit logging for coordinator initialization
- Added logging at each update cycle start

### Technical
- Enhanced logging in coordinator initialization
- Improved setup flow in __init__.py
- Better debugging capabilities

## [63.0] - 2025-01-24

### Added
- Initial public release on GitHub
- 350 sensors for WarmLink/Zealux heat pumps
- Danish and English language support
- Automatic updates every 5 minutes
- Comprehensive sensor coverage: T-sensors, P-parameters, F-functions, M-timers, W-schedules

### Features
- Temperature sensors (T01-T39)
- Pressure sensors (P01-P20)
- Function parameters (F01-F14)
- Timer settings (M1-M4)
- Schedule settings (W1-W5)
- Smart Grid parameters (SG01-SG20)
- Device information
- Operational modes

### Technical
- DataUpdateCoordinator for efficient updates
- Intelligent sensor mapping
- Unit and device class auto-detection
- Icon assignment
- State class handling
- Custom friendly names with codes

---

## Migration Guides

### v70 Migration (BREAKING CHANGE)

**Affected Sensors:** 61 sensors with spaces in codes

**Before v70:**
```
sensor.warmlink_m1_mode_m1 mode
sensor.warmlink_zone_2_mixing_temp_zone 2 mixing temp
```

**After v70:**
```
sensor.m1_mode_m1_mode
sensor.zone_2_mixing_temp_zone_2_mixing_temp
```

**Steps:**
1. Backup dashboards and automations
2. Install v70
3. Restart Home Assistant
4. Find new entity IDs in Developer Tools → States
5. Update all references in dashboards/automations
6. Reload automations

**Unaffected:** Sensors like T01-T39, P01-P20 remain unchanged.

---

## Upgrade Path

- **v63 → v70**: File replacement + restart (follow v70 migration guide)
- **v64 → v70**: File replacement + restart (follow v70 migration guide)
- **v65 → v70**: File replacement + restart (follow v70 migration guide)
- **v66 → v70**: File replacement + restart (follow v70 migration guide)
- **v67 → v70**: File replacement + restart (follow v70 migration guide)
- **v68 → v70**: File replacement + restart (follow v70 migration guide)
- **v69 → v70**: File replacement + restart (follow v70 migration guide)

All upgrades v63-v69 → v70 are smooth file replacements, but v70 requires entity ID migration.

---

## Notes

- **v70**: Breaking change - plan migration time (30-120 minutes depending on setup size)
- **v69**: Performance improvement - recommended upgrade
- **v68**: Essential for fault code monitoring
- **v67**: Useful for manual refresh capability
- **v66**: Critical for continuous graphs
- **v65**: Essential for stability
- **v64**: Recommended for proper logging

---

**Current Version:** 70.0
**Total Sensors:** 391
**Supported Languages:** Danish (da), English (en)
**Update Interval:** 300 seconds (5 minutes)
