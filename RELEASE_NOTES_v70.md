# WarmLink v70.0 - Entity ID Fix

## ⚠️ BREAKING CHANGE - Entity ID Migration Required

This release fixes invalid entity ID warnings but **changes entity IDs for 61 sensors**. Migration required!

---

## 🐛 Fixed

### Invalid Entity ID Warnings
- **79 warnings eliminated** for sensors with spaces in codes
- Complies with Home Assistant 2027.x+ requirements
- Follows Home Assistant best practices (entity.should_not_set_entity_id)

### Affected Sensors (61 total)
Entity IDs for these sensor types will change:
- M1-M4 timer sensors (M1 Mode, M1 Start, M1 End, etc.)
- W1-W5 schedule sensors (W1 Mode, W1 Start Hour, etc.)
- Zone 2 sensors (Zone 2 Mixing Temp, Zone 2 Water Target, etc.)
- Version sensors (Mainboard Version, SubBoard Version, etc.)

---

## 🔄 Entity ID Changes

### Examples

**Before v70:**
```
sensor.warmlink_m1_mode_m1 mode                                    ❌
sensor.warmlink_zone_2_mixing_temp_zone 2 mixing temp              ❌
sensor.warmlink_mainboard_version_mainboard version                ❌
```

**After v70:**
```
sensor.m1_mode_m1_mode                                             ✅
sensor.zone_2_mixing_temp_zone_2_mixing_temp                       ✅
sensor.mainboard_version_mainboard_version                         ✅
```

### Unaffected Sensors (330 total)
These sensors **DO NOT** change:
- T01-T39 (temperature sensors)
- P01-P20 (pressure/parameter sensors)
- F01-F14 (function sensors)
- All other sensors without spaces

---

## 📋 Migration Guide

### Before Upgrading

1. **Backup dashboards** - Export YAML from all dashboards using affected sensors
2. **Backup automations** - Copy `automations.yaml`
3. **Document current entity IDs** - Developer Tools → States → Filter "warmlink" → Take screenshot

### Installation

1. Download `warmlink_v70_entity_id_fix.zip`
2. Replace `config/custom_components/warmlink/` with new files
3. Restart Home Assistant
4. **Note new entity IDs** - Developer Tools → States → Compare with backup

### Update References

1. **Dashboards** - Find/replace old entity IDs with new ones in YAML
2. **Automations** - Update `automations.yaml` with new entity IDs
3. **Scripts** - Update any scripts referencing affected sensors
4. **Template sensors** - Update templates using affected sensors
5. **Node-RED** - Update flow nodes (if applicable)

### Reload Configuration

```
Developer Tools → YAML → Reload Automations
```

---

## ⏱️ Migration Effort

Estimated time depends on your setup:
- **Minimal usage (few affected sensors):** 15-30 minutes
- **Moderate usage (several dashboards):** 1-2 hours
- **Heavy usage (complex automations):** 2-3 hours

---

## ✅ Verification

After migration, check logs:

```
Settings → System → Logs → Search "invalid entity"
```

**Should NOT show:**
```
❌ Detected invalid entity ID
```

**Should show:**
```
✅ WarmLink: Setup completed successfully
✅ No warnings
```

---

## 📊 Technical Changes

### Code Changes
- Removed manual `self.entity_id` setting in sensor.py
- Uses `code_friendly` in unique_id for consistency
- Lets Home Assistant auto-generate entity_id from name + unique_id

### Benefits
- Complies with Home Assistant guidelines
- Future-proof for HA 2027.x+
- Eliminates 79 deprecation warnings
- Follows entity naming best practices

---

## 🔧 Rollback

If you need to rollback:

1. Download [v69 release](https://github.com/srbjessen/ha-warmlink/releases/tag/v69.0)
2. Replace files
3. Restart Home Assistant
4. Old entity IDs will work again

---

## 📦 What's Included

### From Previous Versions
- ✅ 391 sensors (v68 fault codes included)
- ✅ Async file loading (v69 performance fix)
- ✅ Manual refresh button (v67)
- ✅ No data gaps (v66 intelligent caching)
- ✅ Stable operation (v65 empty value fix)

### Current Version
- ✅ Valid entity IDs (v70 fix)
- ✅ Future-proof naming
- ✅ No deprecation warnings

---

## 🆘 Support

- **Migration issues?** [Open an issue](https://github.com/srbjessen/ha-warmlink/issues)
- **Questions?** [Start a discussion](https://github.com/srbjessen/ha-warmlink/discussions)

---

## 📝 Full Changelog

See [CHANGELOG.md](https://github.com/srbjessen/ha-warmlink/blob/main/CHANGELOG.md) for complete version history.

---

**Version:** 70.0  
**Release Date:** 2025-02-15  
**Breaking Change:** Yes - Entity ID migration required  
**Migration Time:** 30-120 minutes  

**BACKUP BEFORE UPGRADING!** 💾
