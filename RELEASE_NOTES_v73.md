# WarmLink v73.0 - Device-Driven DHW Range

## 🔧 Changed — DHW target range now follows your unit

The DHW target dropdown previously used a fixed **47–60 °C** band. It now reads the device's **own min/max** (registers `R36`/`R37`) **live**, so:
- You get your unit's actual configured range (e.g. **15–55 °C** on some models, 47–60 on others).
- If you change the limits in the WarmLink app, the dropdown follows on the next update.

Thanks to @ferrystienstra-cloud for the suggestion (#9).

---

## ⚠️ A note on low DHW temperatures (Legionella)

Setting the tank low (e.g. ~35 °C) for price or solar-surplus optimisation is genuinely useful — but a tank sitting around **32–45 °C is exactly where Legionella grows fastest**. General guidance (WHO/HSE) is to store hot water at **≥60 °C**, or — if you run it cooler for efficiency — to run a **weekly anti-Legionella cycle that heats the whole tank to ≥60 °C** (most WarmLink/Zealux units have this built in).

For reference: at 60 °C Legionella is ~killed in 30 minutes; at 55 °C a full kill takes 5–6 hours. So if you run the tank low, keep the weekly disinfection cycle on.

---

## ⬆️ Upgrade
- **HACS:** update to v73.0 → restart. **Manual:** replace the `custom_components/warmlink` folder → restart.
- **Not a breaking change** — same DHW target select, just an automatic/wider range from your device.

---

☕ *Enjoying WarmLink? It's free and maintained in my spare time — [a coffee](https://ko-fi.com/srbjessen) is a lovely thank-you.*
