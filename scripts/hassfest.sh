#!/usr/bin/env bash
set -euo pipefail
root=$(git rev-parse --show-toplevel)
exec docker run --rm --network none \
  --mount "type=bind,source=$root,target=/github/workspace,readonly" \
  ghcr.io/home-assistant/hassfest@sha256:4b1adfb1e0a37710af0390708eb8000230b80b2193ccffbeed0a901fa9765181
