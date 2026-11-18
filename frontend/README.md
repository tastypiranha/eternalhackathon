# FreshSense dashboard

React + Vite + Tailwind + TypeScript, based on the team's Figma Make design, wired to the FreshSense backend. Nothing is simulated in the browser: every number comes from the backend API.

## Run
```bash
npm install
npm run dev        # http://localhost:5173 (the backend must run on :8000)
```
To use another backend, set `VITE_API_BASE` in `.env` (see `.env.example`). If the backend isn't reachable, the app shows a waiting screen and retries every 3 s.

## Pages
| Page | What it does | Backend |
|---|---|---|
| **Shipment** (default) | Enter a product, packing age, printed expiry, origin hub, destination city, vehicle and disruptions → watch the tag's readings play back → at the destination warehouse, every outlet in the city is checked and the crate is routed to the best one. Includes 3 demo presets | `GET /api/shipments/options`, `POST /api/shipments/simulate` |
| Overview / Crates / Dispatch / Activity | The live fleet simulation (crates on trucks, FEFO vs FIFO, redirects, journey reports) | `WS /ws`, `GET /api/state`, `GET /api/crates/{id}/journey` |
| Analytics | Heat loss by truck/stage, impact, the model card (held-out results), the FIFO vs FreshSense benchmark | `GET /api/analytics` |
| Test lab | Held-out lab test cases + your own CSV readings | `GET /api/testcases`, `POST /api/testcases/run`, `POST /api/predict` |

Products, locations, trucks and assumptions are loaded from `GET /api/locations` and `GET /api/calibration` at startup (`src/demo/config.ts → initConfig`). `src/data/demo.json` only holds UI settings (speeds, colours, statuses).
