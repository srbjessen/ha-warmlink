
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


async def _validate(hass, user_input):
    """Validate credentials + device access. Returns an errors dict ({} = OK).

    Normalises ``device_code`` in place. A blank device_code means "auto-detect"
    (owner accounts); members/shared accounts get an empty device list from the
    cloud and must supply the code explicitly — see issue #1.
    """
    errors = {}
    device_code = (user_input.get("device_code") or "").strip()
    user_input["device_code"] = device_code

    api = WarmlinkAPI(user_input["username"], user_input["password"], hass)
    if not await api.login():
        errors["base"] = "auth"
    elif device_code:
        resp = await api.get_props_batch(device_code, ["Power", "Mode"])
        if not resp or not resp.get("objectResult"):
            errors["device_code"] = "device_not_found"
    else:
        devs = await api.get_devices()
        if not devs or not devs.get("objectResult"):
            errors["base"] = "no_devices"
    return errors


class WarmlinkConfigFlow(config_entries.ConfigFlow, domain="warmlink"):
    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            errors = await _validate(self.hass, user_input)
            if not errors:
                title = "WarmLink"
                if user_input.get("device_code"):
                    title = f"WarmLink {user_input['device_code']}"
                return self.async_create_entry(title=title, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or {}
            ),
            errors=errors,
        )

    async def async_step_reconfigure(self, user_input=None):
        """Change the account / device code on an existing entry.

        Updates the same config entry in place, so the entry_id — and therefore
        every entity ID and dashboard/automation reference — is preserved. No
        need to remove and re-add the integration.
        """
        errors = {}
        entry = self.hass.config_entries.async_get_entry(self.context["entry_id"])
        if user_input is not None:
            errors = await _validate(self.hass, user_input)
            if not errors:
                self.hass.config_entries.async_update_entry(entry, data=user_input)
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=self.add_suggested_values_to_schema(
                DATA_SCHEMA, user_input or (entry.data if entry else {})
            ),
            errors=errors,
        )
