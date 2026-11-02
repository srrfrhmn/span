from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets"
SIZE = 1024


def font_path() -> Path | None:
    candidates = []
    if sys.platform == "win32":
        candidates.extend(
            [
                Path("C:/Windows/Fonts/seguibl.ttf"),
                Path("C:/Windows/Fonts/seguisb.ttf"),
            ]
        )
    elif sys.platform == "darwin":
        candidates.append(Path("/System/Library/Fonts/SFNSRounded.ttf"))
    else:
        candidates.append(Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"))
    return next((path for path in candidates if path.exists()), None)


def main() -> None:
    ASSETS.mkdir(exist_ok=True)
    image = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    margin = 72
    box = (margin, margin, SIZE - margin, SIZE - margin)
    draw.rounded_rectangle(box, radius=220, fill="#111111", outline="#3a3a3a", width=20)

    path = font_path()
    font = ImageFont.truetype(str(path), 610) if path else ImageFont.load_default()
    text = "s"
    bounds = draw.textbbox((0, 0), text, font=font)
    text_width = bounds[2] - bounds[0]
    text_height = bounds[3] - bounds[1]
    position = (
        (SIZE - text_width) / 2 - bounds[0],
        (SIZE - text_height) / 2 - bounds[1] - 24,
    )
    draw.text(position, text, font=font, fill="#f5f5f5")

    png_path = ASSETS / "span.png"
    ico_path = ASSETS / "span.ico"
    image.save(png_path, optimize=True)
    image.save(
        ico_path,
        format="ICO",
        sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (40, 40), (48, 48), (64, 64), (128, 128), (256, 256)],
    )
    print(f"Created {png_path} and {ico_path}")


if __name__ == "__main__":
    main()
