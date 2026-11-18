# PERSON B — Frontend (React dashboard, ~35% of the build)

> **For the AI assistant reading this:** you are helping Person B build the FreshSense dashboard in React.
> You MUST also have `00_MASTER_PLAN.md`. **Section 6 of the master plan is the contract.** Use the exact field names, endpoint paths and JSON shapes from master 6.8–6.10. Do not invent fields the backend doesn't send. If the backend is not ready, use mock data shaped exactly like master 6.9.

---

## 1. Your mission

Build a single-page dashboard that makes the judges say "wow" in 10 seconds:
1. **Live map** of Bengaluru: Hyperpure warehouses, Blinkit dark stores, Zomato restaurants, Feeding India partners, moving trucks, and route lines. When a crate is redirected, the **old route turns grey and dashed and the new route lights up**.
2. **Right panel:** live redirect/alert feed and **FEFO vs FIFO** dispatch tables.
3. **Control panel** (bottom bar): buttons that trigger scenarios (heat, shock, door, compressor), pause/resume, speed, reset, plus a "Live tag" slider fallback.
4. **Crate drawer → Journey Report:** full temperature/humidity/freshness history with a safe band, excursion shading, a stage table, and a blame line.
5. **Crates tab** (cards) and **Analytics tab** (hours lost by truck/stage, impact counters, benchmark, Model 1 card).
6. Toast notifications for new alerts and redirects.

You drive the laptop during the demo.

---

## 2. Setup (H0 – H1)

Requirements: Node 20+.
```bash
cd freshsense
npm create vite@latest frontend -- --template react
cd frontend
npm install
npm install leaflet react-leaflet recharts react-hot-toast
npm install -D tailwindcss @tailwindcss/vite
```
- **react-leaflet version:** check `package.json`. If `react` is version 19 → `npm install react-leaflet@5`. If `react` is 18 → `npm install react-leaflet@4`.
- **Tailwind v4 setup:** in `vite.config.js` add `import tailwindcss from '@tailwindcss/vite'` and put `tailwindcss()` in `plugins`. In `src/index.css` put `@import "tailwindcss";` as the first line.
- **Leaflet CSS is mandatory:** in `src/main.jsx` add `import 'leaflet/dist/leaflet.css'`. Without it the map renders broken.
- `frontend/.env`:
  ```
  VITE_API_BASE=http://localhost:8000
  VITE_WS_URL=ws://localhost:8000/ws
  VITE_USE_MOCK=false
  ```
- Run: `npm run dev` → http://localhost:5173

### Folder structure
```
frontend/src/
├── main.jsx
├── App.jsx                     # layout + tabs + selected crate state
├── index.css
├── config.js                   # API_BASE, WS_URL, USE_MOCK, STATUS_COLORS, TYPE_ICONS, PRODUCT_EMOJI
├── api.js                      # fetch helpers for every REST endpoint
├── hooks/useLiveState.js       # WebSocket + reconnect + polling fallback + mock mode
├── mock/state.json             # mock State (master 6.9 shape, 12 crates, 3 trucks)
├── mock/locations.json         # copy of GET /api/locations shape (master 6.1 + 6.2)
├── components/
│   ├── Header.jsx
│   ├── MapView.jsx             # Leaflet map, markers, routes, redirect animation
│   ├── RightPanel.jsx          # Feed + DispatchTables
│   ├── EventFeed.jsx
│   ├── DispatchTables.jsx      # FEFO vs FIFO side by side
│   ├── ControlPanel.jsx        # bottom bar + LiveTagSlider
│   ├── LiveTagSlider.jsx
│   ├── CrateCard.jsx
│   ├── CratesTab.jsx
│   ├── FreshnessRing.jsx       # small SVG ring 0-100
│   ├── JourneyDrawer.jsx       # slide-over with full report
│   ├── AnalyticsTab.jsx
│   └── StatusBadge.jsx
```

### Shared constants (`config.js`), exact values
```js
export const API_BASE = import.meta.env.VITE_API_BASE || 'http://localhost:8000';
export const WS_URL   = import.meta.env.VITE_WS_URL   || 'ws://localhost:8000/ws';
export const USE_MOCK = import.meta.env.VITE_USE_MOCK === 'true';

export const STATUS_COLORS = {
  fresh: '#16A34A', watch: '#EAB308', at_risk: '#F97316', critical: '#DC2626', spoiled: '#6B7280',
};
export const STATUS_LABELS = {
  fresh: 'Fresh', watch: 'Watch', at_risk: 'At risk', critical: 'Critical', spoiled: 'Spoiled',
};
export const STATUS_ORDER = ['fresh', 'watch', 'at_risk', 'critical', 'spoiled'];
export const TYPE_ICONS = { warehouse: '🏭', dark_store: '⚡', restaurant: '🍽️', food_bank: '❤️' };
export const TYPE_LABELS = {
  warehouse: 'Hyperpure warehouse', dark_store: 'Blinkit dark store',
  restaurant: 'Zomato partner restaurant', food_bank: 'Feeding India partner',
};
export const BRAND_RED = '#E23744';
```
Formatting helpers: `fmtTime(iso)` → `"HH:MM"` (from the sim time string, without timezone conversion: just take characters 11–16). Hours: `x.toFixed(1) + ' h'`. Temp: `x.toFixed(1) + ' °C'`.

---

## 3. Step-by-step build plan (Phase 1: H0 → H8)

### Step B1 (H0 – H1): Skeleton + mock data
- Create the app, install everything, set up Tailwind and Leaflet CSS.
- `mock/state.json`: copy the State example from master 6.9 and expand it to **12 crates and 3 trucks** using the IDs, products, trucks and destinations from master 6.5's seed table (C-001 has `truck_id: null` and sits at WH-1). Use the coordinates from master 6.2. Give C-003 status `at_risk` with ~29 h left, so it ranks first in FEFO.
- `mock/locations.json`: `{ "locations": [...master 6.2...], "trucks": [...trucks.json...], "products": {...master 6.1...} }`.
- `App.jsx` layout (desktop 1366×768 minimum, 1920×1080 ideal):
  ```
  ┌──────────────────────────── Header (h-14) ─────────────────────────────┐
  │ FreshSense · subtitle · tabs [Live Map | Crates | Analytics] · clock · ●│
  ├────────────────────────────────────────────┬───────────────────────────┤
  │                                            │ Right panel (w-[34%])      │
  │            Map (flex-1)                    │  EventFeed (top half)      │
  │                                            │  DispatchTables (bottom)   │
  ├────────────────────────────────────────────┴───────────────────────────┤
  │ ControlPanel (h-20, always visible on every tab)                        │
  └─────────────────────────────────────────────────────────────────────────┘
  JourneyDrawer = right slide-over (w-[680px], full height) when a crate is selected
  ```
- App state: `selectedCrateId` (string | null), `activeTab` ('map' | 'crates' | 'analytics').

**Done when:** the page renders the layout with the mock data. Push.

### Step B2 (H1 – H3): MapView (the most important component)
- `MapContainer`: center `[12.97, 77.64]`, zoom `11`, `className="h-full w-full"`.
- `TileLayer`: url `https://tile.openstreetmap.org/{z}/{x}/{y}.png`, attribution `&copy; OpenStreetMap contributors` (CARTO basemaps now require an API key). (If offline, tiles fail but markers and lines still draw. That's acceptable.)
- **Location markers:** one `Marker` per location with `L.divIcon` (avoids Leaflet's broken default marker images):
  ```js
  L.divIcon({ className: '', html: `<div class="loc-icon loc-${type}">${TYPE_ICONS[type]}</div>`, iconSize: [30, 30], iconAnchor: [15, 15] })
  ```
  CSS: `.loc-icon` = white circle 30px, shadow, centered emoji 16px. Warehouses 36px with a red (`BRAND_RED`) border. The popup shows the name, type label, `min_hours_needed`, and demand per product.
- **Trucks:** a `Marker` at `truck.lat/lng` with a divIcon `🚚` in a 36px circle whose **border colour = the worst status among its crates** (use `STATUS_ORDER` to compare), plus a small label with the truck name underneath. Tooltip: driver, compressor state (`❄️ OK` / `⚠️ FAILED`), door state.
  - Smooth movement: add CSS `.leaflet-marker-icon.truck-icon { transition: transform 1s linear; }` (give the truck divIcon `className: 'truck-icon'`). During zoom, disable it: on the map's `zoomstart` add class `zooming` to the map container and remove it on `zoomend`; CSS `.zooming .truck-icon { transition: none !important; }`.
  - Truck popup: a list of its crates (emoji, id, coloured status dot, hours left, destination area), each with an **"Open journey"** button → `setSelectedCrateId(id)`.
- **C-001** (no truck): a small marker next to WH-1 showing `🥛 C-001 LIVE TAG` with a status-coloured border. Click → open the journey.
- **Route lines:** for each truck, a `Polyline` with `positions={truck.route_points}`, `color={truck.color}`, `weight={4}`, `opacity={0.8}`.
- **Legend** (bottom-left overlay): icons + status colours.

**Done when:** with mock data, the map shows all 22 locations, 3 trucks with routes, and C-001; popups work.

### Step B3 (H3 – H4): Right panel
**`EventFeed.jsx`**: merges `state.redirects` and `state.alerts` into one list sorted by `ts` (newest first, max 25 items). Skip alerts of type `rerouted`, `donated` and `discarded`, because the redirect card already shows those events.
- Redirect item (larger card, tinted by decision: REDIRECT = orange-50, DONATE = pink-50, DISCARD = gray-100):
  `🔄 C-003 Chicken → Blinkit Dark Store – Whitefield (demo)` / reason text (small) / `20 kg saved · 23 min away`. Click → open the journey.
- Alert item (one line): icon by type (`temp_excursion` 🌡️, `door_open` 🚪, `shock` 💥, `compressor_fail` ❄️, `status_change` ⚠️, `rerouted` 🔄, `donated` ❤️, `discarded` 🗑️, `delivery_rejected` ❌), `HH:MM`, message. Severity colour on the left border (info blue, warning amber, critical red).

**`DispatchTables.jsx`**: two tables side by side, titled **"Old way: FIFO"** and **"FreshSense: FEFO"**.
- Columns: `#`, Crate (emoji + id), Hours left (coloured by status), Destination (area name only, e.g. "Rajajinagar").
- FIFO rows with `would_be_rejected: true` get a red background and the badge `❌ would be rejected`.
- FEFO rows for crates that were redirected show `🔄` and their new destination.
- When a row's rank changes between updates, flash it yellow for 1.5 s (keep the previous ranks in a `useRef`).
- Footer: `FIFO would reject X crates · FreshSense: 0` (X = count of `would_be_rejected`).

**Toasts** (`react-hot-toast`, `<Toaster position="top-center" />`): for each item in `state.new_redirects` show a toast (`🔄 C-003 rerouted to Blinkit Whitefield`, 5 s). For each `new_alerts` item with severity `critical`, show a red toast. Show warning alerts only if they're `temp_excursion` (to avoid noise). Deduplicate by `id` using a `Set` in a `useRef`, so a toast never shows twice.

### Step B4 (H4 – H5): ControlPanel + api.js
`api.js`: one function per endpoint in master 6.8:
```js
const post = (path, body) => fetch(API_BASE + path, { method: 'POST',
  headers: { 'Content-Type': 'application/json' }, body: body ? JSON.stringify(body) : undefined })
  .then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
export const heat = id => post(`/api/simulate/heat/${id}`);
export const shock = id => post(`/api/simulate/shock/${id}`);
export const door = tid => post(`/api/simulate/door/${tid}`);
export const compressorFail = tid => post(`/api/simulate/compressor/${tid}/fail`);
export const compressorFix = tid => post(`/api/simulate/compressor/${tid}/fix`);
export const simControl = body => post('/api/sim/control', body);   // {paused} or {minutes_per_tick}
export const resetDemo = () => post('/api/demo/reset');
export const tagReading = body => post('/api/tag/reading', body);
export const getJourney = id => fetch(`${API_BASE}/api/crates/${id}/journey`).then(r => r.json());
export const getAnalytics = () => fetch(`${API_BASE}/api/analytics`).then(r => r.json());
export const getLocations = () => fetch(`${API_BASE}/api/locations`).then(r => r.json());
export const getState = () => fetch(`${API_BASE}/api/state`).then(r => r.json());
```
**ControlPanel layout** (left → right, big readable buttons, `text-sm font-semibold`):
1. **Crate group:** a dropdown of active crates (`C-003 🍗 Chicken – T-2`), **default selection C-003**. Buttons `🔥 Heat crate` and `💥 Shock crate`.
2. **Truck group:** a dropdown of trucks, **default T-3**. Buttons `🚪 Open door`, then `❄️ Compressor fail` or `✅ Fix compressor` (one toggle button driven by `truck.compressor_ok`).
3. **Simulation group:** `▶ Resume` / `⏸ Pause` (one toggle driven by `state.paused`; when paused, make the Resume button pulse green so the presenter doesn't forget), a speed select (`1, 2, 5, 10 min/tick`, current value from `state.minutes_per_tick`), and `🔄 Reset demo` (asks `confirm()` first).
4. **Live tag:** a button `📡 Live tag` that opens `LiveTagSlider` as a popover.

Every button shows a quick success toast or an error toast if the request fails.

**`LiveTagSlider.jsx`** (fallback for when Wokwi doesn't work): a temperature slider −2…35 °C (default 4), humidity 40…100 (default 88), VOC 0…500 (default 60), a door toggle, and a switch **"Send as live tag"**. While the switch is on, call `tagReading({crate_id:'C-001', temp_c, humidity, voc_index, door_open, source:'slider'})` every 2 s with `setInterval`, and clear it on unmount or switch off.

### Step B5 (H5 – H6): Live data + redirect animation
**`hooks/useLiveState.js`** returns `{ state, connection }` where `connection` ∈ `'live' | 'polling' | 'offline' | 'mock'`:
- If `USE_MOCK`: return the mock state, `connection='mock'`.
- Else open a WebSocket to `WS_URL`. `onmessage` → `JSON.parse` → if `data.type === 'state'` → `setState(data)`.
- On close/error: reconnect with backoff 1 s, 2 s, 4 s (max 4 s). After **3 failed attempts**, also start polling `getState()` every 2 s (`connection='polling'`) while still retrying the WS every 10 s. When the WS reconnects, stop polling.
- Also fetch `getLocations()` once at startup (with a fallback to `mock/locations.json` if it fails).

Header connection dot: green "Live", amber "Polling", red "Offline", grey "Mock".

**Redirect animation in MapView** (this is the demo's money shot):
- Keep `recentRedirects` in state: for each new item in `state.new_redirects` (dedupe by id), store `{id, from_point, oldDest: [lat,lng] of from_location_id, newDest: [lat,lng] of to_location_id, decision, expiresAt: Date.now() + 20000}`.
- For each active one, draw:
  - the **old route**: a `Polyline` from `from_point` to `oldDest`, `color '#9CA3AF'`, `dashArray '8 8'`, `weight 3`;
  - a **highlight** on the new route: a `Polyline` from `from_point` to `newDest`, `color` = `#F97316` for REDIRECT or `#DB2777` for DONATE, `weight 7`, `opacity 0.9`, with CSS class `route-glow` (keyframe animation pulsing opacity 0.5↔1);
  - a **pulsing ring** on the new destination: a `CircleMarker` radius 18 with class `pulse-ring` (CSS animation scaling and fading).
- Remove expired items with a 1 s interval.
- Optional nice touch: `map.flyTo(newDest, 12, {duration: 1.5})` on a redirect, then fly back after 6 s (add a "Follow redirects" checkbox in the legend, default on).

**Done when (H6):** with the real backend, Reset → Resume → Heat C-003 produces an excursion toast, then a reroute toast, then the grey dashed old route, the glowing new route and a pulsing ring on the Blinkit store, and the FEFO/FIFO tables update.

### Step B6 (H6 – H7): Basic Journey drawer
`JourneyDrawer.jsx` opens when `selectedCrateId` is set. Fetch `getJourney(id)` on open and **re-fetch every 5 s** while open.
- **Phase 1 version:** a header (emoji, id, product, status badge, close ✕), a summary row (Freshness ring, hours left, temp, humidity, destination; if redirected, show `Original: X → Now: Y` with the reason), and **one recharts `LineChart`** of `readings`: X = `ts` formatted `HH:MM`, left Y = `temp_c`, right Y = `humidity`. Add a `ReferenceLine y={product.max_safe_c}` in red, dashed, labelled "safe limit".
- Esc closes the drawer.

### Step B7 (H7 – H8): Freeze + rehearse
Feature freeze at H7:15. Rehearse the Evaluation 1 demo with A and C. Check the layout on the presentation laptop's resolution. Make browser zoom 90% if the bottom bar doesn't fit.

---

## 4. Phase 2 (H8 → H16)

### Step B8 (H8:30 – H10:30): Full Journey Report
Inside `JourneyDrawer`, below the summary:
1. **Blame banner:** `journey.blame.text` in a red-50 box with 🔎 (or a green box if `share_pct == 0`).
2. **Temperature chart (recharts `ComposedChart`, height 220):**
   - `ReferenceArea y1={-5} y2={product.max_safe_c}` filled green, opacity 0.08 (safe band);
   - one `ReferenceArea x1={exc.start} x2={exc.end}` per excursion, filled red, opacity 0.12 (for x matching, use the raw `ts` strings as the X `dataKey` and format ticks with `fmtTime`);
   - `Line dataKey="temp_c"` with dots off;
   - a red dashed `ReferenceLine` at `max_safe_c`.
3. **Humidity chart** (height 140): `Line dataKey="humidity"`.
4. **Freshness chart** (height 160): `Area dataKey="freshness_score"`, Y 0–100, with horizontal reference lines at 70/40/15 coloured like the statuses.
5. **Stage table:** columns `Stage | Where | Time | Avg °C | Max °C | Avg RH | Min above limit | Life used (h) | Extra loss (h)`. Highlight the blamed stage's row in red-50. Show times as `HH:MM–HH:MM`, durations as `1 h 20 min`.
6. **Excursions list:** `🔥 40 min at up to 18.3 °C · Loading dock · 21:00–21:40`.
7. Footer: `Picked up {picked_up_at} · Total life {total_life_h} h · Used {life_used_h} h · Extra loss from heat {extra_loss_h} h`.

### Step B9 (H10:30 – H12:00): Crates tab + Analytics tab
**`CratesTab.jsx`**: a filter row (status chips + product chips), then a grid of `CrateCard` (4 columns at 1366 px).

`CrateCard`: 4px left border in the status colour, the emoji and id, `FreshnessRing` (SVG circle, stroke in the status colour, number in the centre), hours left (big), temp/humidity/VOC (small), truck → destination area, badges `📡 LIVE TAG` (C-001), `🔄 Redirected`, `SPOILED` (whole card grey, opacity 60%). Click → journey.

**`AnalyticsTab.jsx`** (fetch `getAnalytics()` on open and every 5 s):
1. **Impact KPI tiles:** Crates redirected, Donated, kg saved, Rejections avoided, Deliveries completed, Deliveries rejected. Big numbers.
2. **"Where freshness is lost — by truck":** recharts horizontal `BarChart` of `hours_lost_by_truck` (`extra_loss_h`), with the label `name · driver`. Bar colour = the truck colour. Note: "includes last 7 days (demo data) + live".
3. **"By stage":** a bar chart of `hours_lost_by_stage`.
4. **Benchmark card:** if `benchmark` exists, show two grouped bars (FIFO vs FreshSense: rejected, kg wasted) plus the big text `{rejection_reduction_pct}% fewer rejections (simulation)`. Otherwise show the grey text "Benchmark pending".
5. **Model 1 card:** if `model_card.available`, show the dataset name (linked), task, validation method, **Accuracy** and **Macro F1** as big numbers, top features, and the images from `model_card.images` (`<img src="/model/confusion_matrix.png">`, hidden with `onError` if missing). Label it **"Validated on REAL lab data"**. Otherwise show "Model results pending".

### Step B10 (H12:00 – H13:30): Polish
- **Header:** `FreshSense` in bold with a red dot accent; subtitle "Per-crate freshness intelligence for the Eternal cold chain"; next to it, impact chips (`🔄 3 redirected · 60 kg saved · ❌→✅ 3 rejections avoided`); sim clock `🕒 12:06` and `⏸ Paused` when paused.
- **Map overlay (top-right):** a small "Today" impact counter card.
- A loading skeleton until the first state arrives.
- Spoiled crates are greyed out everywhere.
- Check at 1366×768 and 1920×1080. No horizontal scroll.
- Keyboard shortcuts for the presenter (optional): `H` heat the selected crate, `R` resume/pause.

### Step B11 (H13:30 – H14:00): Bug fixes, then **freeze at H14**
### H14 – H16: Rehearse. You drive the screen. Know the click order in master section 9 by heart.

---

## 5. Things you must NOT do
- Don't change field names. If the backend sends something different from master 6.9, tell A. Don't "fix" it silently in the frontend.
- Don't use Leaflet's default marker icons (broken image paths with Vite). Use `divIcon`.
- Don't forget `import 'leaflet/dist/leaflet.css'`.
- Don't use a map API that needs a key (Google Maps, Mapbox).
- Don't use official Eternal/Zomato/Blinkit logos. Use text and emoji icons.
- Don't re-create the Leaflet map on every state update. Only markers and lines should update. Keep `MapContainer` mounted once.
- Don't spam toasts. Dedupe by id and only show the types listed above.

## 6. Your checkpoints
| Time | You must have |
|---|---|
| H1 | Layout + mock data rendering, pushed |
| H3 | Map with locations, trucks, routes, popups (mock) |
| H4 | Right panel (feed + FEFO/FIFO) + toasts; connected to the live WS |
| H5 | Control panel working against the real backend |
| H6 | Redirect animation working live |
| H7 | Basic journey drawer; freeze |
| H12 | Full journey report, Crates tab, Analytics tab |
| H14 | Polished and frozen |
