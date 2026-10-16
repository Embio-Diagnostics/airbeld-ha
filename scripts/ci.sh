#!/usr/bin/env bash
set -euo pipefail
case "${HA_SELECT:-both}" in
  both|newest|floor) ;;
  *) printf 'Unknown HA_SELECT\n' >&2; exit 2 ;;
esac
uv run --frozen --offline ruff check .
uv run --frozen --offline ruff format --check .
if [[ ${HA_SELECT:-both} != floor ]]; then
  uv run --frozen --offline pytest -q
  uv run --frozen --offline python scripts/check_defects.py --verify-unfixed
fi
if [[ ${HA_SELECT:-both} != newest ]]; then
  uv run --frozen --offline --project ci/ha-min pytest -q tests
  uv run --frozen --offline --project ci/ha-min python scripts/check_defects.py --verify-unfixed
fi
uv run --frozen --offline python scripts/check_hacs_metadata.py
bash scripts/hassfest.sh
