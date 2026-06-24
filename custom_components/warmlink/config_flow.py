
import logging

from homeassistant import config_entries
import voluptuous as vol

from .managers.warmlink_api import WarmlinkAPI

LOGGER = logging.getLogger(__name__)

LANGUAGES = {
    "en": "English",
    "da": "Dansk"
}

DATA_SCHEMA = vol.Schema({
    vol.Required("username"): str,
    vol.Required("password"): str,
    vol.Required("language", default="en"): vol.In(LANGUAGES),
    vol.Optional("device_code", default=""): str,
})


class WarmlinkConfigFlow(config_entries.ConfigFlow, domain="warmlink"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # A blank device_code means "auto-detect" (works for owner accounts).
            # Members/shared accounts get an empty device list from the cloud, so
            # they must supply the device code explicitly — see issue #1.
            device_code = (user_input.get("device_code") or "").strip()
            user_input["device_code"] = device_code

            api = WarmlinkAPI(user_input["username"], user_input["password"], self.hass)
            if not await api.login():
                errors["base"] = "auth"
            elif device_code:
                # Verify the supplied device answers for this account.
                resp = await api.get_props_batch(device_code, ["Power", "Mode"])
                if not resp or not resp.get("objectResult"):
                    errors["device_code"] = "device_not_found"
            else:
                # Owner accounts: auto-discover via the device list.
                devs = await api.get_devices()
                if not devs or not devs.get("objectResult"):
                    errors["base"] = "no_devices"

            if not errors:
                return self.async_create_entry(title="WarmLink", data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )
