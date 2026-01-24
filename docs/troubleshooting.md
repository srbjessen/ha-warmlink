# Troubleshooting Guide

Common issues and solutions for WarmLink integration.

## Integration Not Showing Up

**Problem**: Can't find WarmLink in integration list

**Solutions**:
1. Verify files in `config/custom_components/warmlink/`
2. Check `manifest.json` is valid JSON
3. Restart Home Assistant
4. Clear browser cache (Ctrl+Shift+Delete)
5. Check logs: Settings → System → Logs

## Login Failures

**Problem**: "Invalid credentials" or "Login failed"

**Solutions**:
1. Test credentials in WarmLink mobile app
2. Check for typos in username/password
3. Try logging out and back in to app
4. Verify account is active
5. Check internet connection

## Sensors Always Unavailable

**Problem**: All sensors show "unavailable"

**Solutions**:
1. Wait 5 minutes after adding integration
2. Check internet connection
3. Verify heat pump is online in app
4. Reload integration: Settings → Devices & Services → WarmLink → ⋮ → Reload
5. Check logs for API errors
6. Try restarting Home Assistant

## Some Sensors Missing

**Problem**: Expected sensors don't appear

**Solutions**:
1. Not all codes available on all models
2. Wait for next update cycle (5 minutes)
3. Check if sensors work in WarmLink app
4. Some sensors only appear in specific modes

## Sensors Briefly Unavailable

**Problem**: Sensors show "unavailable" for 1-2 seconds

This is normal in older versions (pre-v60). Upgrade to v60+ which has value caching.

## Update Issues

**Problem**: Can't update integration

**Solutions**:
1. For v60+: Delete integration, restart, re-add
2. Check HACS for update
3. Try manual installation
4. Check [CHANGELOG](../CHANGELOG.md) for version notes

## API Errors

**Problem**: Logs show API connection errors

**Solutions**:
1. Check internet connection
2. Verify WarmLink service is online
3. Check firewall settings
4. Try reloading integration
5. Wait 10 minutes and try again

## Debug Logging

Enable detailed logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.warmlink: debug
```

Restart Home Assistant and check: Settings → System → Logs

## Common Error Messages

### "Token refresh failed"
- Temporary API issue
- Wait 5 minutes and reload integration

### "Device not found"
- Check device is online in app
- Verify account has access

### "Update failed"
- Network timeout
- Integration will retry automatically

## Still Need Help?

1. Check [Installation Guide](installation.md)
2. Search [GitHub Issues](https://github.com/srbjessen/ha-warmlink/issues)
3. Ask in [Discussions](https://github.com/srbjessen/ha-warmlink/discussions)
4. Open new issue with logs

When reporting issues, include:
- Home Assistant version
- Integration version
- Heat pump model
- Relevant logs (remove sensitive data)
