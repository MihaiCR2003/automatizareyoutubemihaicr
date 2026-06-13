"""Compune videoclipul final: background + personaj PNG + voice-over + muzica."""

from __future__ import annotations

import random
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

from moviepy.editor import (
    AudioFileClip,
    CompositeAudioClip,
    CompositeVideoClip,
    ImageClip,
    TextClip,
    VideoFileClip,
    afx,
    vfx,
)

from src.config import CONFIG, path_from_root


def _apply_zoom(clip, duration: float, width: int, height: int, zoom_in: bool):
    """Aplica un efect lent de zoom in/out (Ken Burns) pe un clip de dimensiune width x height."""
    max_zoom = 1.12

    def transform(get_frame, t):
        progress = t / duration if duration > 0 else 0
        zoom = (1 + (max_zoom - 1) * progress) if zoom_in else (max_zoom - (max_zoom - 1) * progress)

        frame = get_frame(t)
        img = Image.fromarray(frame)
        new_w, new_h = max(int(width * zoom), width), max(int(height * zoom), height)
        img = img.resize((new_w, new_h), Image.LANCZOS)

        left = (new_w - width) // 2
        top = (new_h - height) // 2
        img = img.crop((left, top, left + width, top + height))
        return np.array(img)

    return clip.fl(transform)


def _pick_background_file() -> Path:
    """Alege aleator un fundal dintre toate imaginile/video-urile disponibile (varietate intre videoclipuri)."""
    bg_dir = path_from_root(CONFIG["background"]["assets_dir"])
    valid_exts = {".png", ".jpg", ".jpeg", ".mp4", ".mov", ".webm"}
    candidates = [p for p in bg_dir.iterdir() if p.suffix.lower() in valid_exts]
    if candidates:
        return random.choice(candidates)
    return bg_dir / CONFIG["background"]["default"]


def _load_background(duration: float, width: int, height: int):
    """Incarca fundalul (video sau imagine), redimensionat la width x height, cu efect de zoom."""
    bg_file = _pick_background_file()

    if bg_file.suffix.lower() in {".mp4", ".mov", ".webm"}:
        clip = VideoFileClip(str(bg_file))
        if clip.duration < duration:
            clip = clip.fx(vfx.loop, duration=duration)
        else:
            clip = clip.subclip(0, duration)
    else:
        clip = ImageClip(str(bg_file)).set_duration(duration)

    clip = clip.resize(height=height)
    if clip.w < width:
        clip = clip.resize(width=width)
    clip = clip.crop(
        x_center=clip.w / 2, y_center=clip.h / 2, width=width, height=height
    )

    zoom_in = random.choice([True, False])
    clip = _apply_zoom(clip, duration, width, height, zoom_in)
    return clip


def _segment_timings(duration: float, segments: list[dict]) -> list[tuple[float, float, dict]]:
    """Calculeaza (start, durata, segment) pentru fiecare segment.

    Daca segmentele au deja "start"/"duration" (calculate din audio-ul real
    generat per-segment), le folosim direct pentru sincronizare exacta.
    Altfel, calculam proportional cu lungimea textului (fallback).
    """
    if segments and "start" in segments[0] and "duration" in segments[0]:
        timings = []
        for seg in segments:
            start = seg["start"]
            seg_len = seg["duration"]
            if start >= duration:
                break
            seg_len = min(seg_len, duration - start)
            if seg_len <= 0:
                continue
            timings.append((start, seg_len, seg))
        return timings

    total_len = sum(max(len(seg.get("text", "")), 1) for seg in segments) or 1
    timings = []
    t = 0.0
    for seg in segments:
        seg_len = duration * max(len(seg.get("text", "")), 1) / total_len
        seg_len = min(seg_len, duration - t)
        if seg_len <= 0:
            continue
        timings.append((t, seg_len, seg))
        t += seg_len
    return timings


def _load_caption_font(size: int):
    for font_path in ("arialbd.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(font_path, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _layout_caption_words(words_text: list[str], font, max_width: int):
    """Calculeaza pozitia fiecarui cuvant (impachetate pe linii, centrate) si dimensiunea canvas-ului."""
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)
    space_w = draw.textlength(" ", font=font)

    lines: list[list[tuple[str, float]]] = []
    current: list[tuple[str, float]] = []
    current_width = 0.0

    for word in words_text:
        w = draw.textlength(word, font=font)
        extra = w if not current else w + space_w
        if current and current_width + extra > max_width:
            lines.append(current)
            current = []
            current_width = 0.0
            extra = w
        current.append((word, w))
        current_width += extra

    if current:
        lines.append(current)

    ascent, descent = font.getmetrics()
    line_height = ascent + descent + 14
    padding = 10

    layout = []
    idx = 0
    for line_idx, line in enumerate(lines):
        total_width = sum(w for _, w in line) + space_w * (len(line) - 1)
        x = max((max_width - total_width) / 2, 0)
        y = padding + line_idx * line_height
        for word, w in line:
            layout.append({"index": idx, "word": word, "x": x, "y": y})
            x += w + space_w
            idx += 1

    canvas_size = (int(max_width), int(len(lines) * line_height + 2 * padding))
    return layout, canvas_size


def _render_caption_frame(layout, canvas_size, active_index: int, font, color, highlight_color, stroke_color, stroke_width):
    img = Image.new("RGBA", canvas_size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for item in layout:
        fill = highlight_color if item["index"] == active_index else color
        draw.text(
            (item["x"], item["y"]),
            item["word"],
            font=font,
            fill=fill,
            stroke_width=stroke_width,
            stroke_fill=stroke_color,
        )
    return np.array(img)


def _load_subtitle_clips(duration: float, width: int, height: int, segments: list[dict] | None = None):
    """Creeaza subtitrari tip 'karaoke' (cuvant cu cuvant evidentiat), sincronizate cu vocea."""
    sub_cfg = CONFIG["subtitles"]
    if not sub_cfg.get("enabled") or not segments:
        return []

    max_width = int(width * 0.9)
    base_font_size = sub_cfg["font_size"]
    color = sub_cfg["color"]
    highlight_color = sub_cfg.get("highlight_color", "#FFD400")
    stroke_color = sub_cfg["stroke_color"]
    stroke_width = sub_cfg["stroke_width"]
    position_y = int(height * sub_cfg["position_y_ratio"])

    clips = []

    for seg_index, (start, seg_len, seg) in enumerate(_segment_timings(duration, segments)):
        text = seg.get("text", "").strip()
        if not text:
            continue

        words = seg.get("words")
        if not words:
            clip = (
                TextClip(
                    text,
                    fontsize=base_font_size,
                    color=color,
                    font=sub_cfg["font"],
                    method="caption",
                    size=(max_width, None),
                    align="center",
                    stroke_color=stroke_color,
                    stroke_width=stroke_width,
                )
                .set_duration(seg_len)
                .set_start(start)
                .set_position(("center", position_y))
            )
            clips.append(clip)
            continue

        # Segmentul "hook" (primul dupa intro) e accentuat cu un font mai mare.
        font_size = int(base_font_size * 1.25) if seg_index == 1 else base_font_size
        font = _load_caption_font(font_size)

        words_text = [w["text"] for w in words]
        layout, canvas_size = _layout_caption_words(words_text, font, max_width)

        for word_idx, w in enumerate(words):
            w_start = w["start"]
            if w_start >= start + seg_len:
                break

            next_start = words[word_idx + 1]["start"] if word_idx + 1 < len(words) else start + seg_len
            w_dur = min(next_start, start + seg_len) - w_start
            if w_dur <= 0:
                continue

            frame = _render_caption_frame(
                layout, canvas_size, word_idx, font, color, highlight_color, stroke_color, stroke_width
            )
            clip = (
                ImageClip(frame)
                .set_duration(w_dur)
                .set_start(w_start)
                .set_position(("center", position_y))
            )
            clips.append(clip)

    return clips


def _load_character_clips(duration: float, width: int, char_cfg: dict, segments: list[dict] | None = None):
    """Creeaza clipuri cu personajul PNG, schimband expresia in functie de segmentele scenariului.

    Daca `segments` este furnizat (lista de {text, expresie}), durata fiecarei expresii
    este proportionala cu lungimea textului segmentului respectiv. Altfel, alterneaza
    expresii aleatorii la fiecare 4 secunde.
    """
    chars_dir = path_from_root(char_cfg["assets_dir"])
    scale = char_cfg["default_scale"]
    position = tuple(char_cfg["default_position"])
    positions = char_cfg["positions"]
    files_by_name = {p["name"]: p["file"] for p in positions}
    default_file = positions[0]["file"]

    clips = []

    if segments:
        for start, seg_len, seg in _segment_timings(duration, segments):
            file_name = files_by_name.get(seg.get("expresie"), default_file)
            img_path = chars_dir / file_name

            clip = (
                ImageClip(str(img_path))
                .set_duration(seg_len)
                .resize(width=int(width * scale))
                .set_position(position)
                .set_start(start)
            )
            clips.append(clip)

        return clips

    segment_duration = 4.0  # secunde intre schimbari de poza
    t = 0.0
    while t < duration:
        pos_cfg = random.choice(positions)
        img_path = chars_dir / pos_cfg["file"]
        seg_len = min(segment_duration, duration - t)

        clip = (
            ImageClip(str(img_path))
            .set_duration(seg_len)
            .resize(width=int(width * scale))
            .set_position(position)
            .set_start(t)
        )
        clips.append(clip)
        t += seg_len

    return clips


def _build_audio(voice_path: Path, duration: float):
    """Mixeaza voice-over-ul cu muzica ambientala."""
    voice_volume = CONFIG["audio"]["voice_volume"]
    music_volume = CONFIG["audio"]["music_volume"]
    music_dir = path_from_root(CONFIG["audio"]["music_dir"])

    voice_clip = AudioFileClip(str(voice_path)).fx(afx.volumex, voice_volume)

    music_files = list(music_dir.glob("*.mp3")) + list(music_dir.glob("*.wav"))
    if not music_files:
        return voice_clip

    music_path = random.choice(music_files)
    music_clip = AudioFileClip(str(music_path)).fx(afx.volumex, music_volume)

    if music_clip.duration < duration:
        music_clip = music_clip.fx(afx.audio_loop, duration=duration)
    else:
        music_clip = music_clip.subclip(0, duration)

    return CompositeAudioClip([music_clip, voice_clip])


def build_video(
    voice_over_path: Path,
    output_path: Path,
    segments: list[dict] | None = None,
    video_cfg: dict | None = None,
    character_cfg: dict | None = None,
) -> Path:
    """Construieste videoclipul final si il salveaza la output_path.

    `video_cfg` (width, height, fps, max_duration_seconds) si `character_cfg`
    (assets_dir, positions, default_scale, default_position) pot fi date
    pentru a genera videoclipuri cu alta rezolutie/aspect (ex: serialul
    orizontal 1920x1080), altfel se folosesc valorile implicite din config.yaml.
    """
    video_cfg = video_cfg or CONFIG["video"]
    character_cfg = character_cfg or CONFIG["character"]

    width = video_cfg["width"]
    height = video_cfg["height"]
    fps = video_cfg["fps"]
    max_duration = video_cfg["max_duration_seconds"]

    voice_clip = AudioFileClip(str(voice_over_path))
    duration = min(voice_clip.duration, max_duration)
    voice_clip.close()

    background = _load_background(duration, width, height)
    character_clips = _load_character_clips(duration, width, character_cfg, segments)
    subtitle_clips = _load_subtitle_clips(duration, width, height, segments)
    audio = _build_audio(voice_over_path, duration)

    final = CompositeVideoClip(
        [background, *character_clips, *subtitle_clips], size=(width, height)
    ).set_duration(duration).set_audio(audio)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    final.write_videofile(
        str(output_path),
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        preset="medium",
    )

    return output_path


if __name__ == "__main__":
    build_video(
        Path("output/test_voice.mp3"),
        Path("output/test_video.mp4"),
    )
