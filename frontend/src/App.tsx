import { useCallback, useEffect, useMemo, useState } from "react";

import { cancelJob, createJobs, getAuthStatus, getJobs, getVods, retryJob } from "./api/client";
import AuthStatus from "./components/AuthStatus";
import JobQueue from "./components/JobQueue";
import SelectedVodEditor from "./components/SelectedVodEditor";
import VodList from "./components/VodList";
import type { AuthStatus as AuthStatusType, SelectedVodDraft, TwitchVod, UploadJob } from "./types";

const defaultAuthStatus: AuthStatusType = { twitch: false, google: false };

function draftFromVod(vod: TwitchVod): SelectedVodDraft {
  return {
    twitch_vod_id: vod.id,
    twitch_url: vod.url,
    twitch_title: vod.title,
    youtube_title: vod.title.slice(0, 100),
    youtube_description: `Originally streamed on Twitch: ${vod.url}`,
    privacy_status: "private"
  };
}

function readOauthMessage() {
  const params = new URLSearchParams(window.location.search);
  const provider = params.get("provider");
  const status = params.get("status");
  const message = params.get("message");
  if (!provider || !status) return null;
  window.history.replaceState({}, document.title, window.location.pathname);
  return `${provider} ${status}${message ? `: ${message}` : ""}`;
}

export default function App() {
  const [authStatus, setAuthStatus] = useState(defaultAuthStatus);
  const [vods, setVods] = useState<TwitchVod[]>([]);
  const [selectedDrafts, setSelectedDrafts] = useState<Record<string, SelectedVodDraft>>({});
  const [jobs, setJobs] = useState<UploadJob[]>([]);
  const [loadingVods, setLoadingVods] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [notice, setNotice] = useState<string | null>(() => readOauthMessage());
  const [error, setError] = useState<string | null>(null);

  const selectedList = useMemo(() => Object.values(selectedDrafts), [selectedDrafts]);
  const selectedIds = useMemo(() => new Set(Object.keys(selectedDrafts)), [selectedDrafts]);

  const refreshAuth = useCallback(async () => {
    try {
      setAuthStatus(await getAuthStatus());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load auth status.");
    }
  }, []);

  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await getJobs());
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load jobs.");
    }
  }, []);

  useEffect(() => {
    void refreshAuth();
    void refreshJobs();
  }, [refreshAuth, refreshJobs]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      void refreshJobs();
    }, 4000);
    return () => window.clearInterval(interval);
  }, [refreshJobs]);

  async function fetchVods() {
    setLoadingVods(true);
    setError(null);
    setNotice(null);
    try {
      const latest = await getVods();
      setVods(latest);
      setNotice(`Fetched ${latest.length} Twitch VODs.`);
      await refreshAuth();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not fetch Twitch VODs.");
    } finally {
      setLoadingVods(false);
    }
  }

  function toggleVod(vod: TwitchVod) {
    setSelectedDrafts((current) => {
      const next = { ...current };
      if (next[vod.id]) {
        delete next[vod.id];
      } else {
        next[vod.id] = draftFromVod(vod);
      }
      return next;
    });
  }

  function updateDraft(vodId: string, patch: Partial<SelectedVodDraft>) {
    setSelectedDrafts((current) => ({
      ...current,
      [vodId]: { ...current[vodId], ...patch }
    }));
  }

  async function submitJobs() {
    setSubmitting(true);
    setError(null);
    setNotice(null);
    try {
      await createJobs(selectedList);
      setSelectedDrafts({});
      setNotice(`Added ${selectedList.length} ${selectedList.length === 1 ? "job" : "jobs"} to the queue.`);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not create upload jobs.");
    } finally {
      setSubmitting(false);
    }
  }

  async function handleRetry(jobId: number) {
    setError(null);
    try {
      await retryJob(jobId);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not retry job.");
    }
  }

  async function handleCancel(jobId: number) {
    setError(null);
    try {
      await cancelJob(jobId);
      await refreshJobs();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not cancel job.");
    }
  }

  return (
    <div className="min-h-screen">
      <AuthStatus authStatus={authStatus} onRefresh={refreshAuth} />
      <main className="mx-auto grid w-full max-w-7xl gap-6 px-4 py-6 md:px-6 xl:grid-cols-[minmax(0,1.35fr)_minmax(360px,0.65fr)]">
        <div className="space-y-6">
          {notice ? (
            <div className="rounded-md border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
              {notice}
            </div>
          ) : null}
          {error ? (
            <div className="rounded-md border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800">{error}</div>
          ) : null}
          <VodList vods={vods} selectedIds={selectedIds} loading={loadingVods} onFetch={fetchVods} onToggle={toggleVod} />
        </div>
        <div className="space-y-6">
          <SelectedVodEditor
            selected={selectedList}
            submitting={submitting}
            onChange={updateDraft}
            onSubmit={submitJobs}
          />
        </div>
        <div className="xl:col-span-2">
          <JobQueue jobs={jobs} onRetry={handleRetry} onCancel={handleCancel} />
        </div>
      </main>
    </div>
  );
}

