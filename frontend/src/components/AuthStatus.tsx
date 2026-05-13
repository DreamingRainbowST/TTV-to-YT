import { Link, Plug, RefreshCw } from "lucide-react";

import { API_BASE_URL } from "../api/client";
import type { AuthStatus as AuthStatusType } from "../types";

interface Props {
  authStatus: AuthStatusType;
  onRefresh: () => void;
}

function Badge({ connected, label }: { connected: boolean; label: string }) {
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-md border px-3 py-2 text-sm font-medium ${
        connected
          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
          : "border-slate-200 bg-white text-slate-600"
      }`}
    >
      <span className={`h-2 w-2 rounded-full ${connected ? "bg-emerald-500" : "bg-slate-300"}`} />
      {label} {connected ? "connected" : "not connected"}
    </span>
  );
}

export default function AuthStatus({ authStatus, onRefresh }: Props) {
  return (
    <div className="flex flex-col gap-3 border-b border-slate-200 bg-white px-4 py-4 md:flex-row md:items-center md:justify-between md:px-6">
      <div>
        <h1 className="text-xl font-semibold tracking-normal text-slate-950">Twitch VOD to YouTube Uploader</h1>
        <p className="mt-1 text-sm text-slate-500">Local queue for VODs you own or have rights to upload.</p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Badge connected={authStatus.twitch} label="Twitch" />
        <Badge connected={authStatus.google} label="Google" />
        <a
          href={`${API_BASE_URL}/auth/twitch/login`}
          className="inline-flex min-h-10 items-center gap-2 rounded-md bg-violet-700 px-3 py-2 text-sm font-semibold text-white hover:bg-violet-800"
        >
          <Plug className="h-4 w-4" aria-hidden="true" />
          Connect Twitch
        </a>
        <a
          href={`${API_BASE_URL}/auth/google/login`}
          className="inline-flex min-h-10 items-center gap-2 rounded-md bg-slate-900 px-3 py-2 text-sm font-semibold text-white hover:bg-slate-800"
        >
          <Link className="h-4 w-4" aria-hidden="true" />
          Connect Google
        </a>
        <button
          type="button"
          onClick={onRefresh}
          className="inline-flex h-10 w-10 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-700 hover:bg-slate-50"
          title="Refresh connection status"
        >
          <RefreshCw className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}

