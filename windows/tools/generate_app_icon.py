from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from PIL import Image
from codexcontrol_windows.brand_icon import build_orbit_dial_icon

def build_icon(size: int) -> Image.Image:
    return build_orbit_dial_icon(size, accent="#7fe1a2")


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    assets_dir = root / "build-assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    output_path = assets_dir / "CodexControl.ico"

    base = build_icon(256)
    sizes = [(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (24, 24), (16, 16)]
    base.save(output_path, format="ICO", sizes=sizes)
    print(output_path)


if __name__ == "__main__":
    main()
