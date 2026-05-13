import { Send } from "lucide-react";

import type { PrivacyStatus, SelectedVodDraft } from "../types";

interface Props {
  selected: SelectedVodDraft[];
  submitting: boolean;
  onChange: (vodId: string, patch: Partial<SelectedVodDraft>) => void;
  onSubmit: () => void;
}

const privacyOptions: PrivacyStatus[] = ["private", "unlisted", "public"];

export default function SelectedVodEditor({ selected, submitting, onChange, onSubmit }: Props) {
  return (
    <section>
      <div className="mb-3">
        <h2 className="text-base font-semibold text-slate-950">Selected VOD Metadata</h2>
        <p className="text-sm text-slate-500">Set YouTube metadata before adding jobs to the local queue.</p>
      </div>
      {selected.length === 0 ? (
        <div className="rounded-md border border-dashed border-slate-300 bg-white px-4 py-8 text-center text-sm text-slate-500">
          Select one or more VODs to edit upload metadata.
        </div>
      ) : (
        <div className="space-y-3">
          {selected.map((draft) => (
            <div key={draft.twitch_vod_id} className="rounded-md border border-slate-200 bg-white p-4 shadow-sm">
              <div className="mb-3">
                <p className="line-clamp-2 text-sm font-semibold text-slate-900">{draft.twitch_title}</p>
                <a
                  href={draft.twitch_url}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-1 block break-all text-xs text-violet-700 hover:text-violet-900"
                >
                  {draft.twitch_url}
                </a>
              </div>
              <div className="grid gap-3">
                <label className="grid gap-1 text-sm font-medium text-slate-700">
                  YouTube title
                  <input
                    value={draft.youtube_title}
                    onChange={(event) => onChange(draft.twitch_vod_id, { youtube_title: event.target.value })}
                    className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                    maxLength={100}
                  />
                </label>
                <label className="grid gap-1 text-sm font-medium text-slate-700">
                  Description
                  <textarea
                    value={draft.youtube_description}
                    onChange={(event) => onChange(draft.twitch_vod_id, { youtube_description: event.target.value })}
                    className="min-h-24 resize-y rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                  />
                </label>
                <label className="grid gap-1 text-sm font-medium text-slate-700">
                  Privacy
                  <select
                    value={draft.privacy_status}
                    onChange={(event) =>
                      onChange(draft.twitch_vod_id, { privacy_status: event.target.value as PrivacyStatus })
                    }
                    className="min-h-10 rounded-md border border-slate-300 px-3 py-2 text-sm text-slate-950 outline-none focus:border-violet-500 focus:ring-2 focus:ring-violet-100"
                  >
                    {privacyOptions.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            </div>
          ))}
          <button
            type="button"
            onClick={onSubmit}
            disabled={submitting}
            className="inline-flex min-h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
          >
            <Send className="h-4 w-4" aria-hidden="true" />
            Add {selected.length} {selected.length === 1 ? "job" : "jobs"} to queue
          </button>
        </div>
      )}
    </section>
  );
}

