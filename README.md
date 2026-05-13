# Twitch VOD to YouTube Uploader

Local-only MVP for moving Twitch VODs you own or have rights to upload into YouTube through a persistent FastAPI queue.

## Prerequisites

- Windows 10/11 with PowerShell
- Python 3.12+
- Node.js 20+
- Google OAuth credentials with YouTube Data API v3 enabled
- Twitch developer app credentials only if you want optional Twitch OAuth fallback

The backend installs `yt-dlp` into its local Python virtual environment from `backend/requirements.txt`.

## One-command start

From the project root:

```powershell
.\start.bat
```

The script will:

- create `.env` from `.env.example` if it does not exist;
- create `backend/.venv`;
- install backend dependencies;
- install frontend dependencies;
- use `data/app.db` for SQLite;
- use `downloads/` for temporary VOD files;
- start the FastAPI backend and Vite frontend.

Then open:

- Frontend: http://localhost:5173
- Backend health: http://localhost:8000/health

Keep the terminal open while using the app. Press `Ctrl+C` to stop both servers. Runtime logs are written to `logs/`.

## Environment

If `.env` was created automatically, fill in the Google values before uploading to YouTube:

```env
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
```

Twitch OAuth values are optional for the current MVP because public VOD lookup works by Twitch channel login:

```env
TWITCH_CLIENT_ID=
TWITCH_CLIENT_SECRET=
```

Do not commit `.env`, SQLite databases, local downloads, logs, or OAuth tokens.

## Google Permissions

The app requests these YouTube scopes:

- `https://www.googleapis.com/auth/youtube.upload`
- `https://www.googleapis.com/auth/youtube.force-ssl`

The second scope is used to read your playlists and add uploaded videos to a selected playlist. If you connected Google before playlist support was added, click **Connect Google** again and approve the updated permissions.

## Public Twitch VOD Lookup

The main VOD list works without Twitch OAuth. Enter a public Twitch channel login in the UI and the backend fetches public past broadcasts, including title, Twitch URL, thumbnail, creation timestamp, duration, uploader, game/category, and view count when Twitch exposes them publicly.

The backend uses Twitch's public web metadata path first and falls back to `yt-dlp` if that path changes. Twitch OAuth is still available as an optional fallback through Helix for users who connect an account.

## Configure Google and YouTube

1. Open the [Google Cloud Console](https://console.cloud.google.com/).
2. Create or choose a project.
3. Enable **YouTube Data API v3**.
4. Configure the OAuth consent screen.
5. Create OAuth 2.0 credentials for a web application.
6. Add `http://localhost:8000/auth/google/callback` as an authorized redirect URI.
7. Copy the client ID and client secret into `.env`.

The app requests YouTube upload and playlist-management permissions, then uses YouTube resumable uploads.

Playlist support also requires permission to manage YouTube playlist items. Keep the app in Google OAuth **Testing** mode and add each account that will use the tool under **Test users**.

## Configure Twitch OAuth Optional

1. Open the [Twitch Developer Console](https://dev.twitch.tv/console/apps).
2. Create an application.
3. Set the OAuth redirect URL to `http://localhost:8000/auth/twitch/callback`.
4. Copy the client ID and client secret into `.env`.

This is optional. You can fetch public VODs by channel login without Twitch OAuth.

## Manual Run

The one-command script is the normal path. If you need to run services manually, use two terminals.

Backend:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:DATABASE_URL="sqlite:///../data/app.db"
$env:DOWNLOAD_DIR="../downloads"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Frontend:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

## Core Flow

1. Start the app with `.\start.bat`.
2. Enter a Twitch channel login and fetch latest public VODs.
3. Connect Google.
4. Select one or more VODs.
5. Edit YouTube title, description, privacy, and optional playlist for each selected VOD.
6. Add jobs to the queue.
7. The backend worker downloads with `yt-dlp`, uploads to YouTube, adds the video to the selected playlist when configured, stores the YouTube URL, and deletes the local temporary file after successful upload.

## Playlists

After Google is connected, the frontend automatically asks the backend for your YouTube playlists. You can refresh the playlist list with the refresh button in **Selected VOD Metadata**.

For convenience, you can:

- apply one playlist to all selected VODs;
- override the playlist per VOD;
- leave playlist empty for uploads that should not be added to a playlist.

The playlist list is fetched from YouTube on demand and kept in the current browser session. The app does not need to request the list before every upload job.

## Power Loss and Resume Behavior

Jobs are persisted in SQLite. When the backend starts, it recovers interrupted jobs:

- `queued` jobs stay queued;
- interrupted `downloading`, `downloaded`, and `uploading` jobs are returned to the queue;
- if a completed downloaded file exists in `downloads/`, the worker skips downloading and continues with upload;
- if only an incomplete download exists, `yt-dlp` may resume the partial download when possible;
- YouTube resumable upload session URLs are stored locally in SQLite and reused after restart;
- if YouTube says the resumable session expired, the worker starts the YouTube upload again from the local file.

If the upload succeeded but adding to a playlist failed, the job is still marked `uploaded` and shows a warning instead of uploading a duplicate video.

## API Endpoints

- `GET /health`
- `GET /auth/twitch/login`
- `GET /auth/twitch/callback`
- `GET /auth/google/login`
- `GET /auth/google/callback`
- `GET /api/auth/status`
- `GET /api/youtube/playlists`
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
- YouTube resumable upload recovery depends on YouTube keeping the resumable session alive; expired sessions restart upload from the local file.
- Production hardening would need encrypted secrets, stronger CSRF/session handling, structured migrations, durable task leasing, and better observability.

## Troubleshooting

- **Google OAuth credentials missing**: verify `.env` has `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`, then restart with `.\start.bat`.
- **Redirect URI mismatch**: the URI in Google or Twitch developer settings must exactly match the callback in `.env`.
- **No Google refresh token**: revoke the app grant in your Google account permissions and reconnect; the MVP uses `access_type=offline` and `prompt=consent`.
- **Playlists do not load**: click **Connect Google** again and approve the updated YouTube permissions. Also check that the Google account is added as a test user in Google Cloud.
- **Public Twitch VOD fetch fails**: verify the channel login and that past broadcasts are public. The fallback requires the backend venv dependency `yt-dlp`.
- **Port already in use**: stop the process using port `8000` or `5173`, then run `.\start.bat` again.
- **YouTube upload 403**: check that YouTube Data API v3 is enabled, the OAuth consent screen is configured, and the Google account has upload permission.
- **Large uploads fail**: retry the failed job. The MVP uses YouTube resumable uploads with simple retry behavior for transient server errors.
