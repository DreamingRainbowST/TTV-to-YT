import { ExternalLink } from "lucide-react";

import type { TwitchVod } from "../types";

interface Props {
  vod: TwitchVod;
  selected: boolean;
  onToggle: (vod: TwitchVod) => void;
}

function formatDate(value: string | null) {
  if (!value) return "Unknown date";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatViews(value: number | null) {
  if (value === null || value === undefined) return "Views unknown";
  return `${new Intl.NumberFormat().format(value)} views`;
}

export default function VodCard({ vod, selected, onToggle }: Props) {
  return (
    <article
      className={`grid gap-3 rounded-md border bg-white p-3 shadow-sm transition ${
        selected ? "border-violet-400 ring-2 ring-violet-100" : "border-slate-200"
      }`}
    >
      <button type="button" onClick={() => onToggle(vod)} className="text-left">
        <div className="aspect-video overflow-hidden rounded-md bg-slate-100">
          {vod.thumbnail_url ? (
            <img src={vod.thumbnail_url} alt="" className="h-full w-full object-cover" loading="lazy" />
          ) : (
            <div className="flex h-full items-center justify-center text-sm text-slate-500">No thumbnail</div>
          )}
        </div>
        <div className="mt-3">
          <h3 className="line-clamp-2 text-sm font-semibold leading-5 text-slate-950">{vod.title}</h3>
          <p className="mt-2 truncate text-xs font-medium text-slate-600">
            {[vod.uploader ?? vod.uploader_id, vod.game_name].filter(Boolean).join(" - ") || "Twitch VOD"}
          </p>
          <p className="mt-2 text-xs text-slate-500">{formatDate(vod.created_at)}</p>
          <p className="mt-1 text-xs text-slate-500">
            {vod.duration ?? "Unknown duration"} - {formatViews(vod.view_count)}
          </p>
        </div>
      </button>
      <div className="flex items-center justify-between gap-2">
        <label className="inline-flex items-center gap-2 text-sm font-medium text-slate-700">
          <input
            type="checkbox"
            checked={selected}
            onChange={() => onToggle(vod)}
            className="h-4 w-4 rounded border-slate-300 text-violet-700 focus:ring-violet-600"
          />
          Select
        </label>
        <a
          href={vod.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 text-slate-600 hover:bg-slate-50"
          title="Open Twitch VOD"
        >
          <ExternalLink className="h-4 w-4" aria-hidden="true" />
        </a>
      </div>
    </article>
  );
}
