# PERSON C — Data, Virtual Hardware & Pitch (lighter, well-scoped tasks)

> **For the AI assistant reading this:** you are helping Person C. Person C is less experienced, so explain every step simply, give complete copy-paste code, and never assume prior knowledge.
> You MUST also have `00_MASTER_PLAN.md`. Section 6 of the master plan is the contract. Do not change file names, field names or JSON shapes.
> **Golden rule:** nothing Person C does can break the demo. A and B never wait for C. If a task is stuck for longer than its time box, follow its "If stuck" line and move on.

---

## 1. Your mission (in order of importance)

1. **H0:30** – Create the 3 data files (copy-paste from the master plan). A needs these first.
2. **Wokwi virtual tag** – a simulated ESP32 that sends live temperature/humidity/gas readings to our backend. This is our "hardware".
3. **Model 1** – train a small model on a REAL spoilage dataset and save the results for the dashboard and slides.
4. **Pitch** – slides, demo script, Q&A sheet. You open and close the presentation.
5. **QA + backup** – test the demo like a judge would, report bugs, record backup videos, write the README, and write down the judges' feedback at Evaluation 1.

You own these folders: `firmware/wokwi/`, `notebooks/`, `data/raw/`, `pitch/`, plus `README.md`, and at the start `backend/data/products.json`, `locations.json` and `trucks.json`.

---

## 2. Task C1 (H0:00 – H0:30): Create the 3 data files ⚠️ FIRST PRIORITY

1. Clone the repo A created: `git clone <repo-url> && cd freshsense`.
2. Create these files and paste the **exact** content from the master plan:
   - `backend/data/products.json` ← master section 6.1
   - `backend/data/locations.json` ← master section 6.2 (the long list starting with `WH-1`)
   - `backend/data/trucks.json` ← master section 6.2 (3 trucks)
3. Check each file is valid JSON (run from the repo root):
   ```bash
   python3 -c "import json; [json.load(open(f'backend/data/{n}.json')) for n in ['products','locations','trucks']]; print('ALL VALID')"
   ```
   It must print `ALL VALID`. If you get an error, it gives a line number. Usually the problem is a missing comma or bracket. Compare with the master plan.
4. Count the locations: `python3 -c "import json; print(len(json.load(open('backend/data/locations.json'))))"` → must print **22**.
5. Push:
   ```bash
   git add backend/data && git commit -m "Add product, location and truck data" && git pull --rebase && git push
   ```
6. Tell A: "data files pushed".

**If stuck:** send the three files to A on chat. A can copy them in.

---

## 3. Task C2 (H0:30 – H3:00): Wokwi virtual ESP32 tag

### What you are building
A simulated ESP32 board on wokwi.com with:
- a **DHT22** temperature + humidity sensor (you can change its values while it runs),
- a **potentiometer** (a knob) that pretends to be the gas/VOC sensor,
- a **push button** that pretends to be the truck door switch (press = door opens/closes),
- a **red LED** that turns on when it's too warm.

Every 2 seconds it sends a JSON message over the internet (MQTT) to the public broker `broker.hivemq.com`. Our backend listens and shows it as crate **C-001** on the dashboard.

### Step 1: Choose the team code (with A)
Pick one unique code, e.g. `fs-k7q2x`. The MQTT topic will be `freshsense/fs-k7q2x/tag/C-001`. Give it to A. A sets it in the backend as the environment variable `FRESHSENSE_MQTT_TOPIC`. **Both sides must match exactly.**

### Step 2: Create the Wokwi project
1. Go to https://wokwi.com, sign in (a free account lets you save projects), and click **New Project → ESP32** (choose the Arduino template).
2. You'll see tabs: `sketch.ino`, `diagram.json`, and a **Library Manager** (the "+" button or the `libraries.txt` file).

### Step 3: Paste `diagram.json`
Replace the whole content of `diagram.json` with:
```json
{
  "version": 1,
  "author": "FreshSense",
  "editor": "wokwi",
  "parts": [
    { "type": "board-esp32-devkit-c-v4", "id": "esp", "top": 0, "left": 0, "attrs": {} },
    { "type": "wokwi-dht22", "id": "dht1", "top": -120, "left": 160, "attrs": { "temperature": "3", "humidity": "88" } },
    { "type": "wokwi-potentiometer", "id": "pot1", "top": -120, "left": -160, "attrs": {} },
    { "type": "wokwi-pushbutton", "id": "btn1", "top": 220, "left": 160, "attrs": { "color": "blue" } },
    { "type": "wokwi-led", "id": "led1", "top": 220, "left": -140, "attrs": { "color": "red" } },
    { "type": "wokwi-resistor", "id": "r1", "top": 290, "left": -90, "attrs": { "value": "220" } }
  ],
  "connections": [
    [ "esp:TX", "$serialMonitor:RX", "", [] ],
    [ "esp:RX", "$serialMonitor:TX", "", [] ],
    [ "dht1:VCC", "esp:3V3", "red", [] ],
    [ "dht1:GND", "esp:GND.1", "black", [] ],
    [ "dht1:SDA", "esp:15", "green", [] ],
    [ "pot1:VCC", "esp:3V3", "red", [] ],
    [ "pot1:GND", "esp:GND.1", "black", [] ],
    [ "pot1:SIG", "esp:34", "orange", [] ],
    [ "btn1:1.l", "esp:4", "blue", [] ],
    [ "btn1:2.l", "esp:GND.1", "black", [] ],
    [ "led1:A", "r1:1", "red", [] ],
    [ "r1:2", "esp:2", "red", [] ],
    [ "led1:C", "esp:GND.1", "black", [] ]
  ],
  "dependencies": {}
}
```
**If the diagram shows errors**, delete the parts and add them by hand with the blue "+" button, wired like this:

| Part | Part pin | ESP32 pin |
|---|---|---|
| DHT22 | VCC | 3V3 |
| DHT22 | SDA (data) | GPIO 15 |
| DHT22 | GND | GND |
| Potentiometer | VCC | 3V3 |
| Potentiometer | SIG (middle) | GPIO 34 |
| Potentiometer | GND | GND |
| Push button | one side | GPIO 4 |
| Push button | other side | GND |
| LED | anode (long leg, A) | 220 Ω resistor → GPIO 2 |
| LED | cathode (C) | GND |

### Step 4: Add libraries
In `libraries.txt` (or via the Library Manager), add exactly these two lines:
```
PubSubClient
DHT sensor library for ESPx
```

### Step 5: Paste `sketch.ino`
Replace everything with the code below. **Change only the `TOPIC` line** to use your team code.
```cpp
#include <WiFi.h>
#include <PubSubClient.h>
#include "DHTesp.h"

// ===== CHANGE THIS LINE: must match FRESHSENSE_MQTT_TOPIC in the backend =====
const char* TOPIC = "freshsense/fs-CHANGE-ME/tag/C-001";

const char* WIFI_SSID = "Wokwi-GUEST";   // Wokwi's built-in virtual WiFi, no password
const char* WIFI_PASS = "";
const char* MQTT_HOST = "broker.hivemq.com";
const int   MQTT_PORT = 1883;

const int DHT_PIN = 15;
const int POT_PIN = 34;
const int BTN_PIN = 4;
const int LED_PIN = 2;
const float TEMP_ALERT_C = 7.0;          // LED turns on above this (dairy safe limit)

DHTesp dht;
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

bool doorOpen = false;
int lastBtn = HIGH;
unsigned long lastPublish = 0;

void connectWiFi() {
  Serial.print("Connecting to WiFi");
  WiFi.begin(WIFI_SSID, WIFI_PASS, 6);
  while (WiFi.status() != WL_CONNECTED) { delay(250); Serial.print("."); }
  Serial.println(" connected!");
}

void connectMQTT() {
  while (!mqtt.connected()) {
    String clientId = "freshsense-tag-" + String((uint32_t)esp_random(), HEX);
    Serial.print("Connecting to MQTT...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" connected!");
    } else {
      Serial.print(" failed, rc="); Serial.println(mqtt.state());
      delay(1000);
    }
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(BTN_PIN, INPUT_PULLUP);
  pinMode(LED_PIN, OUTPUT);
  dht.setup(DHT_PIN, DHTesp::DHT22);
  connectWiFi();
  mqtt.setServer(MQTT_HOST, MQTT_PORT);
  connectMQTT();
}

void loop() {
  if (!mqtt.connected()) connectMQTT();
  mqtt.loop();

  // Button toggles the door state (press once = open, press again = closed)
  int btn = digitalRead(BTN_PIN);
  if (btn == LOW && lastBtn == HIGH) {
    doorOpen = !doorOpen;
    Serial.println(doorOpen ? "DOOR OPEN" : "DOOR CLOSED");
    delay(50);
  }
  lastBtn = btn;

  if (millis() - lastPublish >= 2000) {
    lastPublish = millis();
    TempAndHumidity d = dht.getTempAndHumidity();
    if (isnan(d.temperature) || isnan(d.humidity)) {
      Serial.println("DHT read failed");
      return;
    }
    int raw = analogRead(POT_PIN);            // 0..4095
    int voc = map(raw, 0, 4095, 0, 500);      // VOC index 0..500
    digitalWrite(LED_PIN, d.temperature > TEMP_ALERT_C ? HIGH : LOW);

    char payload[220];
    snprintf(payload, sizeof(payload),
      "{\"crate_id\":\"C-001\",\"temp_c\":%.2f,\"humidity\":%.1f,\"voc_index\":%d,\"door_open\":%s,\"source\":\"wokwi\"}",
      d.temperature, d.humidity, voc, doorOpen ? "true" : "false");
    mqtt.publish(TOPIC, payload);
    Serial.println(payload);
  }
}
```

### Step 6: Run and test
1. Click the green ▶ **Start Simulation** button.
2. The serial monitor (bottom) should show `Connecting to WiFi... connected!`, then `Connecting to MQTT... connected!`, then a JSON line every 2 seconds.
3. **Change values live:** click the DHT22 sensor while the simulation runs. Sliders appear for temperature and humidity. Move the temperature to 20 °C and the next JSON line should show ~20. Turn the potentiometer knob and `voc_index` changes. Click the button and `door_open` flips. Above 7 °C the red LED turns on.
4. **Check the message reaches our backend:** ask A to watch the dashboard (or run the backend). Crate C-001 should show your temperature within ~2 seconds.
5. **Before every demo:** set the DHT22 back to **3 °C** and **88%** humidity, and the knob near zero. (The DHT22 might start at a default like 24 °C if the attrs didn't apply. Always check.)
6. Click **Save**, then copy the project URL into `firmware/wokwi/README.md`. Also save `sketch.ino`, `diagram.json` and `libraries.txt` into `firmware/wokwi/` in the repo and push.

### `firmware/wokwi/README.md` (write this)
- Project link
- The wiring table (from above)
- The topic used
- "How to demo": start the simulation → wait for "connected" → click DHT22 → raise the temperature → watch C-001 on the dashboard turn warm and raise an alert.

**If stuck (time box: until H3:00):**
- WiFi stuck on dots → stop and start the simulation again.
- MQTT `rc=-2` → the broker may be busy. Change `MQTT_HOST` to `"test.mosquitto.org"`. **Tell A to change the backend host too.**
- Still not working at H3:00 → stop. We'll use the dashboard's "Live tag" slider instead (B built it). Tell A and B. The Wokwi screen can still be shown during the pitch as "firmware running".

---

## 4. Task C3 (H3:00 – H6:00): Model 1 on REAL data

### Goal
Show judges that a cheap gas sensor can tell fresh meat from spoiled meat, using a **real lab dataset**. You produce:
- `backend/data/model1_results.json` (exact format in master 6.10),
- `frontend/public/model/confusion_matrix.png`,
- `frontend/public/model/feature_importance.png`,
- `frontend/public/model/spoilage_curve.png`.

### Step 1: Download the dataset (time box 45 min)
1. Open https://data.mendeley.com/datasets/mwmhh766fc (Electronic nose dataset for beef quality monitoring). Use the latest version.
2. Click **Download All** (it's a ZIP). If it asks you to log in, a free Mendeley account works.
3. Unzip it into `data/raw/beef_enose/` in the repo. You should see several CSV or Excel files (one per beef cut). **Do not commit `data/raw/`.** It's git-ignored.
4. **Backup dataset, if the main one fails:** https://data.mendeley.com/datasets/czz68d9fwj (fruit spoilage in cold storage: temperature, humidity, light, CO₂, Good/Bad). Unzip to `data/raw/fruit/`.

### Step 2: Install Python packages
```bash
python3 -m venv .venv-ml && source .venv-ml/bin/activate
pip install pandas numpy scikit-learn matplotlib openpyxl
```

### Step 3: Look at the data first
Create `notebooks/peek.py`:
```python
import glob, pandas as pd
files = sorted(glob.glob("data/raw/beef_enose/**/*.csv", recursive=True) + glob.glob("data/raw/beef_enose/**/*.xls*", recursive=True))
print(len(files), "files"); print(files[:10])
f = files[0]
df = pd.read_csv(f) if f.endswith(".csv") else pd.read_excel(f)
print(df.shape); print(df.columns.tolist()); print(df.head())
```
Run `python notebooks/peek.py`. Write down:
- the gas sensor column names (often like `MQ135`, `MQ136`, `MQ2`…),
- whether there is a **class/label** column (e.g. `class`, `label`) or a **microbial count** column (e.g. `TVC`, `Total Viable Count`, `Microbial Population`),
- the time column name (e.g. `minute`), if any.

### Step 4: Train the model
Create `notebooks/model1_train.py`. **Only edit the CONFIG block** if your column names differ.
```python
import glob, json, os
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import GroupKFold, train_test_split
from sklearn.metrics import accuracy_score, f1_score, confusion_matrix, ConfusionMatrixDisplay

# ===================== CONFIG (edit if needed) =====================
RAW_DIR      = "data/raw/beef_enose"
DATASET_NAME = "Electronic nose dataset for beef quality monitoring (Wijaya et al.)"
DATASET_URL  = "https://data.mendeley.com/datasets/mwmhh766fc"
LABEL_CANDIDATES = ["class", "Class", "label", "Label", "CLASS"]
TVC_CANDIDATES   = ["TVC", "tvc", "Total Viable Count", "Microbial Population", "microbial population"]
DROP_COLUMNS     = ["minute", "Minute", "time", "Time", "timestamp", "No", "no", "index", "Unnamed: 0"]
# If only TVC (log CFU/g) exists, classes are made with these approximate cut-offs:
TVC_BINS   = [-np.inf, 3, 4, 5, np.inf]
TVC_LABELS = ["excellent", "good", "acceptable", "spoiled"]
OUT_JSON = "backend/data/model1_results.json"
OUT_IMG  = "frontend/public/model"
# ===================================================================

os.makedirs(OUT_IMG, exist_ok=True)
files = sorted(glob.glob(f"{RAW_DIR}/**/*.csv", recursive=True) + glob.glob(f"{RAW_DIR}/**/*.xls*", recursive=True))
assert files, f"No data files found in {RAW_DIR}"
frames = []
for f in files:
    df = pd.read_csv(f) if f.endswith(".csv") else pd.read_excel(f)
    df["__group"] = os.path.basename(f)          # one group per file (= per beef cut)
    frames.append(df)
data = pd.concat(frames, ignore_index=True)
data.columns = [str(c).strip() for c in data.columns]

label_col = next((c for c in LABEL_CANDIDATES if c in data.columns), None)
tvc_col   = next((c for c in TVC_CANDIDATES if c in data.columns), None)
if label_col:
    y = data[label_col].astype(str).str.strip().str.lower()
elif tvc_col:
    y = pd.cut(data[tvc_col].astype(float), bins=TVC_BINS, labels=TVC_LABELS).astype(str)
else:
    raise SystemExit(f"No label or TVC column. Columns are: {data.columns.tolist()}")

exclude = set(DROP_COLUMNS) | {label_col, tvc_col, "__group"}
X = data[[c for c in data.columns if c not in exclude]].select_dtypes(include=[np.number])
mask = X.notna().all(axis=1) & y.notna() & (y != "nan")
X, y, groups = X[mask], y[mask], data.loc[mask, "__group"]
print("Samples:", len(X), "Features:", X.columns.tolist()); print(y.value_counts())

model = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1)
n_groups = groups.nunique()
if n_groups >= 3:
    # Honest validation: train on some beef cuts, test on a cut the model has never seen
    validation = f"leave-one-group-out style GroupKFold ({min(5, n_groups)} folds, grouped by beef cut / file)"
    y_true, y_pred = [], []
    for tr, te in GroupKFold(n_splits=min(5, n_groups)).split(X, y, groups):
        model.fit(X.iloc[tr], y.iloc[tr])
        y_pred += list(model.predict(X.iloc[te])); y_true += list(y.iloc[te])
else:
    validation = "random stratified 70/30 split (WARNING: neighbouring time samples may inflate accuracy)"
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.3, stratify=y, random_state=42)
    model.fit(Xtr, ytr); y_pred = list(model.predict(Xte)); y_true = list(yte)

acc = accuracy_score(y_true, y_pred)
f1  = f1_score(y_true, y_pred, average="macro")
classes = [c for c in TVC_LABELS if c in set(y_true)] or sorted(set(y_true))
print(f"Accuracy={acc:.3f}  Macro-F1={f1:.3f}  ({validation})")

# Confusion matrix
cm = confusion_matrix(y_true, y_pred, labels=classes)
ConfusionMatrixDisplay(cm, display_labels=classes).plot(cmap="Reds", colorbar=False)
plt.title("Model 1 – spoilage stage (real e-nose data)"); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/confusion_matrix.png", dpi=150); plt.close()

# Feature importance (fit on all data)
model.fit(X, y)
imp = pd.Series(model.feature_importances_, index=X.columns).sort_values()
imp.tail(10).plot(kind="barh", color="#E23744")
plt.title("Which sensors matter most"); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/feature_importance.png", dpi=150); plt.close()

# Spoilage curve: top gas sensor over time for the first beef cut, coloured by class
top = imp.index[-1]
g0 = groups.iloc[0]
sub = X[groups == g0].reset_index(drop=True); lab = y[groups == g0].reset_index(drop=True)
colors = {"excellent": "#16A34A", "good": "#EAB308", "acceptable": "#F97316", "spoiled": "#DC2626"}
plt.figure(figsize=(8, 3.5))
plt.scatter(sub.index, sub[top], c=[colors.get(v, "#6B7280") for v in lab], s=4)
plt.xlabel("Time (sample number)"); plt.ylabel(f"{top} reading")
plt.title(f"Gas sensor rises as beef spoils ({g0})"); plt.tight_layout()
plt.savefig(f"{OUT_IMG}/spoilage_curve.png", dpi=150); plt.close()

result = {
    "available": True,
    "dataset_name": DATASET_NAME,
    "dataset_url": DATASET_URL,
    "task": "Classify spoilage stage from gas sensor + temperature + humidity readings",
    "n_samples": int(len(X)), "n_features": int(X.shape[1]),
    "classes": classes,
    "model": "RandomForestClassifier(n_estimators=200)",
    "validation": validation,
    "accuracy": round(float(acc), 3), "macro_f1": round(float(f1), 3),
    "top_features": imp.index[::-1][:3].tolist(),
    "images": ["/model/confusion_matrix.png", "/model/feature_importance.png", "/model/spoilage_curve.png"],
    "notes": "Real lab data. Shows that low-cost gas sensors can detect spoilage stage.",
}
json.dump(result, open(OUT_JSON, "w"), indent=2)
print("Saved", OUT_JSON)
```
Run from the repo root: `python notebooks/model1_train.py`.

### Step 5: Check and push
- Open the 3 PNGs. Do they look sensible?
- Write down **Accuracy** and **Macro F1** for the slides.
- **Be honest:** if accuracy is 0.99+ with a random split, say it might be inflated. The grouped validation is the honest number.
- Push the JSON and PNGs (not the raw data). Tell B the images are in `frontend/public/model/`.

**If stuck (time box: until H6:00):**
- Wrong column names → ask your AI assistant, pasting the output of `peek.py` and this script.
- Main dataset impossible → use the fruit dataset: set `RAW_DIR = "data/raw/fruit"`, the fruit dataset name/URL, and its label column (likely `Class` with Good/Bad). Update `classes` accordingly.
- Nothing works by H6:00 → write `{"available": false}` to `backend/data/model1_results.json`. The dashboard shows "pending". Move on to the slides.

---

## 5. Task C4 (H6:00 – H8:00): Evaluation 1 pitch + QA + backup video

### Evaluation 1 slides (5 slides, Google Slides or similar; save a PDF copy in `pitch/`)
1. **FreshSense:** one line ("Per-crate freshness intelligence for the Eternal cold chain") + the team names.
2. **The problem:** the 40-minute loading-bay chicken example; three leaks: invisible spoilage, wrong-order dispatch, no feedback loop.
3. **Our solution:** Sense → Predict → Act (3 boxes) + "redirects crates across Hyperpure, Blinkit, Zomato, Feeding India".
4. **Our data approach:** a table: real e-nose data (Model 1) · literature shelf-life parameters + USDA FoodKeeper · simulated fleet (clearly labelled) · Wokwi ESP32 firmware.
5. **Progress + next 8 hours:** what works now; next: full journey report, analytics, donation flow, benchmark.

### Evaluation 1 demo script (3 minutes), write it in `pitch/demo_script_eval1.md`
| Time | Who | What |
|---|---|---|
| 0:00 | C | Slides 1–3 (problem + solution) |
| 0:45 | C | Slide 4 (data approach) + show the Wokwi simulation running |
| 1:15 | B | Dashboard: Reset (already done before) → Resume → explain the map |
| 1:40 | B/A | Heat C-003 → alert → redirect on the map → FEFO vs FIFO |
| 2:30 | A | Open C-003 → history chart |
| 2:45 | C | Slide 5 (next steps) |

### QA checklist (run it at H6:30 and again before each rehearsal)
Write results in `pitch/qa_log.md` as `✅` / `❌ + what happened + steps to reproduce`:
- [ ] Backend starts with no errors; `http://localhost:8000/api/health` shows `{"ok": true}`
- [ ] Dashboard loads at `http://localhost:5173`; connection dot is green
- [ ] 22 locations visible on the map; 3 trucks with coloured routes; C-001 near Hoskote
- [ ] Reset → sim is paused → Resume → trucks start moving
- [ ] Heat C-003 → excursion toast within ~5 s → reroute toast within ~15 s → grey dashed old line + glowing new line
- [ ] FIFO table shows a red "would be rejected" row; FEFO shows C-003 near the top
- [ ] Shock C-007 → shock alert
- [ ] Door on T-1 → door alert; temperatures on T-1 rise
- [ ] Compressor fail T-3 → C-008 redirected, later donated (❤️) → Fix compressor works
- [ ] Click a crate → journey drawer opens with charts; Esc closes it
- [ ] Wokwi: raise DHT22 temp → C-001 changes within ~2 s (or the slider works)
- [ ] Pause/Resume and speed change work
- [ ] Reset twice in a row → same starting picture both times
- [ ] Analytics tab loads (Phase 2)

Send bugs to A (backend) or B (frontend) with exact steps. Don't try to fix their code yourself.

### Backup video (H7:30)
On macOS press `Cmd + Shift + 5` → "Record Entire Screen" (turn on the microphone in Options if you want narration). Record the full Evaluation 1 demo flow once (about 2–3 min). Save it to `pitch/backup_eval1.mov`. **Don't commit large videos.** Keep them on the laptop and a USB stick or Google Drive.

### At Evaluation 1
Write down **every judge comment word for word** in `pitch/judges_feedback.md`. At H8:30, read them to the team.

---

## 6. Phase 2 (H8 → H16)

### Task C5 (H8:30 – H10:30): Final slides (9 slides)
| # | Title | Content |
|---|---|---|
| 1 | FreshSense | Tagline + team |
| 2 | The problem | Loading-bay chicken story; 3 leaks; "freshness is the product" |
| 3 | The FreshSense tag (hardware) | ESP32 + SHT31 (temp/humidity) + SGP40 (VOC gas) + accelerometer; BLE to a truck gateway; reusable; **BOM ≈ ₹600–900 (estimate)**; screenshot of the Wokwi circuit |
| 4 | Data approach | Real: e-nose datasets (Model 1). Literature: shelf-life parameters, USDA FoodKeeper. Simulated: fleet, orders, rejections (clearly labelled). Link list |
| 5 | How it works | Architecture diagram (redraw master section 4 simply: Tag → Backend brain → Dashboard) + the freshness formula in one line: "warmer = faster spoilage (Arrhenius)" |
| 6 | Live demo | (switch to the dashboard) |
| 7 | Results | Model 1 accuracy (REAL data) + confusion matrix image; benchmark % (SIMULATION) from A; a small "model card" box: what is real vs simulated |
| 8 | Impact for Eternal | Fewer rejections, less waste, kg saved, CO₂; cross-company value: Hyperpure → Blinkit / Zomato / Feeding India; spoilage heatmap per truck/driver = accountability |
| 9 | Pilot plan + ask | 1 warehouse, ~5 trucks, 3 products (chicken, dairy, leafy greens), 6–8 weeks; measure rejection rate and shelf-life prediction error vs control routes; ask: pilot access + data |

Style: white background, accent red `#E23744`, big text, max ~25 words per slide. Use text names for Eternal brands; **no official logos** unless the organisers provided them.

### Task C6 (H10:30 – H12:00): Final demo script + Q&A sheet
- `pitch/demo_script_final.md`: copy master section 9 and add the **exact words** for your parts (opening and closing). Practise them out loud until you can say them without reading.
  - **Opening (example):** "Imagine a crate of chicken that sat 40 minutes in a hot loading bay. Today's system treats it exactly like a crate that stayed cold, until a restaurant opens it and rejects it. Across a supply chain like Hyperpure's, that means wasted food, rejected deliveries and lost trust. We built FreshSense."
  - **Closing (example):** "FreshSense turns a printed date into a live freshness score, and turns that score into action across the Eternal network. In our demo we saved {kg} kg today; in simulation, {X}% fewer rejections. We'd love to pilot this with one Hyperpure warehouse. Thank you."
- `pitch/qa_sheet.md`: a short answer for each question (A answers the technical ones):

| Question | Short answer |
|---|---|
| Where is the hardware? | The tag design is off-the-shelf parts (ESP32, SHT31, SGP40). The firmware runs on a simulated ESP32 (Wokwi), and public datasets recorded with ESP32 + gas sensors show the sensor class works |
| Is your data fake? | Model 1 uses real lab data. The fleet is a simulation, clearly labelled. The pilot provides real rejection data |
| How is this different from existing cold-chain trackers? | They alert that a crate got warm. We predict hours left per crate and redirect it inside the Eternal network |
| What about sensor drift? | We use change from each crate's own starting level, not absolute values; temperature is the main signal; periodic calibration |
| Cost? | About ₹600–900 per reusable tag (estimate), used for hundreds of trips |
| What if a redirect breaks a restaurant's order? | Roadmap: swap in a fresher crate from warehouse stock for that order |
| How did you pick the shelf-life numbers? | Literature-style Arrhenius parameters per category plus USDA FoodKeeper; the pilot calibrates them |

### Task C7 (H12:00 – H13:30): Plug in numbers + README + QA
- Get from A: benchmark `rejection_reduction_pct` and `waste_reduction_pct`. Put them on slide 7, labelled "simulation".
- Get from a demo run: the kg saved number for the closing line.
- Write `README.md` at the repo root:
  - what FreshSense is (3 lines),
  - how to run the backend (`cd backend && pip install -r requirements.txt && uvicorn main:app --port 8000`),
  - how to run the frontend (`cd frontend && npm install && npm run dev`),
  - the Wokwi link,
  - datasets used (links from master section 12),
  - team names.
- Run the full QA checklist again and report bugs.

### Task C8 (H14:00 – H16:00): Rehearse + final backup
- 3 full rehearsals with a timer (target 5:00, never over 5:30).
- Record the **final backup video** of the whole demo after the freeze (around H15).
- Before going on stage: Wokwi DHT22 set to 3 °C / 88%, knob at zero, simulation started; dashboard Reset done (sim paused); slides open on slide 1; video file ready.

---

## 7. Things you must NOT do
- Don't edit files in `backend/` (except the 3 data files at H0 and `model1_results.json`) or `frontend/src/`.
- Don't commit `data/raw/`, large videos or `.venv` folders.
- Don't present simulated numbers as real. Always say "simulation".
- Don't change the MQTT topic without telling A.
- Don't spend more than the time box on any task. Follow the "If stuck" line.

## 8. Your checkpoints
| Time | You must have |
|---|---|
| H0:30 | 3 data files pushed and valid |
| H3:00 | Wokwi tag sending to the backend (or a decision to use the slider) |
| H6:00 | Model 1 results JSON + 3 PNGs pushed (or `available: false`) |
| H7:30 | Evaluation 1 slides + script done, QA run once, backup video recorded |
| H8:30 | Judges' feedback shared with the team |
| H12:00 | Final slides + demo script + Q&A sheet |
| H13:30 | Numbers plugged in, README written, QA passed |
| H15:00 | Final backup video recorded |
