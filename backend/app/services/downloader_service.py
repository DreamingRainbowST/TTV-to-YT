import json
import re
import subprocess
import sys
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.schemas import TwitchVodOut

DOWNLOAD_PERCENT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")
TWITCH_CHANNEL_RE = re.compile(r"^[A-Za-z0-9_]{3,25}$")
TWITCH_GQL_URL = "https://gql.twitch.tv/gql"
# Public Twitch web client id used by yt-dlp for unauthenticated metadata requests.
TWITCH_PUBLIC_CLIENT_ID = "ue6666qo983tsx6so1t0vnawi233wa"
TWITCH_VIDEOS_QUERY_HASH = "67004f7881e65c297936f32c75246470629557a393788fb5a69d6d9a25a8fd5f"


class DownloadError(RuntimeError):
    pass


class TwitchPublicFetchError(RuntimeError):
    pass


def _last_lines(lines: list[str], limit: int = 60) -> str:
    return "\n".join(lines[-limit:])[-4000:]


def _format_duration(seconds: float | int | None) -> str | None:
    if seconds is None:
        return None

    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _iso_datetime(payload: dict) -> str | None:
    timestamp = payload.get("timestamp")
    if timestamp:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat()

    upload_date = payload.get("upload_date")
    if isinstance(upload_date, str) and len(upload_date) == 8:
        try:
            return datetime.strptime(upload_date, "%Y%m%d").replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            return None
    return None


def _iso_datetime_from_twitch(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).isoformat()
    except ValueError:
        return value


def _fetch_public_vods_graphql(channel: str, limit: int) -> list[TwitchVodOut]:
    operation = {
        "operationName": "FilterableVideoTower_Videos",
        "variables": {
            "channelOwnerLogin": channel,
            "broadcastType": "ARCHIVE",
            "videoSort": "TIME",
            "limit": min(limit, 20),
        },
        "extensions": {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": TWITCH_VIDEOS_QUERY_HASH,
            }
        },
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(
            TWITCH_GQL_URL,
            headers={
                "Client-ID": TWITCH_PUBLIC_CLIENT_ID,
                "Content-Type": "text/plain;charset=UTF-8",
            },
            content=json.dumps([operation]),
        )

    if response.status_code >= 400:
        raise TwitchPublicFetchError(f"Twitch public metadata request failed: {response.text[:500]}")

    payload = response.json()
    user = payload[0].get("data", {}).get("user") if payload else None
    if not user or user.get("id") == "":
        raise TwitchPublicFetchError(f'Channel "{channel}" was not found.')

    edges = user.get("videos", {}).get("edges", [])
    vods: list[TwitchVodOut] = []
    for edge in edges:
        node = edge.get("node") if isinstance(edge, dict) else None
        if not isinstance(node, dict) or not node.get("id"):
            continue

        owner = node.get("owner") if isinstance(node.get("owner"), dict) else {}
        game = node.get("game") if isinstance(node.get("game"), dict) else {}
        vod_id = str(node["id"])
        vods.append(
            TwitchVodOut(
                id=f"v{vod_id}",
                title=node.get("title") or vod_id,
                url=f"https://www.twitch.tv/videos/{vod_id}",
                thumbnail_url=node.get("previewThumbnailURL"),
                created_at=_iso_datetime_from_twitch(node.get("publishedAt")),
                duration=_format_duration(node.get("lengthSeconds")),
                view_count=node.get("viewCount"),
                uploader=owner.get("displayName"),
                uploader_id=owner.get("login"),
                game_name=game.get("displayName") or game.get("name"),
            )
        )

    return vods


def fetch_public_vods(channel: str, limit: int = 20) -> list[TwitchVodOut]:
    channel = channel.strip().lstrip("@")
    if not TWITCH_CHANNEL_RE.fullmatch(channel):
        raise TwitchPublicFetchError("Enter a valid Twitch channel login, for example: lirik")

    try:
        vods = _fetch_public_vods_graphql(channel, limit)
        if vods:
            return vods
    except Exception:
        # Twitch changes its public GraphQL persisted queries occasionally. Keep
        # yt-dlp as a slower fallback because it tracks Twitch extractor changes.
        pass

    url = f"https://www.twitch.tv/{channel}/videos?filter=archives&sort=time"
    args = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--skip-download",
        "--ignore-errors",
        "--no-warnings",
        "--playlist-end",
        str(min(limit, 20)),
        "--dump-json",
        url,
    ]
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            shell=False,
            encoding="utf-8",
            errors="replace",
            timeout=240,
        )
    except FileNotFoundError as exc:
        raise TwitchPublicFetchError("yt-dlp is not installed in the backend Python environment.") from exc
    except subprocess.TimeoutExpired as exc:
        raise TwitchPublicFetchError("Timed out while fetching public Twitch VOD metadata with yt-dlp.") from exc

    vods: list[TwitchVodOut] = []
    parse_errors: list[str] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            parse_errors.append(line[:300])
            continue

        vod_url = payload.get("webpage_url") or payload.get("url")
        vod_id = str(payload.get("id") or Path(str(vod_url)).name)
        title = payload.get("fulltitle") or payload.get("title") or vod_id
        duration = payload.get("duration_string") or _format_duration(payload.get("duration"))
        vods.append(
            TwitchVodOut(
                id=vod_id,
                title=title,
                url=vod_url,
                thumbnail_url=payload.get("thumbnail"),
                created_at=_iso_datetime(payload),
                duration=duration,
                view_count=payload.get("view_count"),
                uploader=payload.get("uploader"),
                uploader_id=payload.get("uploader_id"),
                game_name=None,
            )
        )

    if vods:
        return vods

    error_text = result.stderr.strip() or "\n".join(parse_errors)
    if result.returncode != 0:
        raise TwitchPublicFetchError(f"yt-dlp could not fetch VODs for {channel}: {error_text[-1000:]}")
    raise TwitchPublicFetchError(
        f"No public past broadcasts were found for {channel}. Check the channel name and that VODs are public."
    )


def download_vod(
    job_id: int,
    twitch_url: str,
    download_dir: str,
    progress_callback: Callable[[float], None] | None = None,
) -> str:
    target_dir = Path(download_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    output_template = str(target_dir / f"job-{job_id}-%(id)s.%(ext)s")
    args = [
        sys.executable,
        "-m",
        "yt_dlp",
        "--no-playlist",
        "--newline",
        "--restrict-filenames",
        "-o",
        output_template,
        twitch_url,
    ]

    process = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        shell=False,
        encoding="utf-8",
        errors="replace",
    )

    output_lines: list[str] = []
    assert process.stdout is not None
    for line in process.stdout:
        line = line.rstrip()
        output_lines.append(line)
        match = DOWNLOAD_PERCENT_RE.search(line)
        if match and progress_callback:
            progress_callback(float(match.group(1)))

    return_code = process.wait()
    if return_code != 0:
        raise DownloadError(f"yt-dlp failed with exit code {return_code}:\n{_last_lines(output_lines)}")

    candidates = [
        path
        for path in target_dir.glob(f"job-{job_id}-*")
        if path.is_file() and not path.name.endswith((".part", ".ytdl"))
    ]
    if not candidates:
        raise DownloadError("yt-dlp completed but no downloaded video file was found.")

    newest = max(candidates, key=lambda path: path.stat().st_mtime)
    return str(newest)
