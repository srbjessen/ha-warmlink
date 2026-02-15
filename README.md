# WarmLink Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)
[![GitHub release](https://img.shields.io/github/release/srbjessen/ha-warmlink.svg)](https://github.com/srbjessen/ha-warmlink/releases)
[![License](https://img.shields.io/github/license/srbjessen/ha-warmlink.svg)](LICENSE)

Home Assistant integration for WarmLink/Zealux heat pumps.

Monitor and control your WarmLink/Zealux heat pump directly from Home Assistant with comprehensive sensor coverage, fault code monitoring, and real-time updates.

---

## Features

✅ **391 Sensors** - Complete monitoring of your heat pump
✅ **Fault Code Detection** - 41 fault codes including critical E035
✅ **Real-time Updates** - Automatic updates every 5 minutes
✅ **Manual Refresh** - On-demand data refresh button
✅ **Multi-language** - Danish and English support
✅ **No Data Gaps** - Intelligent caching for continuous graphs
✅ **Async Operations** - Non-blocking file I/O for performance

---

## Sensors

### Temperature Sensors (T01-T39)
- Water inlet/outlet temperatures
- Ambient temperature
- Coil temperatures
- Discharge/suction temperatures
- DHW temperatures
- Zone temperatures

### Pressure & Flow (P01-P20)
- System pressures
- Water flow rate
- Pump speeds

### Function Parameters (F01-F14)
- Fan speeds
- Heating curves
- Temperature targets
- Operating modes

### Timers (M1-M4)
- Mode settings
- Start/end times
- Temperature targets
- Power limits

### Schedules (W1-W5)
- Weekly schedules
- Time slots
- Mode configurations

### Fault Codes (E001-E045)
- Pressure protection (E001, E002, E035, E036)
- Compressor errors (E003, E025, E028, E040, E043)
- Temperature sensors (E005, E006, E015, E016, E020-E024, E029, E031, E032)
- Flow/Pump alarms (E004, E030)
- Electrical protection (E012, E026, E027, E041, E042)
- Communication errors (E011, E038)
- Inverter/Driver errors (E033, E037, E039, E044, E045)

### Smart Grid (SG01-SG20)
- Smart grid parameters
- Energy management

### Device Information
- Software versions
- Hardware information
- Operating hours
- System status

---

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the three dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/srbjessen/ha-warmlink`
5. Category: `Integration`
6. Click "Add"
7. Click "Install" on the WarmLink integration
8. Restart Home Assistant

### Manual Installation

1. Download the latest release from [Releases](https://github.com/srbjessen/ha-warmlink/releases)
2. Extract the files
3. Copy the `custom_components/warmlink` folder to your Home Assistant `config/custom_components/` directory
4. Restart Home Assistant

---

## Configuration

### Add Integration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for **WarmLink**
4. Enter your WarmLink credentials:
   - **Email**: Your WarmLink account email
   - **Password**: Your WarmLink account password
   - **Language**: `da` (Danish) or `en` (English)
5. Click **Submit**

### Entities

After setup, 391 sensors will be created automatically:

```
sensor.warmlink_water_inlet_temp_t01
sensor.warmlink_water_outlet_temp_t02
sensor.warmlink_ambient_temp_t04
sensor.warmlink_mode_state_modestate
sensor.warmlink_high_pressure_switch_protection_e035
button.warmlink_refresh_data
...and 385 more!
```

---

## Usage Examples

### Dashboard Card - Temperature Monitoring

```yaml
type: entities
title: Varmepumpe Temperaturer
entities:
  - entity: sensor.warmlink_water_inlet_temp_t01
    name: Indløb
  - entity: sensor.warmlink_water_outlet_temp_t02
    name: Udløb
  - entity: sensor.warmlink_ambient_temp_t04
    name: Udetemperatur
```

### Manual Refresh Button

```yaml
type: button
entity: button.warmlink_refresh_data
name: Opdater Nu
icon: mdi:refresh
tap_action:
  action: call-service
  service: button.press
  target:
    entity_id: button.warmlink_refresh_data
```

### Fault Code Monitoring

```yaml
automation:
  - alias: "Alarm Ved E035 Fejl"
    trigger:
      - platform: state
        entity_id: sensor.warmlink_high_pressure_switch_protection_e035
        to: '1'
    action:
      - service: notify.mobile_app
        data:
          title: "⚠️ Varmepumpe Alarm!"
          message: "E035 Højtrykskontakt beskyttelse aktiveret!"
          data:
            priority: high
```

### COP Calculation

```yaml
template:
  - sensor:
      - name: "Varmepumpe COP"
        unique_id: warmlink_cop
        unit_of_measurement: ""
        state_class: measurement
        device_class: power_factor
        state: >
          {% set voltage = states('sensor.warmlink_ac_input_voltage_t34') | float(0) %}
          {% set current = states('sensor.warmlink_ac_input_current_t35') | float(0) %}
          {% set power = (voltage * current * 1.732 / 1000) %}
          {% set delta_t = states('sensor.varmepumpe_delta_t') | float(0) %}
          {% set flow = states('sensor.warmlink_water_flow_t39') | float(0) %}
          {% if power > 0 and delta_t > 0 %}
            {{ ((delta_t * flow * 1.163) / power) | round(2) }}
          {% else %}
            0
          {% endif %}
```

---

## Known Limitations

### Single Session Limitation

**⚠️ The WarmLink API only allows ONE active session per account at a time.**

**Problem:**
- If you use the WarmLink mobile app AND Home Assistant with the same account, one will be logged out
- Guest accounts (invited users) can see devices in the app but **API returns no devices**

**Solutions:**

**Option 1: Dedicated Home Assistant Account (Recommended)**

If you want to use BOTH the mobile app and Home Assistant:

1. **Create a second WarmLink account** (Account B)
2. **Keep your primary account** (Account A) as owner
3. **Invite Account B** to your home (from Account A in the app)
4. **Use Account A credentials** in Home Assistant integration
5. **Use Account B** to log into the mobile app

**Result:**
- ✅ Home Assistant works with Account A
- ✅ Mobile app works with Account B  
- ✅ Both can monitor the heat pump
- ✅ No session conflicts

**Option 2: Home Assistant Only**

If you don't need the mobile app:

1. **Use your primary account** in Home Assistant
2. **Log out** of the mobile app (or don't install it)
3. **Single session** - no conflicts

**Option 3: Mobile App Only**

If you prefer the mobile app and don't need Home Assistant integration, just use the app.

**Technical Details:**
- The WarmLink API uses session-based authentication
- Each login invalidates the previous session
- Guest accounts have limited API access (view-only in app, no API device list)
- This is a WarmLink API limitation, not an integration issue

---

## Troubleshooting

### Integration Not Loading

1. Check logs: **Settings** → **System** → **Logs**
2. Search for "warmlink"
3. Common issues:
   - Wrong credentials
   - Network connectivity
   - API changes

### Sensors Showing "Unavailable"

1. Press the refresh button: `button.warmlink_refresh_data`
2. Check coordinator is updating (logs should show "Starting scheduled update")
3. Verify API credentials are correct

### Entity ID Changes (v70 Migration)

If you upgraded to v70, entity IDs for 61 sensors changed. See [CHANGELOG.md](CHANGELOG.md) for migration guide.

### "No Devices Returned from API" Error

**Error Message:**
```
Failed setup, will retry: No devices returned from API
```

**Causes:**

1. **Using a guest/invited account** - Guest accounts cannot access devices via API
   - **Solution:** Use the owner account credentials in Home Assistant
   
2. **Session conflict** - Another session (mobile app) is active
   - **Solution:** Use dedicated accounts (see [Known Limitations](#known-limitations))
   
3. **Account has no devices** - No heat pump associated with account
   - **Solution:** Verify the account owns or has been invited to a home with a heat pump

4. **API connection issues**
   - **Solution:** Check network connectivity and credentials

**Quick Fix:**
- Use the **owner account** (the account that created the home)
- Log out of the mobile app before configuring Home Assistant
- After HA setup, create a second account for the mobile app

---

## Development

### Project Structure

```
custom_components/warmlink/
├── __init__.py           # Integration setup
├── sensor.py             # Sensor platform
├── button.py             # Button platform (refresh)
├── coordinator.py        # DataUpdateCoordinator
├── config_flow.py        # Configuration flow
├── manifest.json         # Integration metadata
├── const.py              # Constants
├── codes.json            # Sensor code list
├── icons.json            # Icon mappings
├── units.json            # Unit mappings
├── common/
│   └── endpoints.py      # API endpoints
├── managers/
│   └── warmlink_api.py   # API client
└── translations/
    ├── da.json           # Danish config translations
    ├── en.json           # English config translations
    ├── sensor_da.json    # Danish sensor names
    └── sensor_en.json    # English sensor names
```

### Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

---

## Credits

- **Original API Reverse Engineering**: [zyznos321/warmlink](https://github.com/zyznos321/warmlink)
- **Home Assistant Integration**: [srbjessen](https://github.com/srbjessen)

---

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## Changelog

See [CHANGELOG.md](CHANGELOG.md) for version history and migration guides.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/srbjessen/ha-warmlink/issues)
- **Discussions**: [GitHub Discussions](https://github.com/srbjessen/ha-warmlink/discussions)

---

## Disclaimer

This integration is not officially affiliated with or endorsed by WarmLink or Zealux. Use at your own risk.

---

**Current Version:** 70.0  
**Total Sensors:** 391  
**Supported Languages:** Danish, English  
**Update Interval:** 5 minutes
