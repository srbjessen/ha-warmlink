# Installation Guide

Complete guide to installing the WarmLink Heat Pump integration.

## Prerequisites

- Home Assistant 2024.1.0 or later
- WarmLink/Linked-Go compatible heat pump
- App credentials (email/phone + password)
- Internet connection

## Method 1: HACS (Recommended)

### Install HACS
If you don't have HACS: https://hacs.xyz/docs/setup/download

### Add WarmLink Repository
1. Open HACS in Home Assistant
2. Click **⋮** (three dots) → **Custom repositories**
3. Add: `https://github.com/srbjessen/ha-warmlink`
4. Category: **Integration**
5. Click **Add**

### Install Integration
1. Search for "**WarmLink**" in HACS
2. Click **Download**
3. Wait for completion
4. **Restart Home Assistant**

## Method 2: Manual Installation

1. Download [latest release](https://github.com/srbjessen/ha-warmlink/releases)
2. Extract `warmlink` folder to `config/custom_components/`
3. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services**
2. Click **+ Add Integration**
3. Search for "**WarmLink**"
4. Enter credentials:
   - **Username**: App email or phone number
   - **Password**: App password
   - **Language**: English or Danish
5. Click **Submit**

## Verification

### Check Device
Settings → Devices & Services → WarmLink

You should see your heat pump device with 200-350 sensors.

## Troubleshooting

### Integration Not Found
1. Verify files in `config/custom_components/warmlink/`
2. Check `manifest.json` exists
3. Restart Home Assistant again
4. Check logs for errors

### Login Failed
1. Verify credentials in WarmLink app
2. Check for typos
3. Ensure account is active
4. Check internet connection

### No Sensors
1. Wait 5 minutes for first update
2. Reload integration
3. Check logs for API errors

### Sensors "Unavailable"
1. Check internet connection
2. Verify heat pump is online
3. Check logs
4. Reload integration

## Enable Debug Logging

Edit `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.warmlink: debug
```

Restart and check: Settings → System → Logs

## Updating

### Via HACS
1. HACS will notify of updates
2. Click **Update**
3. Restart Home Assistant

### Manual
1. Download new release
2. Replace files in `custom_components/warmlink/`
3. Restart Home Assistant

**Note**: Some updates require reinstallation. Check [CHANGELOG.md](../CHANGELOG.md).

## Next Steps

- [Dashboard Examples](dashboard_examples.md)
- [Troubleshooting](troubleshooting.md)
- [Configuration](configuration.md)

## Support

- 📖 [Documentation](https://github.com/srbjessen/ha-warmlink)
- 💬 [Discussions](https://github.com/srbjessen/ha-warmlink/discussions)
- 🐛 [Issues](https://github.com/srbjessen/ha-warmlink/issues)
