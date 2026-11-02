from __future__ import annotations

import sys
from dataclasses import dataclass


if sys.platform == "win32":
    UI_FONT = "Segoe UI Variable"
    DISPLAY_FONT = "Segoe UI Variable Display"
elif sys.platform == "darwin":
    UI_FONT = "SF Pro Text"
    DISPLAY_FONT = "SF Pro Display"
else:
    UI_FONT = "DejaVu Sans"
    DISPLAY_FONT = "DejaVu Sans"


@dataclass(frozen=True)
class Theme:
    name: str
    label: str
    background: str
    surface: str
    surface_high: str
    border: str
    text: str
    muted: str
    accent: str
    accent_soft: str
    heat: tuple[str, str, str, str, str]


THEMES = {
    "forest": Theme(
        "forest",
        "Forest",
        "#101512",
        "#171e1a",
        "#1e2822",
        "#2a362f",
        "#f2f7f4",
        "#8fa198",
        "#5ee28d",
        "#213b2b",
        ("#222b26", "#254f32", "#267443", "#35a95d", "#5ee28d"),
    ),
    "ocean": Theme(
        "ocean",
        "Ocean",
        "#0d141b",
        "#131d27",
        "#1a2835",
        "#283a49",
        "#f0f6fa",
        "#8da2b3",
        "#55c7f5",
        "#183648",
        ("#202d38", "#1c4960", "#176b8e", "#2398c5", "#55c7f5"),
    ),
    "violet": Theme(
        "violet",
        "Violet",
        "#131119",
        "#1b1723",
        "#251f30",
        "#382f46",
        "#f6f2fa",
        "#a499af",
        "#b98cff",
        "#35264d",
        ("#2a2532", "#453269", "#65449a", "#8a5bd0", "#b98cff"),
    ),
    "ember": Theme(
        "ember",
        "Ember",
        "#17110f",
        "#211815",
        "#2d211c",
        "#423129",
        "#fbf4ef",
        "#ad9a90",
        "#ff9a62",
        "#4a2c20",
        ("#30251f", "#613424", "#91472a", "#c86138", "#ff9a62"),
    ),
    "mono": Theme(
        "mono",
        "Mono",
        "#111111",
        "#191919",
        "#232323",
        "#353535",
        "#f5f5f5",
        "#999999",
        "#eeeeee",
        "#303030",
        ("#292929", "#4c4c4c", "#747474", "#aaaaaa", "#eeeeee"),
    ),
}
