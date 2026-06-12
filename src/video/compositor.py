"""Compune videoclipul final: background + personaj PNG + voice-over + muzica."""

from __future__ import annotations

import random
from pathlib import Path

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


def _load_background(duration: float):
    """Incarca fundalul (video sau imagine), redimensionat la 1080x1920."""
    width = CONFIG["video"]["width"]
    height = CONFIG["video"]["height"]
    bg_dir = path_from_root(CONFIG["background"]["assets_dir"])
    bg_file = bg_dir / CONFIG["background"]["default"]

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
    return clip


def _segment_timings(duration: float, segments: list[dict]) -> list[tuple[float, float, dict]]:
    """Calculeaza (start, durata, segment) pentru fiecare segment, proportional cu lungimea textului."""
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


def _load_subtitle_clips(duration: float, segments: list[dict] | None = None):
    """Creeaza subtitrari pentru narator, sincronizate cu segmentele scenariului."""
    sub_cfg = CONFIG["subtitles"]
    if not sub_cfg.get("enabled") or not segments:
        return []

    width = CONFIG["video"]["width"]
    height = CONFIG["video"]["height"]
    clips = []

    for start, seg_len, seg in _segment_timings(duration, segments):
        text = seg.get("text", "").strip()
        if not text:
            continue

        clip = (
            TextClip(
                text,
                fontsize=sub_cfg["font_size"],
                color=sub_cfg["color"],
                font=sub_cfg["font"],
                method="caption",
                size=(int(width * 0.9), None),
                align="center",
                stroke_color=sub_cfg["stroke_color"],
                stroke_width=sub_cfg["stroke_width"],
            )
            .set_duration(seg_len)
            .set_start(start)
            .set_position(("center", int(height * sub_cfg["position_y_ratio"])))
        )
        clips.append(clip)

    return clips


def _load_character_clips(duration: float, segments: list[dict] | None = None):
    """Creeaza clipuri cu personajul PNG, schimband expresia in functie de segmentele scenariului.

    Daca `segments` este furnizat (lista de {text, expresie}), durata fiecarei expresii
    este proportionala cu lungimea textului segmentului respectiv. Altfel, alterneaza
    expresii aleatorii la fiecare 4 secunde.
    """
    width = CONFIG["video"]["width"]
    char_cfg = CONFIG["character"]
    chars_dir = path_from_root(char_cfg["assets_dir"])
    scale = char_cfg["default_scale"]
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
                .set_position(("center", "bottom"))
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
            .set_position(("center", "bottom"))
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


def build_video(voice_over_path: Path, output_path: Path, segments: list[dict] | None = None) -> Path:
    """Construieste videoclipul final 1080x1920 si il salveaza la output_path."""
    width = CONFIG["video"]["width"]
    height = CONFIG["video"]["height"]
    fps = CONFIG["video"]["fps"]
    max_duration = CONFIG["video"]["max_duration_seconds"]

    voice_clip = AudioFileClip(str(voice_over_path))
    duration = min(voice_clip.duration, max_duration)
    voice_clip.close()

    background = _load_background(duration)
    character_clips = _load_character_clips(duration, segments)
    subtitle_clips = _load_subtitle_clips(duration, segments)
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
