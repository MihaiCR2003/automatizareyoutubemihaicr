"""Genereaza un thumbnail 1080x1920 pe baza personajului si a unui titlu."""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from src.config import CONFIG, path_from_root

_EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002190-\U000021FF"
    "\U00002B00-\U00002BFF"
    "\U0000FE00-\U0000FE0F"
    "]+",
    flags=re.UNICODE,
)


def _strip_emojis(text: str) -> str:
    return _EMOJI_PATTERN.sub("", text).strip()


def generate_thumbnail(title: str, output_path: Path, character_image: str | None = None) -> Path:
    width = CONFIG["video"]["width"]
    height = CONFIG["video"]["height"]
    char_cfg = CONFIG["character"]

    bg_dir = path_from_root(CONFIG["background"]["assets_dir"])
    bg_candidates = list(bg_dir.glob("*.png")) + list(bg_dir.glob("*.jpg"))

    if bg_candidates:
        canvas = Image.open(bg_candidates[0]).convert("RGBA").resize((width, height))
    else:
        canvas = Image.new("RGBA", (width, height), (20, 20, 30, 255))

    chars_dir = path_from_root(char_cfg["assets_dir"])
    char_file = character_image or char_cfg["positions"][0]["file"]
    char_img = Image.open(chars_dir / char_file).convert("RGBA")

    scale = char_cfg["default_scale"]
    new_width = int(width * scale)
    ratio = new_width / char_img.width
    char_img = char_img.resize((new_width, int(char_img.height * ratio)))

    canvas.alpha_composite(
        char_img, ((width - char_img.width) // 2, height - char_img.height)
    )

    draw = ImageDraw.Draw(canvas)
    font = None
    for font_path in (
        "arialbd.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            font = ImageFont.truetype(font_path, 90)
            break
        except OSError:
            continue
    if font is None:
        font = ImageFont.load_default()

    _draw_wrapped_text(draw, _strip_emojis(title), font, width, padding=60, fill=(255, 255, 255, 255))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(output_path)
    return output_path


def _draw_wrapped_text(draw, text, font, max_width, padding, fill):
    words = text.split()
    lines, current = [], ""

    for word in words:
        test_line = f"{current} {word}".strip()
        bbox = draw.textbbox((0, 0), test_line, font=font)
        if bbox[2] - bbox[0] <= max_width - 2 * padding:
            current = test_line
        else:
            lines.append(current)
            current = word
    if current:
        lines.append(current)

    y = padding
    for line in lines:
        draw.text((padding, y), line, font=font, fill=fill, stroke_width=4, stroke_fill=(0, 0, 0, 255))
        bbox = draw.textbbox((0, 0), line, font=font)
        y += (bbox[3] - bbox[1]) + 20


if __name__ == "__main__":
    generate_thumbnail("Titlu de test pentru thumbnail", Path("output/thumbnail.jpg"))
