
import json, os, re, logging

LOGGER = logging.getLogger(__name__)

_TRANSLATIONS_PATH = os.path.join(os.path.dirname(__file__), "translations")
_UNITS_PATH = os.path.join(os.path.dirname(__file__), "units.json")
_ICONS_PATH = os.path.join(os.path.dirname(__file__), "icons.json")

# Track codes we've already logged warnings for (to avoid spam)
_logged_missing_translations = set()
_logged_missing_units = set()
_logged_missing_icons = set()

def load_sensor_translations(language):
    """Load sensor translations for specified language."""
    path = os.path.join(_TRANSLATIONS_PATH, f"sensor_{language}.json")
    try:
        with open(path) as f:
            data = json.load(f)
            LOGGER.info(f"WarmLink: Loaded {len(data)} translations for language '{language}'")
            return data
    except Exception as e:
        LOGGER.warning(f"WarmLink: Failed to load translations for '{language}': {e}")
        # Fallback to English
        try:
            with open(os.path.join(_TRANSLATIONS_PATH, "sensor_en.json")) as f:
                data = json.load(f)
                LOGGER.info(f"WarmLink: Fallback to English - loaded {len(data)} translations")
                return data
        except Exception as e2:
            LOGGER.error(f"WarmLink: Failed to load English fallback translations: {e2}")
            return {}

try:
    with open(_UNITS_PATH) as f:
        _UNITS = json.load(f)
    LOGGER.info(f"WarmLink: Loaded {len(_UNITS)} unit mappings")
except Exception as e:
    _UNITS = {}
    LOGGER.error(f"WarmLink: Failed to load units.json: {e}")

try:
    with open(_ICONS_PATH) as f:
        _ICONS = json.load(f)
    LOGGER.info(f"WarmLink: Loaded {len(_ICONS)} icon mappings")
except Exception as e:
    _ICONS = {}
    LOGGER.error(f"WarmLink: Failed to load icons.json: {e}")

def make_entity_id_friendly(text):
    """Convert text to entity_id friendly format."""
    text = text.lower()
    text = re.sub(r'[\s\-]+', '_', text)
    text = re.sub(r'[^a-z0-9_]', '', text)
    text = re.sub(r'_+', '_', text)
    return text.strip('_')

from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from .const import DOMAIN

# Map units to device classes
UNIT_TO_DEVICE_CLASS = {
    "°C": SensorDeviceClass.TEMPERATURE,
    "V": SensorDeviceClass.VOLTAGE,
    "A": SensorDeviceClass.CURRENT,
    "W": SensorDeviceClass.POWER,
    "kW": SensorDeviceClass.POWER,
    "kWh": SensorDeviceClass.ENERGY,
    "Hz": SensorDeviceClass.FREQUENCY,
    "bar": SensorDeviceClass.PRESSURE,
    "%": SensorDeviceClass.POWER_FACTOR,
}

async def async_setup_entry(hass, entry, async_add_entities):
    coord = hass.data[DOMAIN][entry.entry_id]
    
    # Get language from config, default to English
    language = entry.data.get("language", "en")
    translations = load_sensor_translations(language)
    
    entities = []
    codes_without_translation = []
    codes_without_unit = []
    codes_without_icon = []
    
    for item in coord.data:
        code = item["code"]
        
        # Track missing mappings
        if code not in translations and code not in _logged_missing_translations:
            codes_without_translation.append(code)
            _logged_missing_translations.add(code)
        
        if code not in _UNITS and code not in _logged_missing_units:
            codes_without_unit.append(code)
            _logged_missing_units.add(code)
            
        if code not in _ICONS and code not in _logged_missing_icons:
            codes_without_icon.append(code)
            _logged_missing_icons.add(code)
        
        entities.append(WarmlinkSensor(coord, code, entry, translations))
    
    # Log summary of missing mappings
    if codes_without_translation:
        LOGGER.info(f"WarmLink: Codes without translation ({len(codes_without_translation)}): {codes_without_translation}")
    if codes_without_unit:
        LOGGER.debug(f"WarmLink: Codes without unit mapping ({len(codes_without_unit)}): {codes_without_unit}")
    if codes_without_icon:
        LOGGER.debug(f"WarmLink: Codes without icon mapping ({len(codes_without_icon)}): {codes_without_icon}")
    
    LOGGER.info(f"WarmLink: Created {len(entities)} sensor entities")
    async_add_entities(entities, True)

class WarmlinkSensor(CoordinatorEntity, SensorEntity):
    """Representation of a WarmLink sensor."""
    
    def __init__(self, coord, code, entry, translations):
        """Initialize the sensor."""
        super().__init__(coord)
        self.code = code
        self._entry = entry
        self._cached_value = None  # Cache last known value
        self._cached_attrs = {"code": self.code}  # Cache last known attributes
        
        # Get description from translations (fallback to code itself)
        desc = translations.get(code, code)
        desc_friendly = make_entity_id_friendly(desc)
        
        # Get unit and icon from mappings
        unit = _UNITS.get(code)
        icon = _ICONS.get(code)
        
        # Set attributes
        self._attr_unique_id = f"{entry.entry_id}_{self.code}"
        self._attr_name = f"{desc} [{self.code}]"
        self.entity_id = f"sensor.warmlink_{desc_friendly}_{self.code.lower()}"
        
        # Set icon (default to help-circle for unmapped codes)
        self._attr_icon = icon if icon else "mdi:help-circle-outline"
        
        # Set unit of measurement
        if unit:
            self._attr_native_unit_of_measurement = unit
            # Set device class if applicable
            if unit in UNIT_TO_DEVICE_CLASS:
                self._attr_device_class = UNIT_TO_DEVICE_CLASS[unit]
            # Set state class for numeric values
            if unit in ["°C", "V", "A", "W", "kW", "Hz", "bar", "%", "m³/h", "rpm"]:
                self._attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def device_info(self) -> DeviceInfo:
        """Return device info."""
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
    
    @property
    def available(self) -> bool:
        """Return if entity is available."""
        # Always available if we have a cached value
        # This prevents unavailable states during updates
        return self._cached_value is not None or self.coordinator.last_update_success
    
    @property
    def native_value(self):
        """Return the state of the sensor."""
        if self.coordinator.data:
            for i in self.coordinator.data:
                if i["code"] == self.code:
                    value = i.get("value")
                    if value is not None:
                        self._cached_value = value  # Update cache
                    return value
        # Return cached value if no new data
        return self._cached_value
    
    @property
    def extra_state_attributes(self):
        """Return extra state attributes."""
        if self.coordinator.data:
            for i in self.coordinator.data:
                if i["code"] == self.code:
                    attrs = {"code": self.code}
                    # Add range info if available
                    if i.get("rangeStart"):
                        attrs["range_min"] = i.get("rangeStart")
                    if i.get("rangeEnd"):
                        attrs["range_max"] = i.get("rangeEnd")
                    self._cached_attrs = attrs  # Update cache
                    return attrs
        # Return cached attributes if no new data
        return self._cached_attrs
