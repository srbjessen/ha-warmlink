
from .const import DOMAIN
from .coordinator import WarmlinkCoordinator
import logging

LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "button"]

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
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok

