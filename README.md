# Ctrl Freaks — DataStorm 7.0

**Latent Demand Estimation Pipeline for Sri Lanka Beverage Distribution (January 2026 Forecast)**

Built for [DataStorm 7.0](https://octave.lk/datastorm/) by Octave John Keells Group. Estimates uncapped monthly demand for 20,000 outlets and allocates a LKR 5M promotional budget across Western Province.

---

## Project Structure

```
├── data/
│   ├── raw/            # Source CSVs (transactions, outlet master, coordinates, etc.)
│   ├── bronze/         # Ingestion — untouched parquet snapshots + manifest.json
│   ├── silver/         # Cleaned parquet + dq_report.json + rejected_records
│   ├── gold/           # Feature-engineered model_ready.parquet + POI data + RD grid
│   └── output/         # Final CSVs
├── src/
│   ├── bronze/ingest.py
│   ├── silver/dq_checks.py + clean.py
│   ├── gold/poi_scraper.py + turing_rd.py + features.py
│   ├── model/tobit_sfa.py
│   ├── spend/optimizer.py
│   └── xai/explainer.py
├── web/                # Next.js 16 outlet dashboard
│   ├── app/            # 4 static routes
│   │   ├── page.tsx          # Overview (metric cards + budget table)
│   │   ├── map/page.tsx      # Western Province outlet map (clustered)
│   │   ├── budget/page.tsx   # Sorted allocation table
│   │   └── settings/page.tsx # Kafka + GenAI + pipeline config
│   ├── components/     # shadcn/ui + Leaflet map components
│   ├── public/data/    # Pipeline-generated JSON files for the web app
│   └── package.json
├── run_pipeline.sh
├── pitch_deck.html     # Executive pitch deck (standalone HTML)
└── README.md
```

---

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 20+
- pnpm 9+

### Setup

```bash
# Python
uv sync                    # or: pip install -r requirements.txt

# Web app
pnpm install --prefix web
```

### Run the Pipeline

```bash
chmod +x run_pipeline.sh
./run_pipeline.sh
```

Supports a `--start-from N` flag to resume from a specific phase:

| Flag | Description |
|------|-------------|
| `--start-from 1` | Bronze ingestion (default) |
| `--start-from 2` | Silver cleaning |
| `--start-from 3` | Gold POI spatial enrichment |
| `--start-from 4` | Gold feature assembly |
| `--start-from 5` | Gold EDA prep |
| `--start-from 6` | Turing reaction-diffusion |
| `--start-from 7` | Latent demand model |
| `--start-from 8` | Budget optimization |
| `--start-from 9` | JSON/web asset export |
| `--start-from 10` | Output validation |

Outputs go to `data/output/teamname_predictions.csv` and `data/output/teamname_budget_allocations.csv`. Phase 9 automatically writes JSON files to `web/public/data/` for the dashboard.

### Run the Web App

```bash
pnpm run dev --prefix web    # → http://localhost:3000
```

Build for production:

```bash
pnpm run build --prefix web
pnpm run start --prefix web
```

---

## Web App — Outlet Intelligence Dashboard

4 static pages rendered via Next.js App Router:

| Route | Page | Content |
|-------|------|---------|
| `/` | Overview | 6 metric cards + strategy summary + budget DataTable |
| `/map` | Outlet Map | Western Province ~8,900 outlets, clustered CircleMarkers with popups |
| `/budget` | Budget Allocation | Sorted table of 1,799 allocations with LKR + share % |
| `/settings` | Settings | Kafka streaming config, GenAI API keys, pipeline settings |

**Stack**: Next.js 16 + shadcn/ui + lucide-react + react-leaflet + MarkerClusterGroup + @tanstack/react-table

**Map performance**: Mounted once in the persistent layout (`AppShell`), hidden off-screen on non-map pages using `position: absolute; left: -9999px`. Navigates instantly — no re-initialization, no jank. A `ResizeObserver` auto-invalidates Leaflet on layout transitions.

---

## Pipeline Architecture

**Medallion layers**: Raw → Bronze → Silver → Gold → Model → Output.

| Agent | Layer | Purpose |
|-------|-------|---------|
| A | Bronze | Forensic ingestion — zero transformations, schema manifest |
| B | Silver | 8 DQ check functions, quarantine pattern, flatline forensic check |
| C | Gold | OSM POI scraping (500m/1000m/2000m radii), Gray-Scott Turing RD, feature engineering |
| D | Model | Tobit censored regression + SFA + peer-group uplift ensemble |
| E | Spend | LKR 5M budget optimizer (tiered allocation by spend type) |
| F | XAI | LLM-generated per-outlet explanations |

---

## Key Features

- **Turing Reaction-Diffusion**: Gray-Scott RD simulation at 1000 timesteps produces a `rd_demand_pressure` spatial activator feature per outlet grid cell.
- **Censoring threshold logic**: Per-outlet constraint ceiling derived from `constraint_score` and `flatline_flag`.
- **Ensemble prediction**: 50% Tobit + 30% SFA + 20% peer 90th percentile, adjusted by January seasonality.
- **Spend optimizer**: Splits LKR 5M into 3 tiers (45/35/20) by incremental upside, capped at LKR 150K/60K/10K per outlet.
- **Spend type assignment**: Discount / Merchandising / Promotional based on outlet type, flatline flag, and cooler count.

---

## Tech Stack

| Domain | Tools |
|--------|-------|
| **Pipeline** | Python, pandas, numpy, scipy, statsmodels |
| **Spatial** | GeoPandas, Overpass API, Shapely |
| **Web** | Next.js 16, shadcn/ui, lucide-react, react-leaflet, MarkerClusterGroup, @tanstack/react-table |
| **Packaging** | pnpm, uv, pyproject.toml |
| **Reporting** | Pitch deck (standalone HTML) |

---

## Output Files

| File | Rows | Columns |
|------|------|---------|
| `teamname_predictions.csv` | 20,000 | Outlet_ID, Maximum_Monthly_Liters |
| `teamname_budget_allocations.csv` | 1,799 | Outlet_ID, Trade_Spend_LKR, Spend_Type, Outlet_Type |
| `teamname_budget_simple.csv` | 1,799 | Outlet_ID, Trade_Spend_LKR |

---

## Team — Ctrl Freaks

- **Sukitha Rathnayake** — MLOps, DQ Forensics, Ensemble Logic
- **Vidura Gunawardana** — Pipeline Architecture, Turing RD, Tobit Modeling, Web App
