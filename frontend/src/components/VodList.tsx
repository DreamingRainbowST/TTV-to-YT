import { RefreshCw } from "lucide-react";

import type { TwitchVod } from "../types";
import VodCard from "./VodCard";

interface Props {
  vods: TwitchVod[];
  selectedIds: Set<string>;
  loading: boolean;
  onFetch: () => void;
  onToggle: (vod: TwitchVod) => void;
}

export default function VodList({ vods, selectedIds, loading, onFetch, onToggle }: Props) {
  return (
    <section className="min-w-0">
      <div className="mb-3 flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-950">Latest Twitch VODs</h2>
          <p className="text-sm text-slate-500">Fetches the latest 20 archive videos from your connected Twitch account.</p>
        </div>
        <button
          type="button"
          onClick={onFetch}
          disabled={loading}
          className="inline-flex min-h-10 items-center justify-center gap-2 rounded-md bg-violet-700 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-800 disabled:cursor-not-allowed disabled:bg-slate-300"
        >
          <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} aria-hidden="true" />
          Fetch VODs
        </button>
      </div>
      {vods.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-10 text-center text-sm text-slate-500">
          Connect Twitch, then fetch VODs.
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

