
from .const import DOMAIN
from .coordinator import WarmlinkCoordinator
from homeassistant.helpers import config_validation as cv
import logging

LOGGER = logging.getLogger(__name__)

# Configured via config entries (UI) only, not via YAML.
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

PLATFORMS = ["sensor", "button", "switch", "select", "water_heater", "climate"]

async def async_setup(hass, config):
    """Set up the WarmLink component."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass, entry):
    """Set up WarmLink from a config entry."""
    coord = WarmlinkCoordinator(hass, entry)
    
    # Perform first refresh to get initial data
    await coord.async_config_entry_first_refresh()
    
    # Store coordinator
    hass.data[DOMAIN][entry.entry_id] = coord
    
    # Forward setup to platforms (this will create sensors)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    
    # Add update listener for config changes
    entry.async_on_unload(entry.add_update_listener(update_listener))
    
    LOGGER.info(f"WarmLink: Integration setup complete. Update interval: {coord.update_interval}")
    
    return True

async def update_listener(hass, entry):
    """Handle config entry update."""
    await hass.config_entries.async_reload(entry.entry_id)

async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        # Release the shared API client from the pool when no other loaded entry
        # uses the same account. Otherwise a reconfigure that changes the password
        # (same username) would reuse the pooled client — and its stale token —
        # until the next full HA restart.
        username = entry.data.get("username")
        pool = hass.data.get(DOMAIN, {}).get("_api_pool", {})
        if username in pool:
            others = [
                e for e in hass.config_entries.async_entries(DOMAIN)
                if e.entry_id != entry.entry_id and e.data.get("username") == username
            ]
            if not others:
                pool.pop(username, None)
                LOGGER.debug("WarmLink: Released pooled API client for account %s", username)
    return unload_ok

