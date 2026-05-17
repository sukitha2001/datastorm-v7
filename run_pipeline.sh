#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQS="${SCRIPT_DIR}/requirements.txt"

echo "Setting up Python environment..."

if command -v uv &> /dev/null; then
    echo "  Using uv ($(uv --version 2>&1))"
    if [ ! -d "$VENV_DIR" ]; then
        uv venv "$VENV_DIR"
    fi
    source "${VENV_DIR}/bin/activate"
    uv pip install -r "$REQS"
else
    echo "  uv not found  falling back to pip + venv"
    if [ ! -d "$VENV_DIR" ]; then
        python3 -m venv "$VENV_DIR"
    fi
    source "${VENV_DIR}/bin/activate"
    pip install -r "$REQS"
fi

PYTHON="${VENV_DIR}/bin/python3"

echo "Phase 1: Exploratory Data Analysis (Simple)"
${PYTHON} "$SCRIPT_DIR/src/eda/eda_simple.py"

echo "Phase 2: Exploratory Data Analysis (Spatial)"
${PYTHON} "$SCRIPT_DIR/src/eda/eda_advanced.py"

echo "Phase 3: Turing Reaction-Diffusion Simulation"
${PYTHON} "$SCRIPT_DIR/src/gold/turing_rd.py"

echo "Phase 4: Latent Demand Estimation"
${PYTHON} "$SCRIPT_DIR/src/model/latent_demand.py"
