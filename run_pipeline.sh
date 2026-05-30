#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQS="${SCRIPT_DIR}/requirements.txt"

# ── Parse --start-from flag ─────────────────────────────────────
START_PHASE=1
while [[ $# -gt 0 ]]; do
    case "$1" in
        --start-from)
            START_PHASE="$2"
            shift 2
            ;;
        *)
            echo "Usage: $0 [--start-from N]"
            echo "  --start-from N   Start from phase N (1-10)"
            exit 1
            ;;
    esac
done

echo "Setting up Python environment..."

if command -v uv &> /dev/null; then
    echo "  Using uv ($(uv --version 2>&1))"
    if [ ! -d "$VENV_DIR" ]; then
        uv venv "$VENV_DIR"
    fi
    source "${VENV_DIR}/bin/activate"
    uv pip install -r "$REQS"
else
    echo "  uv not found — falling back to pip + venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    source "${VENV_DIR}/bin/activate"
    pip install -r "$REQS"
fi

PYTHON="${VENV_DIR}/bin/python3"
export PYTHONPATH="$SCRIPT_DIR"

should_run() {
    [ "$START_PHASE" -le "$1" ]
}

phase_header() {
    echo ""
    echo "============================================"
    echo "Phase $1: $2"
    echo "============================================"
}

if should_run 1; then phase_header 1 "BRONZE — Raw Ingestion"; ${PYTHON} "${SCRIPT_DIR}/pipeline/bronze_ingestion.py"; else echo "  [SKIP] Phase 1"; fi

if should_run 2; then phase_header 2 "SILVER — Data Quality & Cleaning"; ${PYTHON} "${SCRIPT_DIR}/pipeline/silver_cleaning.py"; else echo "  [SKIP] Phase 2"; fi

if should_run 3; then phase_header 3 "GOLD (POI) — Spatial Enrichment"; ${PYTHON} "${SCRIPT_DIR}/scraping/poi_processor.py"; else echo "  [SKIP] Phase 3"; fi

if should_run 4; then phase_header 4 "GOLD (RD) — Turing Reaction-Diffusion"; ${PYTHON} "${SCRIPT_DIR}/src/gold/turing_rd.py"; else echo "  [SKIP] Phase 4"; fi

if should_run 5; then phase_header 5 "GOLD (Merge) — Feature Assembly"; ${PYTHON} "${SCRIPT_DIR}/pipeline/gold_merger.py"; else echo "  [SKIP] Phase 5"; fi

if should_run 6; then phase_header 6 "MODEL — Latent Demand Estimation"; ${PYTHON} "${SCRIPT_DIR}/src/model/latent_demand.py"; else echo "  [SKIP] Phase 6"; fi

if should_run 7; then phase_header 7 "SPEND — Budget Optimization"; ${PYTHON} "${SCRIPT_DIR}/src/spend/optimizer.py"; else echo "  [SKIP] Phase 7"; fi

if should_run 8; then
    phase_header 8 "EXPORT — JSON + Web Assets"
    mkdir -p "${SCRIPT_DIR}/web/public/data"
    ${PYTHON} -c "
import pandas as pd, json, os

DATA = '${SCRIPT_DIR}'
PUBLIC = f'{DATA}/web/public/data'
RAW = f'{DATA}/data/raw'

# Export coordinates CSV with slight longitude shift (+0.01)
outlets_meta = pd.read_parquet(f'{DATA}/data/silver/outlets.parquet')
coords = pd.read_parquet(f'{DATA}/data/silver/coordinates.parquet')
merged_coords = outlets_meta[['Outlet_ID']].merge(coords, on='Outlet_ID', how='left')
merged_coords['Longitude'] = merged_coords['Longitude']
merged_coords.to_csv(f'{RAW}/outlet_coordinates.csv', index=False)
print(f'Coordinates CSV: {len(merged_coords)} rows')

# Convert predictions to JSON
pred_path = f'{DATA}/data/predictions/ctrl_freaks_predictions.csv'
if os.path.exists(pred_path):
    pred = pd.read_csv(pred_path)
    pred.to_json(f'{PUBLIC}/predictions.json', orient='records')
    pred.to_csv(f'{PUBLIC}/predictions.csv', index=False)
    print(f'Predictions: {len(pred)} rows')
else:
    print(f'  [WARN] Predictions not found: {pred_path}')

# Convert budget to JSON (with Spend_Type column)
budget_path = f'{DATA}/data/budget/ctrl_freaks_budget_mapping.csv'
if os.path.exists(budget_path):
    budget = pd.read_csv(budget_path)
    budget.to_json(f'{PUBLIC}/budget_allocations.json', orient='records')
    budget.to_csv(f'{PUBLIC}/budget_allocations.csv', index=False)
    print(f'Budget: {len(budget)} rows')
else:
    print(f'  [WARN] Budget not found: {budget_path}')

# Convert coordinates to JSON
coords_path = f'{RAW}/outlet_coordinates.csv'
if os.path.exists(coords_path):
    coords_df = pd.read_csv(coords_path)
    coords_df.to_json(f'{PUBLIC}/outlet_coordinates.json', orient='records')
    coords_df.to_csv(f'{PUBLIC}/outlet_coordinates.csv', index=False)
    print(f'Coordinates: {len(coords_df)} rows')
else:
    print(f'  [WARN] Coordinates not found: {coords_path}')

# ── Merge into single outlets.json (DIST_W* only) ──────────────
pred_df = pd.read_csv(f'{PUBLIC}/predictions.csv')
coord_df = pd.read_csv(f'{PUBLIC}/outlet_coordinates.csv')
master_df = pd.read_csv(f'{RAW}/outlet_master.csv')
budget_df = pd.read_csv(f'{DATA}/data/budget/ctrl_freaks_budget_mapping.csv') if os.path.exists(f'{DATA}/data/budget/ctrl_freaks_budget_mapping.csv') else None
txn_df = pd.read_csv(f'{RAW}/transactions_history_final.csv')

# Derive each outlet's primary distributor (most common in transactions)
dist_map = (
    txn_df.groupby('Outlet_ID')['Distributor_ID']
    .agg(lambda x: x.mode().iloc[0] if not x.mode().empty else None)
    .reset_index()
)

merged = pred_df.merge(coord_df, on='Outlet_ID', how='left') \
                .merge(master_df, on='Outlet_ID', how='left') \
                .merge(dist_map, on='Outlet_ID', how='left')

if budget_df is not None:
    merged = merged.merge(
        budget_df[['Outlet_ID', 'Trade_Spend_LKR']], on='Outlet_ID', how='left'
    )
else:
    merged['Trade_Spend_LKR'] = 0

merged['Trade_Spend_LKR'] = merged['Trade_Spend_LKR'].fillna(0).round(2)
merged['Cooler_Count'] = merged['Cooler_Count'].fillna(0).astype(int)

# Keep only Western Province distributors
merged = merged[merged['Distributor_ID'].str.startswith('DIST_W', na=False)].copy()

# Fill NaN in string/object columns to avoid invalid JSON (NaN is not valid JSON)
for col in merged.select_dtypes(include='object').columns:
    merged[col] = merged[col].fillna('')
for col in merged.select_dtypes(include=['float64', 'int64']).columns:
    merged[col] = merged[col].fillna(0)

out = merged[[
    'Outlet_ID', 'Latitude', 'Longitude',
    'Outlet_Type', 'Outlet_Size', 'Cooler_Count',
    'Distributor_ID',
    'Maximum_Monthly_Liters', 'Trade_Spend_LKR',
]].to_dict(orient='records')

with open(f'{PUBLIC}/outlets.json', 'w') as f:
    json.dump(out, f, indent=2)

print(f'Merged outlets.json: {len(out)} rows (DIST_W* only)')

manifest = []
for filename in [
    'outlets.json',
    'predictions.json',
    'budget_allocations.json',
    'outlet_coordinates.json',
]:
    file_path = f'{PUBLIC}/{filename}'
    if os.path.exists(file_path):
        try:
            with open(file_path) as f:
                row_count = len(json.load(f))
        except Exception:
            row_count = 0
        manifest.append({
            'filename': filename,
            'row_count': row_count,
            'bytes': os.path.getsize(file_path),
            'generated_at': pd.Timestamp.utcnow().isoformat(),
        })

with open(f'{PUBLIC}/analysis_manifest.json', 'w') as f:
    json.dump({'datasets': manifest}, f, indent=2)

print(f'Analysis backend manifest: {len(manifest)} datasets')
"
else echo "  [SKIP] Phase 8"; fi

if should_run 9; then
    phase_header 9 "OUTPUT — Validation"
    echo "  Checking predictions..."
    if [ -f "${SCRIPT_DIR}/data/predictions/ctrl_freaks_predictions.csv" ]; then
        LINES=$(wc -l < "${SCRIPT_DIR}/data/predictions/ctrl_freaks_predictions.csv")
        echo "  predictions: $((LINES - 1)) rows"
    else
        echo "  [WARN] predictions not found"
    fi
    if [ -f "${SCRIPT_DIR}/data/budget/ctrl_freaks_budget_allocations.csv" ]; then
        LINES=$(wc -l < "${SCRIPT_DIR}/data/budget/ctrl_freaks_budget_allocations.csv")
        echo "  budget_allocations: $((LINES - 1)) rows"
    else
        echo "  [WARN] budget_allocations not found at data/budget/"
    fi
    if [ -f "${SCRIPT_DIR}/web/public/data/outlets.json" ]; then
        echo "  outlets.json: present"
    else
        echo "  [WARN] outlets.json not found"
    fi
else
    echo "  [SKIP] Phase 9"
fi

echo ""
echo "============================================"
echo "Pipeline complete!"
echo "============================================"
