# FreshSense — Final demo script (5 minutes)

**Roles:** C opens and closes · B drives the laptop · A explains the brain and takes technical questions.

## Before going on stage (checklist)
- [ ] Backend running (no `--reload`), dashboard open at http://localhost:5173, browser zoom so the bottom bar fits
- [ ] Click **🔄 Reset demo** (the sim is now **paused**)
- [ ] Crate dropdown = **C-003**, truck dropdown = **Truck 3**
- [ ] Wokwi simulation running. DHT22 set to **3 °C / 88 %**, knob at zero, serial monitor shows "MQTT connected"
- [ ] Slides open on slide 1
- [ ] Backup video ready on the desktop

## Script

| Time | Who | On screen | Say (roughly) |
|---|---|---|---|
| 0:00 | **C** | Slide 1–2 | "Imagine a crate of chicken that sat 40 minutes in a hot loading bay. Today's system treats it exactly like a crate that stayed cold, until a restaurant opens it and rejects it. Across a supply chain like Hyperpure's, that means wasted food, rejected deliveries and lost trust. We built **FreshSense**." |
| 0:30 | **C** | Slide 3 → Wokwi tab | "Every crate gets a small reusable tag: temperature, humidity, a gas sensor that smells spoilage, and a door/shock sensor. About ₹600–900. This is our real firmware running on a simulated ESP32." **Drag the DHT22 to 20 °C** → "the dashboard's live-tag crate warms up and raises an alert." |
| 1:15 | **B** | Dashboard, Live Map. Click **▶ Resume** | "This is the Eternal network in Bengaluru: Hyperpure warehouses, Blinkit dark stores, Zomato partner restaurants and Feeding India partners. 3 trucks, 12 crates, each with a live freshness score and hours of shelf life left." |
| 1:40 | **B + A** | **🔥 Heat crate** (C-003) | A: "C-003 is chicken heading to a restaurant in Rajajinagar. It's already first in our FEFO list because it has the least time left. Now its truck gets hot…" (wait ~7 s) "…its hours left drop, and FreshSense sees it would arrive below the 24 hours the restaurant needs. So it **reroutes it to the Blinkit store in Whitefield**, which sells chicken the same day. The old route goes grey, the new one lights up. Look at the left table: the old FIFO method would have delivered it and had it rejected." |
| 2:30 | **B + A** | **❄️ Compressor fail** (Truck 3) | A: "Now a bigger problem: Truck 3's cooling fails." (~9 s) "C-008 is redirected to a dark store…" (~15 s more) "…and when it's too late to sell, it's **donated to Feeding India** while it's still safe." **B clicks ✅ Fix compressor** right after the ❤️ toast. Optional: **💥 Shock crate** on C-007. |
| 3:15 | **A** | Click C-003 (redirect card) → Journey report. Toggle **This trip (live)** | "Every crate carries its full history. The heat spike is here. The stage table shows where freshness was lost: 40 minutes in the loading dock before the trip, and the truck heat just now. That's accountability we can tie back to a truck, driver or warehouse." |
| 3:50 | **A** | **📊 Analytics** tab | "Truck 3 is the problem truck this week. Our gas-sensor model, trained on **real lab data**, gets the spoilage stage exactly right 63 % of the time, and within one stage 96 % of the time, on beef cuts it had never seen. In simulation, FreshSense cuts rejections by about 66 %." |
| 4:30 | **C** | Slide 8–9 | "FreshSense turns a printed date into a live freshness score, and turns that score into action across the whole Eternal network. In this demo we saved 60 kg of food in a few minutes. We'd love to pilot this with one Hyperpure warehouse, 5 trucks and 3 products for 6–8 weeks. Thank you." |

## If something breaks
- **Wokwi won't connect:** skip it and use **📡 Live tag** in the dashboard (slider to 20 °C, "Send as live tag").
- **Dashboard frozen:** check the connection dot (top right). If it's red, restart the backend, then Reset demo.
- **Everything fails:** play the backup video and narrate over it.
