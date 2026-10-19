"""Credential-free local metadata checks, NOT full upstream HACS validation."""

import json
import struct
from pathlib import Path


def require(condition: object, message: str) -> None:
    """Fail even if Python assertions are disabled."""
    if not condition:
        raise SystemExit(message)


def main() -> None:
    """Validate local HACS and manifest fields and their referenced files."""
    root = Path(__file__).resolve().parents[1]
    hacs = json.loads((root / "hacs.json").read_text(encoding="utf-8"))
    component = root / "custom_components" / "airbeld"
    manifest = json.loads((component / "manifest.json").read_text(encoding="utf-8"))
    require(hacs["homeassistant"] == "2025.10.0", "HACS floor differs")
    require(hacs["content_in_root"] is False, "HACS layout differs")
    require(hacs["render_readme"] is True, "HACS readme disabled")
    require(hacs["name"] == manifest["name"] == "airbeld™", "Name differs")
    require(manifest["domain"] == "airbeld", "Domain differs")
    require(manifest["version"], "Missing version")
    require(manifest["config_flow"] is True, "Missing config flow")
    require(manifest["requirements"], "Missing requirements")
    for name in ("README.md", "LICENSE"):
        require((root / name).is_file(), name)
    for name in (
        "__init__.py",
        "config_flow.py",
        "strings.json",
        "translations/en.json",
    ):
        require((component / name).is_file(), name)
    json.loads((component / "strings.json").read_text())
    json.loads((component / "translations/en.json").read_text())
    for name in ("icon.png", "logo.png"):
        path = component / "brand" / name
        require(path.is_file(), f"Missing brand/{name}")
        data = path.read_bytes()
        require(
            data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR",
            f"Invalid brand/{name} PNG",
        )
        width, height = struct.unpack(">II", data[16:24])
        require(width > 0 and height > 0, f"Empty brand/{name}")
        if name == "icon.png":
            require(width == height, "Brand icon must be square")
    print("local HACS metadata and brand PNG assets: valid (not full HACS validation)")


if __name__ == "__main__":
    main()
