"""Orchestrator principal: trending -> script -> voice-over -> video -> thumbnail -> aprobare/upload."""

from __future__ import annotations

import uuid
from datetime import datetime

from src.config import CONFIG, path_from_root
from src.script_generation.generate_script import generate_script, generate_script_from_candidates
from src.storage import db
from src.telegram_bot import notifier
from src.trending.get_trends import get_trending_topics_with_context
from src.tts.voice_over import generate_voice_over
from src.upload.youtube_upload import upload_video
from src.video.compositor import build_video
from src.video.thumbnail import generate_thumbnail


def run_pipeline(topic: str | None = None) -> str:
    """Ruleaza intregul pipeline de generare pentru un singur videoclip.

    Daca `topic` nu este specificat, alege primul subiect trending.
    Returneaza run_id-ul rularii, salvat in storage.
    """
    run_id = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"
    output_dir = path_from_root(CONFIG["video"]["output_dir"], run_id)

    if CONFIG["telegram"]["notify_on_start"]:
        notifier.send_message(f"Pornesc generarea videoclipului ({run_id})...")

    if topic:
        script = generate_script(topic, "")
    else:
        candidates = get_trending_topics_with_context()
        if not candidates:
            candidates = [{"topic": "Curiozitati interesante", "context": ""}]

        script = generate_script_from_candidates(candidates)
        topic = script.get("subiect_ales", candidates[0]["topic"])

    voice_path = output_dir / "voice_over.mp3"
    generate_voice_over(script["voice_over"], voice_path)

    video_path = output_dir / "video.mp4"
    build_video(voice_path, video_path, segments=script.get("segments"))

    thumbnail_path = output_dir / "thumbnail.jpg"
    generate_thumbnail(script["titlu"], thumbnail_path)

    status = "pending_approval" if CONFIG["telegram"]["require_approval_before_upload"] else "ready_to_upload"

    db.save_run(
        run_id,
        {
            "topic": topic,
            "titlu": script["titlu"],
            "descriere": script["descriere"],
            "tags": script["tags"],
            "video_path": str(video_path),
            "thumbnail_path": str(thumbnail_path),
            "status": status,
            "created_at": datetime.now().isoformat(),
        },
    )

    if CONFIG["telegram"]["notify_on_finish"]:
        notifier.send_video(video_path, caption=f"{script['titlu']}\n\nRun ID: {run_id}")
        if status == "pending_approval":
            notifier.send_message(
                f"Videoclipul {run_id} asteapta aprobare.\n"
                f"Foloseste /approve {run_id} sau /reject {run_id}."
            )
        else:
            url = approve_and_upload(run_id)
            notifier.send_message(f"Videoclipul {run_id} a fost postat pe YouTube:\n{url}")

    return run_id


def approve_and_upload(run_id: str) -> str:
    """Incarca pe YouTube videoclipul corespunzator run_id-ului si returneaza URL-ul."""
    run = db.get_run(run_id)
    if run is None:
        raise ValueError(f"Nu exista nicio rulare cu ID-ul {run_id}")

    video_id = upload_video(
        video_path=path_from_root(run["video_path"]),
        title=run["titlu"],
        description=run["descriere"],
        tags=run["tags"],
        thumbnail_path=path_from_root(run["thumbnail_path"]),
    )

    url = f"https://youtube.com/shorts/{video_id}"
    db.update_run(run_id, {"status": "uploaded", "youtube_url": url})
    return url


if __name__ == "__main__":
    run_pipeline()
