#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$REPO_ROOT/.env"
TEMPLATE_FILE="$REPO_ROOT/infra/secrets-template.env"

if [[ ! -f "$ENV_FILE" ]]; then
  cp "$TEMPLATE_FILE" "$ENV_FILE"
  echo "Created .env from template"
fi

PYTHON_EXE="${PYTHON_EXE:-python3}"
if [[ -f "$ENV_FILE" ]]; then
  while IFS='=' read -r key value; do
    [[ -z "$key" || "$key" =~ ^# ]] && continue
    if [[ "$key" == "PYTHON_EXE" && -n "$value" ]]; then
      PYTHON_EXE="$value"
    fi
  done < "$ENV_FILE"
fi

if [[ ! -d "$REPO_ROOT/.venv" ]]; then
  "$PYTHON_EXE" -m venv "$REPO_ROOT/.venv"
fi

"$REPO_ROOT/.venv/bin/python" -m pip install --upgrade pip
"$REPO_ROOT/.venv/bin/python" -m pip install -r "$REPO_ROOT/requirements.txt"
"$REPO_ROOT/.venv/bin/python" "$REPO_ROOT/scripts/seed_demo_data.py"

echo "Bootstrap completed successfully"
