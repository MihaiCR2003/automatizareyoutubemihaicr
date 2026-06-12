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
│   ├── client_secret.json  # OAuth YouTube (nu se comite)
│   ├── token.json           # Token YouTube generat (nu se comite)
│   └── firebase_credentials.json  # Credențiale Firebase (nu se comite)
├── output/               # Videoclipuri generate (per run_id)
├── src/
│   ├── trending/          # Identificare subiecte trending (Google Trends)
│   ├── script_generation/ # Generare script via Hugging Face
│   ├── tts/                # Voice-over via ElevenLabs
│   ├── video/              # Compositing video (MoviePy) + thumbnail (Pillow)
│   ├── upload/             # Upload YouTube (Data API v3)
│   ├── storage/            # Stare pipeline (Firebase Realtime DB)
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
| ElevenLabs | `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID` | Cont gratuit pe elevenlabs.io, alege/clonează o voce română |
| Hugging Face | `HUGGINGFACE_API_TOKEN` | Token gratuit din Settings → Access Tokens pe huggingface.co |
| Telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | Creează bot cu @BotFather, ia chat_id cu @userinfobot |
| YouTube | `client_secret.json` în `config/` | Google Cloud Console → activează YouTube Data API v3 → creează credențiale OAuth (Desktop app) |
| Firebase | `firebase_credentials.json`, `FIREBASE_DB_URL` | Firebase Console → Project Settings → Service Accounts → Generate key + Realtime Database URL |

### Autentificare YouTube (prima rulare, local)

```bash
python -m src.upload.youtube_upload
```

Se va deschide un flow OAuth în browser; după autorizare se generează `config/token.json`.

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
`ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `HUGGINGFACE_API_TOKEN`,
`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `FIREBASE_DB_URL`,
`YOUTUBE_CLIENT_SECRET_JSON`, `YOUTUBE_TOKEN_JSON`, `FIREBASE_CREDENTIALS_JSON`
(conținutul fișierelor JSON corespunzătoare, ca string).

> Notă: token-ul YouTube (`token.json`) trebuie generat o singură dată local
> (vezi secțiunea de autentificare) și apoi salvat ca secret, pentru ca
> GitHub Actions să poată face refresh automat fără interacțiune.

## 📝 Configurare

Toate setările (rezoluție, durată max, volume audio, poziții personaj, tag-uri
YouTube implicite etc.) se găsesc în `config/config.yaml`.
