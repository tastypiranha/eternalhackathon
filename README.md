# FreshSense

**Per-crate freshness intelligence for the Eternal cold chain.**
A tag on every crate senses temperature, humidity, gas and shocks. FreshSense predicts each crate's **hours of shelf life left**, keeps its **full journey history**, and when a crate can't reach its destination fresh enough, **redirects it on a live map** to the best place in the Eternal network: a Blinkit dark store, a nearer Zomato restaurant, or a Feeding India partner.

Built for the Eternal hackathon, track *Reducing Food Wastage through Data & Analytics*.

## Run it
**Backend** (Python 3.11+):
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cd backend
FRESHSENSE_MQTT_TOPIC="freshsense/<TEAMCODE>/tag/C-001" uvicorn main:app --port 8000
```
**Dashboard** (Node 20+), in a second terminal:
```bash
cd frontend && npm install && npm run dev
```
Open http://localhost:5173 → **🔄 Reset demo** → **▶ Resume** → **🔥 Heat crate**.

**Virtual tag:** see `firmware/wokwi/README.md`.
**Tests:** `cd backend && python -m pytest -q` (13 tests).

## Repo
| Folder | What |
|---|---|
| `backend/` | FastAPI: freshness engine, simulator, redirect rules, journey report, analytics, MQTT |
| `frontend/` | React dashboard: live map, FIFO vs FEFO, control panel, journey report, analytics |
| `firmware/wokwi/` | ESP32 tag firmware + Wokwi circuit |
| `notebooks/` | Model 1 training on real e-nose data (`python -I notebooks/model1_train.py`) |
| `pitch/` | demo scripts, Q&A sheet, QA checklist |
| `docs/plan/` | the 16-hour build plan: master plan + one brief per team member |

**Pitch deck:** https://claude.ai/artifact/Topph2cTRBxW16DvgFd4yV (private until shared from its Share menu)

**Model 1 dataset:** download the ZIP from the Mendeley link below and unzip the `TS*.csv` files into `data/raw/beef_enose/` (git-ignored), then run `python -I notebooks/model1_train.py`.

## Data: what's real and what's simulated
| | Source |
|---|---|
| **Real** | Model 1: [Electronic nose dataset for beef quality monitoring (Wijaya et al., Mendeley Data)](https://data.mendeley.com/datasets/mwmhh766fc). 10,800 readings, 5 beef cuts. Leave-one-cut-out results: 63 % exact stage (chance 25 %), 96 % within one stage, 74 % spoiled vs sellable |
| **Literature** | Arrhenius shelf-life parameters per product, cross-checked with [USDA FoodKeeper](https://catalog.data.gov/dataset/fsis-foodkeeper-data) |
| **Simulated** | Fleet, crates, temperatures, orders, deliveries; the FIFO vs FreshSense benchmark (66 % fewer rejections, simulation only) |
| **Demo data** | All Bengaluru locations, trucks and drivers are labelled "(demo)" |

Map © OpenStreetMap contributors.

## Team
_Add names here._
