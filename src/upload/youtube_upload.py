"""Upload videoclipuri pe YouTube folosind YouTube Data API v3 (OAuth2)."""

from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.config import CONFIG, env, path_from_root

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]
TOKEN_URI = "https://oauth2.googleapis.com/token"


def _get_credentials() -> Credentials:
    """Construieste credentialele YouTube.

    Preferata: YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
    (nu necesita fisiere si functioneaza headless in GitHub Actions).
    Fallback: flux OAuth bazat pe fisiere (client_secret.json / token.json),
    pentru rulare locala interactiva.
    """
    client_id = env("YOUTUBE_CLIENT_ID")
    client_secret = env("YOUTUBE_CLIENT_SECRET")
    refresh_token = env("YOUTUBE_REFRESH_TOKEN")

    if client_id and client_secret and refresh_token:
        creds = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri=TOKEN_URI,
            client_id=client_id,
            client_secret=client_secret,
            scopes=SCOPES,
        )
        creds.refresh(Request())
        return creds

    token_file = Path(env("YOUTUBE_TOKEN_FILE", "config/token.json"))
    client_secret_file = Path(env("YOUTUBE_CLIENT_SECRET_FILE", "config/client_secret.json"))

    creds: Credentials | None = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(client_secret_file), SCOPES)
            creds = flow.run_local_server(port=0)

        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return creds


def upload_video(
    video_path: Path,
    title: str,
    description: str,
    tags: list[str],
    thumbnail_path: Path | None = None,
) -> str:
    """Incarca videoclipul pe YouTube si returneaza ID-ul acestuia."""
    creds = _get_credentials()
    youtube = build("youtube", "v3", credentials=creds)

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags + CONFIG["youtube"]["default_tags"],
            "categoryId": CONFIG["youtube"]["category_id"],
        },
        "status": {
            "privacyStatus": CONFIG["youtube"]["privacy_status"],
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(str(video_path), chunksize=-1, resumable=True, mimetype="video/mp4")

    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()

    video_id = response["id"]

    if thumbnail_path and thumbnail_path.exists():
        youtube.thumbnails().set(
            videoId=video_id, media_body=MediaFileUpload(str(thumbnail_path))
        ).execute()

    return video_id


if __name__ == "__main__":
    video_id = upload_video(
        path_from_root("output", "test_video.mp4"),
        title="Test upload",
        description="Test description",
        tags=["test"],
    )
    print(f"https://youtube.com/shorts/{video_id}")
