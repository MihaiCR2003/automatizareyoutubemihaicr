# 🎬 Sistem Automatizat de Generare și Postare YouTube Shorts

Pipeline 100% gratuit pentru generarea, editarea și postarea automată de videoclipuri
YouTube Shorts (1080x1920), cu voice-over natural în română, personaj PNG, fundal video
și muzică ambientală. Control prin bot Telegram, scheduling zilnic la 18:00 via GitHub Actions.

## 📂 Structură

```
.
├── .github/workflows/daily-pipeline.yml   # Scheduler zilnic (cron 18:00)
├── assets/
│   ├── characters/     # PNG-uri personaj (fundal transparent), diverse poze/expresii
│   ├── backgrounds/     # Video/imagini de fundal (mp4/png/jpg)
│   └── music/           # Muzică ambientală (mp3/wav)
├── config/
│   ├── config.yaml       # Configurare generală
│   ├── client_secret.json  # OAuth YouTube, fallback local (nu se comite)
│   └── token.json           # Token YouTube, fallback local (nu se comite)
├── output/               # Videoclipuri generate (per run_id)
├── supabase/
│   └── schema.sql         # Schema tabelei "runs" (storage stare pipeline)
├── src/
│   ├── trending/          # Identificare subiecte trending (Google Trends)
│   ├── script_generation/ # Generare script via Gemini
│   ├── tts/                # Voice-over via Edge TTS
│   ├── video/              # Compositing video (MoviePy) + thumbnail (Pillow)
│   ├── upload/             # Upload YouTube (Data API v3)
│   ├── storage/            # Stare pipeline (Supabase Postgres)
│   └── telegram_bot/       # Bot de control + notificări
├── main.py                # Orchestrator pipeline
├── requirements.txt
└── .env.example
```

## 🚀 Setup local

1. **Python**: `pip install -r requirements.txt` (necesită `ffmpeg` instalat și în PATH).
2. Copiază `.env.example` → `.env` și completează cheile (vezi mai jos).
3. Adaugă în `assets/characters/` PNG-uri ale personajului (transparent), cu numele
   din `config/config.yaml` (`idle.png`, `talking.png`, `excited.png`, `pointing.png`).
4. Adaugă cel puțin un fundal în `assets/backgrounds/` (ex: `default_bg.mp4`) și
   muzică în `assets/music/`.

## 🔑 Chei și credențiale necesare

| Serviciu | Variabilă | Cum obții |
|---|---|---|
| Edge TTS | - | Fără cheie - voce română gratuită (`ro-RO-EmilNeural` / `ro-RO-AlinaNeural`, configurabil în `config/config.yaml`) |
| Gemini | `GEMINI_API_KEY` | Cheie gratuită din aistudio.google.com → Get API Key |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Creează bot cu @BotFather, ia chat_id cu @userinfobot |
| YouTube | `YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN` | Google Cloud Console (OAuth Web app) + script local de generare refresh token (o singură dată) |
| Supabase (opțional) | `SUPABASE_URL`, `SUPABASE_KEY` | Proiect gratuit pe supabase.com → rulează `supabase/schema.sql` în SQL Editor → `SUPABASE_KEY` = "secret key" (service role). Fără asta, starea pipeline-ului se salvează local în `output/runs.json`. |

### Autentificare YouTube (o singură dată)

Cu `YOUTUBE_CLIENT_ID` + `YOUTUBE_CLIENT_SECRET` + `YOUTUBE_REFRESH_TOKEN` setate în `.env`
(sau ca secrete GitHub), nu mai e nevoie de niciun fișier sau pas interactiv —
`src/upload/youtube_upload.py` face refresh automat al token-ului la fiecare rulare,
inclusiv headless în GitHub Actions.

Dacă nu ai încă un refresh token, generează-l o singură dată local (Client ID/Secret
de tip "Web application" din Google Cloud Console, cu redirect URI
`http://localhost:8080/callback`), apoi salvează cele 3 valori în `.env`.

## ▶️ Rulare

```bash
# Generare bazată pe trending
python main.py

# Pornire bot Telegram (control interactiv)
python -m src.telegram_bot.bot
```

## 🤖 Comenzi Telegram

- `/generate <idee>` — generează un video pe baza unei idei (sau trending dacă e gol)
- `/status` — listează videoclipuri în așteptare de aprobare
- `/approve <run_id>` — aprobă și postează pe YouTube
- `/reject <run_id>` — respinge un videoclip generat

## ⏰ Scheduling (GitHub Actions)

Workflow-ul `.github/workflows/daily-pipeline.yml` rulează zilnic în jurul orei 18:00
(Europe/Bucharest) și poate fi declanșat manual din tab-ul Actions (`workflow_dispatch`,
cu subiect custom opțional).

Adaugă în **Settings → Secrets and variables → Actions** următoarele secrete:
`GEMINI_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `SUPABASE_URL`, `SUPABASE_KEY`,
`YOUTUBE_CLIENT_ID`, `YOUTUBE_CLIENT_SECRET`, `YOUTUBE_REFRESH_TOKEN`.

## 📝 Configurare

Toate setările (rezoluție, durată max, volume audio, poziții personaj, tag-uri
YouTube implicite etc.) se găsesc în `config/config.yaml`.
