import { ExternalLink, RotateCcw, XCircle } from "lucide-react";

import type { UploadJob } from "../types";

interface Props {
  jobs: UploadJob[];
  onRetry: (jobId: number) => void;
  onCancel: (jobId: number) => void;
}

const statusClass: Record<UploadJob["status"], string> = {
  queued: "bg-slate-100 text-slate-700",
  downloading: "bg-sky-100 text-sky-800",
  downloaded: "bg-cyan-100 text-cyan-800",
  uploading: "bg-amber-100 text-amber-800",
  uploaded: "bg-emerald-100 text-emerald-800",
  failed: "bg-rose-100 text-rose-800",
  cancelled: "bg-zinc-100 text-zinc-700"
};

export default function JobQueue({ jobs, onRetry, onCancel }: Props) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-base font-semibold text-slate-950">Job Queue</h2>
        <p className="text-sm text-slate-500">The backend worker processes one queued job at a time.</p>
      </div>
      {jobs.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
          No upload jobs yet.
        </div>
      ) : (
        <div className="overflow-hidden rounded-md border border-slate-200 bg-white shadow-sm">
          <div className="grid min-w-[760px] grid-cols-[1.4fr_1fr_120px_160px_90px] gap-3 border-b border-slate-200 bg-slate-50 px-4 py-3 text-xs font-semibold uppercase text-slate-500">
            <span>Title</span>
            <span>Twitch VOD</span>
            <span>Status</span>
            <span>Progress</span>
            <span>Actions</span>
          </div>
          <div className="overflow-x-auto">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="grid min-w-[760px] grid-cols-[1.4fr_1fr_120px_160px_90px] gap-3 border-b border-slate-100 px-4 py-3 last:border-b-0"
              >
                <div className="min-w-0">
                  <p className="truncate text-sm font-semibold text-slate-950">{job.youtube_title}</p>
                  <p className="mt-1 text-xs text-slate-500">Privacy: {job.privacy_status}</p>
                  {job.youtube_playlist_title ? (
                    <p className="mt-1 truncate text-xs text-slate-500">Playlist: {job.youtube_playlist_title}</p>
                  ) : null}
                  {job.error_message ? (
                    <p className="mt-2 line-clamp-3 text-xs text-rose-700">{job.error_message}</p>
                  ) : null}
                  {job.youtube_url ? (
                    <a
                      href={job.youtube_url}
                      target="_blank"
                      rel="noreferrer"
                      className="mt-2 inline-flex items-center gap-1 text-xs font-medium text-emerald-700 hover:text-emerald-900"
                    >
                      <ExternalLink className="h-3.5 w-3.5" aria-hidden="true" />
                      Open YouTube video
                    </a>
                  ) : null}
                </div>
                <div className="min-w-0">
                  <p className="truncate text-sm text-slate-700">{job.twitch_title}</p>
                  <a
                    href={job.twitch_url}
                    target="_blank"
                    rel="noreferrer"
                    className="mt-1 block truncate text-xs text-violet-700 hover:text-violet-900"
                  >
                    {job.twitch_url}
                  </a>
                </div>
                <div>
                  <span className={`inline-flex rounded-md px-2 py-1 text-xs font-semibold ${statusClass[job.status]}`}>
                    {job.status}
                  </span>
                  <p className="mt-2 text-xs text-slate-500">Retries: {job.retry_count}</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="h-2 w-full overflow-hidden rounded-md bg-slate-100">
                    <div className="h-full bg-violet-600" style={{ width: `${Math.max(0, Math.min(100, job.progress))}%` }} />
                  </div>
                  <span className="w-10 text-right text-xs tabular-nums text-slate-500">{Math.round(job.progress)}%</span>
                </div>
                <div className="flex items-start gap-2">
                  {job.status === "failed" ? (
                    <button
                      type="button"
                      onClick={() => onRetry(job.id)}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                      title="Retry failed job"
                    >
                      <RotateCcw className="h-4 w-4" aria-hidden="true" />
                    </button>
                  ) : null}
                  {job.status === "queued" ? (
                    <button
                      type="button"
                      onClick={() => onCancel(job.id)}
                      className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-700 hover:bg-slate-50"
                      title="Cancel queued job"
                    >
                      <XCircle className="h-4 w-4" aria-hidden="true" />
                    </button>
                  ) : null}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
