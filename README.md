# Twitch VOD to YouTube Uploader

Local-only MVP for moving Twitch VODs you own or have rights to upload into YouTube through a persistent FastAPI queue.

## Prerequisites

- Docker Desktop with Docker Compose, or:
- Python 3.12+
- Node.js 20+
- `yt-dlp` available on `PATH` for manual backend runs
- Twitch developer app credentials
- Google OAuth credentials with YouTube Data API v3 enabled

## Configure Twitch OAuth

1. Open the [Twitch Developer Console](https://dev.twitch.tv/console/apps).
2. Create an application.
3. Set the OAuth redirect URL to `http://localhost:8000/auth/twitch/callback`.
4. Copy the client ID and client secret into `.env`.

The MVP uses Twitch OAuth authorization code flow and then calls Helix Videos for the connected user's latest archive VODs.

## Configure Google and YouTube

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or choose a project.
3. Enable **YouTube Data API v3**.
4. Configure the OAuth consent screen.
5. Create OAuth 2.0 credentials for a web application.
6. Add `http://localhost:8000/auth/google/callback` as an authorized redirect URI.
7. Copy the client ID and client secret into `.env`.

The app requests the `https://www.googleapis.com/auth/youtube.upload` scope and uses resumable uploads.

## Environment

Create `.env` from the example:

```powershell
Copy-Item .env.example .env
```

Fill in:

```env
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

Do not commit `.env`, SQLite databases, local downloads, or OAuth tokens.

## Run with Docker Compose

```powershell
docker compose up --build
```

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health

Docker Compose mounts:

- `./data` to persist SQLite when `DATABASE_URL=sqlite:////data/app.db`
- `./downloads` for temporary video files

The Compose file sets the backend container to `sqlite:////data/app.db` and `/downloads` so the database and temporary files land in those mounted folders. The `.env.example` values are still useful for manual runs.

## Run Manually

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///./app.db"
$env:DOWNLOAD_DIR="../downloads"
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- --host 0.0.0.0
```

Open http://localhost:5173.

## Core Flow

1. Connect Twitch.
2. Connect Google.
3. Fetch latest VODs.
4. Select one or more VODs.
5. Edit YouTube title, description, and privacy for each selected VOD.
6. Add jobs to the queue.
7. The backend worker downloads with `yt-dlp`, uploads to YouTube, stores the YouTube URL, and deletes the local temporary file after successful upload.

## API Endpoints

- `GET /health`
- `GET /auth/twitch/login`
- `GET /auth/twitch/callback`
- `GET /auth/google/login`
- `GET /auth/google/callback`
- `GET /api/auth/status`
- `GET /api/vods`
- `POST /api/jobs`
- `GET /api/jobs`
- `GET /api/jobs/{job_id}`
- `POST /api/jobs/{job_id}/retry`
- `POST /api/jobs/{job_id}/cancel`

## Known MVP Limitations

- This is a single-user local tool.
- OAuth tokens are stored locally in SQLite, not encrypted.
- Cancellation only applies to queued jobs, not active `yt-dlp` or YouTube upload processes.
- Upload progress is chunk-level and download progress depends on `yt-dlp` output.
- The worker processes jobs one at a time in the FastAPI process.
- Production hardening would need encrypted secrets, stronger CSRF/session handling, structured migrations, durable task leasing, and better observability.

## Troubleshooting

- **OAuth credentials missing**: verify `.env` has client IDs and secrets and restart the backend.
- **Redirect URI mismatch**: the URI in Twitch/Google developer settings must exactly match the callback in `.env`.
- **No Google refresh token**: revoke the app grant or reconnect; the MVP uses `access_type=offline` and `prompt=consent`.
- **Twitch VOD fetch returns unauthorized**: reconnect Twitch; the local token may be expired or revoked.
- **`yt-dlp` not found**: install `yt-dlp` locally or run the Docker backend image, which installs it from `requirements.txt`.
- **YouTube upload 403**: check that YouTube Data API v3 is enabled, the OAuth consent screen is configured, and the account has upload permission.
- **Large uploads fail**: retry the failed job. The MVP uses YouTube resumable uploads with simple retry behavior for transient server errors.
