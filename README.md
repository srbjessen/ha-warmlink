# WarmLink Heat Pump Integration for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)
[![GitHub release](https://img.shields.io/github/release/srbjessen/ha-warmlink.svg)](https://github.com/srbjessen/ha-warmlink/releases)
[![License](https://img.shields.io/github/license/srbjessen/ha-warmlink.svg)](LICENSE)

A comprehensive Home Assistant integration for Chinese R290 inverter heat pumps using the WarmLink/Linked-Go control platform.

<img src="docs/images/warmlink_logo.png" alt="WarmLink Logo" width="200"/>

## Supported Brands

This integration works with heat pumps from multiple Chinese OEM manufacturers using the WarmLink/Linked-Go platform:

- **Zealux**
- **Alsavo**
- **Aquatemp**
- **Fairland**
- **Nor-R290** (and variants)

All these brands share nearly identical control systems, making this integration broadly compatible.

## Features

✨ **350+ Sensor Codes** - Comprehensive monitoring of your heat pump
- Temperature sensors (inlet, outlet, ambient, DHW, etc.)
- Compressor parameters (frequency, current, voltage, power)
- EEV valve positions and control
- Operating modes and status
- Timer and schedule settings
- Smart Grid integration parameters
- Relay and output status
- Fault codes and diagnostics

🌍 **Multi-Language Support**
- English (en)
- Danish (da)
- Easy to add more languages

🔄 **Reliable Operation**
- Automatic token refresh
- Intelligent error handling
- Value caching prevents "unavailable" states
- Robust API communication with retry logic

📊 **Rich Data**
- All sensors include proper units (°C, V, A, W, Hz, bar, %, etc.)
- Device classes for proper Home Assistant integration
- State classes for long-term statistics
- Icons for each sensor type

🎨 **Professional UI**
- Custom icons for different sensor types
- Organized by category (Temperature, Compressor, EEV, etc.)
- Clean device info with model and serial number

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Click the 3 dots in the top right corner
3. Select "Custom repositories"
4. Add this repository URL: `https://github.com/srbjessen/ha-warmlink`
5. Select category "Integration"
6. Click "Add"
7. Search for "WarmLink" in HACS
8. Click "Download"
9. Restart Home Assistant

### Manual Installation

1. Download the latest release from [Releases](https://github.com/srbjessen/ha-warmlink/releases)
2. Extract the `warmlink` folder to your `config/custom_components/` directory
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "WarmLink"
4. Enter your WarmLink app credentials:
   - **Username**: Your WarmLink/Linked-Go app email or phone
   - **Password**: Your app password
   - **Language**: Choose English or Danish

## Usage

### Dashboard Examples

See [examples/](examples/) folder for:
- ApexCharts temperature differential graphs
- Operating mode visualizations
- Energy monitoring dashboards

### Template Sensors

Example template sensors for enhanced functionality:

```yaml
template:
  - sensor:
      - name: "Heat Pump Delta T"
        unit_of_measurement: "°C"
        state_class: measurement
        device_class: temperature
        state: >
          {% set inlet = states('sensor.warmlink_water_inlet_temp_t01') | float(0) %}
          {% set outlet = states('sensor.warmlink_water_outlet_temp_t02') | float(0) %}
          {{ (outlet - inlet) | round(1) }}
```

### Operating Mode Translation

```yaml
template:
  - sensor:
      - name: "Heat Pump Operating Mode"
        state: >
          {% set status = states('sensor.warmlink_mode_state_modestate') | int %}
          {% if status == 0 %}Cooling
          {% elif status == 1 %}Heating
          {% elif status == 2 %}Defrost
          {% elif status == 3 %}Unknown
          {% elif status == 4 %}DHW
          {% else %}Off
          {% endif %}
```

## Documentation

- [Installation Guide](docs/installation.md)
- [Configuration Options](docs/configuration.md)
- [Sensor Reference](docs/sensors.md)
- [Troubleshooting](docs/troubleshooting.md)
- [Dashboard Examples](docs/dashboard_examples.md)

## Troubleshooting

### Integration not updating

1. Check your internet connection
2. Verify credentials in the WarmLink app
3. Check Home Assistant logs: **Settings** → **System** → **Logs**

### Sensors showing "Unavailable"

This integration uses value caching to prevent temporary unavailable states. If sensors remain unavailable:

1. Restart the integration: **Settings** → **Devices & Services** → WarmLink → **⋮** → **Reload**
2. Check logs for errors
3. Verify API connectivity

### Update from older versions

**v60+ requires complete reinstallation:**
1. Delete the integration
2. Restart Home Assistant
3. Re-add the integration

See [CHANGELOG.md](CHANGELOG.md) for version-specific notes.

## Contributing

Contributions are welcome! Please read [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

### Adding New Sensor Codes

1. Fork this repository
2. Add codes to `custom_components/warmlink/codes.json`
3. Add translations to `translations/sensor_en.json` and `translations/sensor_da.json`
4. Add units to `units.json` (if applicable)
5. Add icons to `icons.json` (if applicable)
6. Submit a pull request

## Credits

This integration builds upon and greatly expands the foundational work done by the original WarmLink integration developers. We are grateful for their pioneering efforts in reverse engineering the WarmLink/Linked-Go API.

**Original Integration:**
- [zyznos321/warmlink](https://github.com/zyznos321/warmlink) - Initial API reverse engineering and basic sensor support
- Foundation for communication with WarmLink platform
- Community-driven research into Chinese heat pump protocols

**This Version's Enhancements:**
- Expanded from 207 to 350+ sensor codes
- Added multi-language support (English + Danish)
- Implemented value caching to prevent "unavailable" states
- Enhanced error handling and reliability
- Comprehensive documentation and examples
- Professional branding and UI improvements
- Full HACS integration support

Special thanks to:
- Original WarmLink integration developers and contributors
- The Home Assistant community
- All testers and early adopters
- Everyone who contributed sensor codes and translations

**Standing on the shoulders of giants** - This project demonstrates the power of open source collaboration!

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Disclaimer

This is an unofficial integration and is not affiliated with, endorsed by, or connected to WarmLink, Linked-Go, or any heat pump manufacturers. Use at your own risk.

## Support

- 🐛 [Report bugs](https://github.com/srbjessen/ha-warmlink/issues)
- 💡 [Request features](https://github.com/srbjessen/ha-warmlink/issues)
- 💬 [Discussions](https://github.com/srbjessen/ha-warmlink/discussions)

## Star History

If you find this integration useful, please consider giving it a ⭐ on GitHub!

---

Made with ❤️ for the Home Assistant community
