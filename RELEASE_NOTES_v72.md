# WarmLink v72.0 - Member-Account Support

## 🐛 Fixed — Shared / "Member" Accounts

WarmLink allows only one concurrent login per account, so many people keep their main (owner) account for the app and add a **second account as a "member"** of the home for Home Assistant. Until now that failed: member accounts receive an **empty device list** from the WarmLink cloud, so the integration couldn't find the heat pump and setup never completed (issue #1).

**Fix:** the config flow now has an optional **Device code** field.
- **Owner accounts** — leave it blank; the device is auto-detected as before.
- **Member / shared accounts** — enter the heat pump's device code (find it in the WarmLink app → device information). The integration then talks to the device directly.

Login and device access are also validated during setup now, so wrong credentials or a wrong device code give a clear error instead of a silent failure.

**Resolves #1.**

---

## ⬆️ Upgrade
- **HACS:** update to v72.0 → restart Home Assistant. **Manual:** replace the `custom_components/warmlink` folder → restart.
- **No changes needed for existing setups** — the Device code field is optional and defaults to blank (auto-detect). Owner accounts are unaffected.
- **Member-account users:** after updating, remove and re-add the integration with the Device code filled in.

---

## Resolves
- #1 — "Integration does not work with 'member' accounts"
