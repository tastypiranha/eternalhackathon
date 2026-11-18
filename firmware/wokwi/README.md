# FreshSense Tag: Wokwi virtual ESP32

A simulated ESP32 crate tag. Every 2 s it publishes temperature, humidity, VOC (gas) and door state over MQTT. The backend shows the readings as crate **C-001**, the cold-room crate with the 📡 LIVE TAG badge.

**Project link:** _paste your saved wokwi.com link here_

## Set up (5 minutes)
1. Go to https://wokwi.com, sign in, and choose **New Project → ESP32 (Arduino)**.
2. Replace `diagram.json` and `sketch.ino` with the files in this folder. Add both lines of `libraries.txt` in the Library Manager.
3. In `sketch.ino`, change the `TOPIC` line to `freshsense/<TEAMCODE>/tag/C-001`. Start the backend with the **same** topic:
   ```bash
   FRESHSENSE_MQTT_TOPIC="freshsense/<TEAMCODE>/tag/C-001" uvicorn main:app --port 8000
   ```
4. Press ▶. The serial monitor should show `WiFi... connected!`, then `MQTT... connected!`, then one JSON line every 2 s.
5. Check it reached the backend: `curl localhost:8000/api/health` should show `"mqtt": "connected"` with a rising `messages` count, and C-001 on the dashboard should follow the DHT22 value.

## Wiring
| Part | Part pin | ESP32 pin |
|---|---|---|
| DHT22 (temp + humidity) | VCC / SDA / GND | 3V3 / GPIO 15 / GND |
| Potentiometer (stands in for the SGP40 VOC sensor) | VCC / SIG / GND | 3V3 / GPIO 34 / GND |
| Push button (door switch) | one side / other side | GPIO 4 / GND |
| Red LED (too warm) | anode via 220 Ω / cathode | GPIO 2 / GND |

## How to demo
1. **Before going on stage:** start the simulation, then click the DHT22 and set it to **3 °C, 88 %**. Turn the knob to zero.
2. Say: "This is our tag's real firmware running on a simulated ESP32."
3. Click the DHT22 and drag the temperature to **20 °C**. The red LED turns on, and within ~2 s C-001 on the dashboard warms up and raises a 🌡️ alert.
4. Press the button. `door_open` becomes true and a 🚪 alert appears.

## If it doesn't work
- **WiFi stuck on dots:** stop and start the simulation again.
- **MQTT `rc=-2`:** set `MQTT_HOST` to `test.mosquitto.org` in the sketch **and** start the backend with `FRESHSENSE_MQTT_HOST=test.mosquitto.org`.
- **Still not working:** use the dashboard's **📡 Live tag** slider. It drives C-001 the same way.

## Real hardware version (for the slides)
ESP32 or nRF52 + SHT31 (temp/humidity) + SGP40 (VOC) + accelerometer. BLE goes to the truck gateway, then 4G to the cloud. Reusable. Estimated BOM ₹600–900.
