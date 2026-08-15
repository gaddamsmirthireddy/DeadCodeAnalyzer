#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r backend/requirements.txt
