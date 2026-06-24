# WarmLink v71.0 - Writable Controls

## ✨ NEW - Control Your Heat Pump from Home Assistant

The integration can now **set** values, not just read them. This release adds Power, Operating Mode, and DHW target controls, all driven through the WarmLink cloud.

**Not a breaking change** — purely additive. Existing sensors and entity IDs are unchanged; no migration needed (unlike v70).

---

## ✨ Added

### Writable Controls
- **Power switch** (`switch.warmlink_power`) — turn the heat pump on/off from Home Assistant.
- **Operating Mode select** (`select.warmlink_operating_mode`) — *DHW only* / *Heating* / *Heating + DHW*. Only confirmed-safe modes are exposed, to avoid accidentally selecting a cooling mode.
- **DHW Target Temperature select** (`select.warmlink_dhw_target_temperature`) — set the hot-water setpoint as a whole-degree dropdown (47–60 °C). A dropdown is one unambiguous write per change, unlike a stepper/box that sends a cloud write per increment and races over the slow round-trip. Usable as an automation target/trigger. **Resolves #9.**

### Anti-Thermosiphon Guide + Example
- New [`examples/automation_anti_thermosiphon.yaml`](examples/automation_anti_thermosiphon.yaml) plus a README section. An optional way to use the Operating Mode select as a software "check valve" that stops summer DHW tank drain: after a reheat, park the 3-way diverter *off* the tank (Mode = *Heating*) to break the passive convection loop, then release it before the next reheat. The guide explains when it applies and why pipe geometry (a vertical primary riser off the top of the tank) can make the siphon worse.

---

## 🔄 Changed
- **Update interval reduced from 5 minutes to 2 minutes** for more responsive data.

---

## 🔧 Under the Hood
- Added the `DeviceControl` cloud endpoint and a `set_value()` write path — the foundation all three controls write through.
- Added `.gitignore`.

---

## ⬆️ Upgrade
- Smooth file replacement + restart. **No entity-ID migration** (unlike v70).
- The new switch and select entities appear automatically after a restart.

---

## Resolves
- #9 — "missing set DHW temp"
