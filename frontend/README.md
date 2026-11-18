# FreshSense dashboard

React + Vite + Tailwind + react-leaflet + recharts. Implements Person B's plan (`02_PERSON_B_FRONTEND.md`).

## Run
```bash
npm install
npm run dev            # http://localhost:5173  (backend must run on :8000)
```
`.env` sets `VITE_API_BASE`, `VITE_WS_URL`, and `VITE_USE_MOCK` (`true` = run with `src/mock/state.json` and no backend).

## Screens
- **Live Map:** the Eternal network, moving trucks, and routes. A redirect shows as a grey dashed old route, a glowing new route, and a pulsing destination, and the map flies to it.
- **Right panel:** the redirect and alert feed, and the FIFO vs FreshSense FEFO tables (red ❌ = FIFO would deliver a crate that gets rejected).
- **Control panel:** heat/shock a crate, door/compressor on a truck, pause/resume, speed, reset, and the 📡 Live tag slider (backup for Wokwi).
- **Journey drawer:** click any crate, truck popup row, or feed card. Shows the summary, blame line, temperature/humidity/freshness charts (Full journey or This trip), stage table, and excursions.
- **Crates** tab (cards) and **Analytics** tab (hours lost by truck/stage, impact, benchmark, Model 1 card).

Map tiles: OpenStreetMap (`tile.openstreetmap.org`, no key). CARTO basemaps now require an API key, so they aren't used.
