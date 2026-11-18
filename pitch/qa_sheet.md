# FreshSense — Judge Q&A sheet

| Question | Short answer | Who |
|---|---|---|
| **Where is the hardware?** | The tag uses off-the-shelf parts (ESP32, SHT31 temp/humidity, SGP40 gas, accelerometer). Our firmware runs on a simulated ESP32 (Wokwi) and streams live into the dashboard. The public dataset we trained on was recorded with the same class of low-cost MQ gas sensors. | C |
| **Is your data fake?** | Model 1 uses **real lab data**: 10,800 readings from 5 beef cuts, tested on cuts the model never saw. The fleet, orders and rejections are a **simulation**, and we label it that way everywhere. A pilot would give us real rejection data. | A |
| **Why is accuracy only 63 %?** | It's 4 stages (chance = 25 %), tested honestly on unseen beef cuts. Errors are almost always the neighbouring stage: 96 % are within one stage. For the business question "spoiled or sellable", it's 74 %. And gas is only a second signal: temperature history is the main one, through the Arrhenius model. | A |
| **How is this different from existing cold-chain trackers?** | Trackers alert you that a crate got warm. We predict the **hours left for each crate** and **act on it across the Eternal network**: reroute to Blinkit, a nearer Zomato restaurant, or Feeding India. | A |
| **How do you calculate hours left?** | Arrhenius kinetics: every degree above the reference temperature speeds up spoilage exponentially, with parameters per product. We add up the damage minute by minute over the crate's whole temperature history. A strong gas reading speeds it up further. | A |
| **Where do the shelf-life numbers come from?** | Literature-style kinetic parameters per category, cross-checked with USDA FoodKeeper. The pilot calibrates them with real rejections. | A |
| **What about sensor drift / humid cold rooms?** | Temperature is the primary signal, with periodic calibration and IP-rated casing. Gas is used as a secondary correction. | A |
| **Cost? Who pays?** | About ₹600–900 per reusable tag (estimate), used for hundreds of trips, so a few rupees per crate-trip. One avoided rejected chicken crate pays for many trips. | C |
| **Tag loss?** | Tags return with the crates (reusable crate loop), and the same BLE link tracks them. | C |
| **Won't a redirect break the restaurant's order?** | Roadmap: swap in a fresher crate from warehouse stock for that order automatically. | A |
| **Why 66 % fewer rejections?** | It's a 1,000-crate simulation that includes realistic limits: problems caught in time only 85 % of the time, a dark store with spare demand 70 % of the time, a food bank available 80 % of the time. Our pilot target is a more conservative 30–40 %. | A |
| **How would this integrate with Hyperpure?** | Same API the dashboard uses: freshness per crate, plus redirect suggestions, fed into Hyperpure's dispatch and Blinkit inventory systems. | A |
| **Scale?** | One gateway per truck/warehouse. The backend is stateless per tick and scales by city. The model improves per product and per route as real data comes in. | A |
| **What did you actually build in 16 hours?** | Firmware, the freshness engine, a simulator with full crate histories, the redirect engine, a live map dashboard, the journey report, analytics, and a model trained on real data. 13 automated backend tests. | A |
