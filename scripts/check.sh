#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Checking Python syntax"
python -m compileall -q tunnel_toggle

echo "==> Running Ruff lint checks"
python -m ruff check .

echo "==> Checking Ruff formatting"
python -m ruff format --check .

echo "==> Running mypy"
python -m mypy tunnel_toggle

echo "==> Running tests"
python -m pytest

echo "==> Checking application startup"
output="$(python -m tunnel_toggle)"

if [[ "$output" != "Tunnel Toggle 0.1.0a1" ]]; then
    echo "Unexpected application output: $output" >&2
    exit 1
fi

echo "==> Checking Git whitespace"
git --no-pager diff --check
git --no-pager diff --cached --check

echo "All checks passed."
