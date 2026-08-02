#!/usr/bin/env bash

set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")/.."

echo "==> Checking Python syntax"
python3 -m compileall -q tunnel_toggle

echo "==> Checking application startup"
output="$(python3 -m tunnel_toggle)"

if [[ "$output" != "Tunnel Toggle 0.1.0a1" ]]; then
    echo "Unexpected application output: $output" >&2
    exit 1
fi

echo "==> Checking Git whitespace"
git --no-pager diff --check

echo "All available checks passed."
