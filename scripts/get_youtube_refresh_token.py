"""Script local pentru generarea unui YOUTUBE_REFRESH_TOKEN nou.

Ruleaza o singura data, local (nu in GitHub Actions):
    python scripts/get_youtube_refresh_token.py

Foloseste YOUTUBE_CLIENT_ID si YOUTUBE_CLIENT_SECRET din .env.
La final afiseaza noul refresh token - actualizeaza .env si secretul
YOUTUBE_REFRESH_TOKEN din GitHub cu valoarea afisata.

IMPORTANT: Inainte de a rula, in Google Cloud Console -> APIs & Services
-> OAuth consent screen, seteaza "Publishing status" pe "In production"
(altfel refresh token-ul expira automat in 7 zile, in modul "Testing").
"""

from __future__ import annotations

from google_auth_oauthlib.flow import InstalledAppFlow

from src.config import env

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def main() -> None:
    client_id = env("YOUTUBE_CLIENT_ID")
    client_secret = env("YOUTUBE_CLIENT_SECRET")

    if not client_id or not client_secret:
        raise RuntimeError("YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET nu sunt setate in .env")

    client_config = {
        "web": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost:8080/callback"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=8080, redirect_uri_trailing_slash=False, open_browser=True)

    print("\nRefresh token nou:\n")
    print(creds.refresh_token)
    print("\nActualizeaza YOUTUBE_REFRESH_TOKEN in .env si in secretele GitHub Actions.")


if __name__ == "__main__":
    main()
