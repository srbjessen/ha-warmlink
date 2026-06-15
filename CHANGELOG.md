# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

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
