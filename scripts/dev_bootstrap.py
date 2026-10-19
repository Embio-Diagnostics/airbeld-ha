"""Boot a development-only HA; choose staging in memory, not tracked source."""

import os
import runpy
import sys
from pathlib import Path

from custom_components.airbeld import const


def main() -> None:
    """Refuse unknown modes and leave credentials entirely to HA onboarding."""
    mode = os.environ["AIRBELD_DEV_MODE"]
    if mode not in {"local", "staging"}:
        raise SystemExit("Unknown development mode")
    config = Path("/config/configuration.yaml")
    if not config.exists():
        config.write_text("default_config:\n", encoding="utf-8")
    if mode == "staging":
        const.DEFAULT_API_BASE = "https://airbeld-staging-api-fmb3htfqfua5hhgk.westeurope-01.azurewebsites.net"
    sys.argv = ["hass", "--config", "/config"]
    runpy.run_module("homeassistant", run_name="__main__")


if __name__ == "__main__":
    main()
