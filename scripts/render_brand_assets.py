"""Render deterministic PNG brand assets from the project logo concept.

The SVG files remain the editable source. This script creates PNG fallbacks for
PowerPoint, GitHub previews, and Streamlit environments that prefer raster
assets.
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
BRAND_DIR = ROOT / "assets" / "brand"


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _draw_mark(size: int) -> Image.Image:
    scale = size / 512
    image = Image.new("RGBA", (size, size), (8, 17, 31, 255))
    draw = ImageDraw.Draw(image)

    def xy(points: tuple[float, ...]) -> tuple[int, ...]:
        return tuple(round(v * scale) for v in points)

    # Rounded background
    draw.rounded_rectangle(xy((0, 0, 512, 512)), radius=round(112 * scale), fill=(8, 17, 31, 255))

    # Cross-border orbit, approximated with layered arcs.
    for color, width, start, end in [
        ((56, 189, 248, 255), 18, 126, 320),
        ((34, 197, 94, 255), 18, 318, 468),
        ((167, 139, 250, 255), 18, 468, 620),
    ]:
        draw.arc(xy((99, 97, 411, 409)), start=start, end=end, fill=color, width=round(width * scale))
    for offset in range(0, 120, 40):
        draw.arc(
            xy((122, 132, 407, 404)),
            start=76 + offset,
            end=94 + offset,
            fill=(56, 189, 248, 180),
            width=round(10 * scale),
        )

    # Evidence hexagon.
    hex_points = [
        xy((257, 152)),
        xy((348, 205)),
        xy((348, 309)),
        xy((257, 362)),
        xy((166, 309)),
        xy((166, 205)),
    ]
    draw.polygon(hex_points, fill=(230, 250, 246, 255))
    draw.line(hex_points + [hex_points[0]], fill=(147, 197, 253, 255), width=round(8 * scale), joint="curve")

    # Connector hints.
    draw.line([xy((257, 183)), xy((257, 230))], fill=(30, 41, 59, 90), width=round(8 * scale))
    draw.line([xy((194, 292)), xy((231, 272))], fill=(30, 41, 59, 90), width=round(8 * scale))
    draw.line([xy((320, 292)), xy((283, 272))], fill=(30, 41, 59, 90), width=round(8 * scale))

    # Audit check.
    draw.line([xy((214, 260)), xy((246, 292)), xy((306, 222))], fill=(15, 118, 110, 255), width=round(20 * scale), joint="curve")

    # Agent nodes.
    for cx, cy, fill, stroke in [
        (257, 152, (56, 189, 248, 255), (224, 242, 254, 255)),
        (166, 309, (34, 197, 94, 255), (236, 253, 245, 255)),
        (348, 309, (167, 139, 250, 255), (243, 232, 255, 255)),
    ]:
        r = round(30 * scale)
        draw.ellipse((round(cx * scale) - r, round(cy * scale) - r, round(cx * scale) + r, round(cy * scale) + r), fill=fill, outline=stroke, width=round(8 * scale))

    return image


def render_assets() -> None:
    BRAND_DIR.mkdir(parents=True, exist_ok=True)
    mark = _draw_mark(1024)
    mark.save(BRAND_DIR / "crossagent-mark.png")

    lockup = Image.new("RGBA", (1600, 450), (8, 17, 31, 255))
    draw = ImageDraw.Draw(lockup)
    lockup.alpha_composite(_draw_mark(300), (62, 75))
    draw.text((430, 116), "Cross-Border Audit Agent", font=_font(70, bold=True), fill=(248, 250, 252, 255))
    draw.text((434, 195), "TRUSTED MULTI-AGENT AUDIT WORKFLOW", font=_font(30, bold=True), fill=(147, 197, 253, 255))
    draw.text(
        (434, 260),
        "Structured evidence · RAG provenance · Maker-Checker review · Risk reports",
        font=_font(31),
        fill=(203, 213, 225, 255),
    )
    lockup.save(BRAND_DIR / "crossagent-logo.png")


if __name__ == "__main__":
    render_assets()
    print(f"Rendered brand assets in {BRAND_DIR}")
