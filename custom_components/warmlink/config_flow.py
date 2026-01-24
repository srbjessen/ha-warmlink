
from homeassistant import config_entries
import voluptuous as vol

LANGUAGES = {
    "en": "English",
    "da": "Dansk"
}

class WarmlinkConfigFlow(config_entries.ConfigFlow, domain="warmlink"):
    async def async_step_user(self, user_input=None):
        if user_input:
            return self.async_create_entry(title="WarmLink", data=user_input)
        return self.async_show_form(step_id="user", data_schema=vol.Schema({
            vol.Required("username"): str,
            vol.Required("password"): str,
            vol.Required("language", default="en"): vol.In(LANGUAGES)
        }))
