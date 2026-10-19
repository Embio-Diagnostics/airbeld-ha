"""Reproduce the integration brand PNGs from the repository's approved wordmark."""

from pathlib import Path

from PIL import Image


def main() -> None:
    """Keep the logo intact and use its cyan initial for a square icon."""
    root = Path(__file__).resolve().parents[1]
    brand = root / "custom_components/airbeld/brand"
    source = Image.open(root / "images/airbeld.png").convert("RGBA")
    source.save(brand / "logo.png")
    initial = source.crop((0, 52, 82, 128))
    icon = Image.new("RGBA", (128, 128))
    icon.alpha_composite(initial, (23, 26))
    icon.save(brand / "icon.png")


if __name__ == "__main__":
    main()
