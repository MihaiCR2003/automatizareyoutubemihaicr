"""Orchestrator pentru serialul narativ pe episoade (videoclipuri lungi, 1920x1080).

Fiecare rulare genereaza UN episod, continuand direct din memoria episodului
anterior (salvata in baza de date), si il publica pe YouTube.
"""

from __future__ import annotations

from datetime import datetime

from src.config import CONFIG, path_from_root
from src.script_generation.generate_episode import generate_episode
from src.series import state as series_state
from src.storage import db
from src.telegram_bot import notifier
from src.tts.voice_over import generate_voice_over_segments
from src.upload.youtube_upload import upload_video
from src.video.compositor import build_video
from src.video.thumbnail import generate_thumbnail, pick_thumbnail_character


def _character_cfg() -> dict:
    series_cfg = CONFIG["series"]
    char_cfg = CONFIG["character"]
    return {
        "assets_dir": char_cfg["assets_dir"],
        "positions": char_cfg["positions"],
        "default_scale": series_cfg.get("character_scale", char_cfg["default_scale"]),
        "default_position": series_cfg.get("character_position", char_cfg["default_position"]),
    }


def run_episode() -> str:
    """Genereaza si publica urmatorul episod al serialului. Returneaza run_id-ul rularii."""
    series_cfg = CONFIG["series"]
    state = series_state.get_state()
    next_episode_number = (state.get("episode_number", 0) if state else 0) + 1

    if CONFIG["telegram"]["notify_on_start"]:
        notifier.send_message(f"Pornesc generarea episodului {next_episode_number} din serial...")

    script = generate_episode(state)
    episode_number = script["episode_number"]

    titlu_serial = script.get("titlu_serial") or (state or {}).get("titlu_serial") or "Saga"
    video_title = f"{titlu_serial} | Episodul {episode_number}: {script['titlu_episod']}"[:100]

    run_id = f"series_ep{episode_number:03d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_dir = path_from_root(series_cfg["output_dir"], run_id)

    voice_path, timed_segments = generate_voice_over_segments(script["segments"], output_dir)

    video_path = output_dir / "video.mp4"
    build_video(
        voice_path,
        video_path,
        segments=timed_segments,
        video_cfg=series_cfg["video"],
        character_cfg=_character_cfg(),
    )

    thumbnail_path = output_dir / "thumbnail.jpg"
    generate_thumbnail(
        video_title,
        thumbnail_path,
        character_image=pick_thumbnail_character(timed_segments),
        video_cfg=series_cfg["video"],
        character_cfg=_character_cfg(),
    )

    video_id = upload_video(
        video_path=video_path,
        title=video_title,
        description=script["descriere"],
        tags=script["tags"],
        thumbnail_path=thumbnail_path,
    )
    url = f"https://youtube.com/watch?v={video_id}"

    series_state.save_state(
        {
            "titlu_serial": titlu_serial,
            "episode_number": episode_number,
            "total_episodes": series_cfg["total_episodes"],
            "memorie": script["memorie"],
            "last_youtube_url": url,
            "updated_at": datetime.now().isoformat(),
        }
    )

    db.save_run(
        run_id,
        {
            "titlu_serial": titlu_serial,
            "episode_number": episode_number,
            "titlu": video_title,
            "descriere": script["descriere"],
            "tags": script["tags"],
            "video_path": str(video_path),
            "thumbnail_path": str(thumbnail_path),
            "status": "uploaded",
            "youtube_url": url,
            "created_at": datetime.now().isoformat(),
        },
    )

    if CONFIG["telegram"]["notify_on_finish"]:
        notifier.send_message(f"Episodul {episode_number} - {video_title}\na fost postat:\n{url}")

    return run_id


if __name__ == "__main__":
    run_episode()
