import { RefreshCw } from "lucide-react";

import type { TwitchVod } from "../types";
import VodCard from "./VodCard";

interface Props {
  vods: TwitchVod[];
  selectedIds: Set<string>;
  channel: string;
  loading: boolean;
  onChannelChange: (channel: string) => void;
  onFetch: () => void;
  onToggle: (vod: TwitchVod) => void;
}

export default function VodList({ vods, selectedIds, channel, loading, onChannelChange, onFetch, onToggle }: Props) {
  return (
    <section className="min-w-0">
      <div className="mb-3 grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(280px,420px)] lg:items-end">
        <div>
          <h2 className="text-base font-semibold text-slate-950">Latest Twitch VODs</h2>
          <p className="text-sm text-slate-500">Fetches the latest 20 public past broadcasts by channel name. Twitch login is optional.</p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row">
          <label className="grid flex-1 gap-1 text-sm font-medium text-slate-700">
            Twitch channel
            <input
              value={channel}
              onChange={(event) => onChannelChange(event.target.value)}
              placeholder="lirik"
              className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
            />
          </label>
          <button
            type="button"
            onClick={onFetch}
            disabled={loading}
            className="inline-flex min-h-10 items-center justify-center gap-2 self-end rounded-md bg-violet-700 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
            Fetch VODs
          </button>
        </div>
      </div>
      {vods.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          Enter a public Twitch channel login, then fetch VODs.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {vods.map((vod) => (
            <VodCard key={vod.id} vod={vod} selected={selectedIds.has(vod.id)} onToggle={onToggle} />
          ))}
        </div>
      )}
    </section>
  );
}
