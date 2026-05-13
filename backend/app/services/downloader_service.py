import re
import subprocess
from collections.abc import Callable
from pathlib import Path

DOWNLOAD_PERCENT_RE = re.compile(r"\[download\]\s+(\d+(?:\.\d+)?)%")


class DownloadError(RuntimeError):
    pass


def _last_lines(lines: list[str], limit: int = 60) -> str:
    return "\n".join(lines[-limit:])[-4000:]


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
        "yt-dlp",
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

