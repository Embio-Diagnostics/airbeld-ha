set shell := ["bash", "-euo", "pipefail", "-c"]

# One local gate covers both ends; HA_SELECT is used by CI matrix jobs.
ci:
    bash scripts/ci.sh

test:
    uv run --frozen --offline pytest -q
    uv run --frozen --offline --project ci/ha-min pytest -q tests

dev:
    docker compose -f compose.yaml up --build -d

dev-staging:
    docker compose -f compose.yaml -f compose.staging.yaml up --build -d

dev-down:
    docker compose -f compose.yaml down

dev-staging-down:
    docker compose -f compose.yaml -f compose.staging.yaml down
