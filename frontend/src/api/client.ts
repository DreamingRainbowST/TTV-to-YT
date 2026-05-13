import type { AuthStatus, SelectedVodDraft, TwitchVod, UploadJob } from "../types";

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options?.headers ?? {})
    },
    ...options
  });

  if (!response.ok) {
    let message = `${response.status} ${response.statusText}`;
    try {
      const payload = await response.json();
      message = payload.detail ?? message;
    } catch {
      // Keep the status text fallback.
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

export function getAuthStatus(): Promise<AuthStatus> {
  return request<AuthStatus>("/api/auth/status");
}

export function getVods(channel?: string): Promise<TwitchVod[]> {
  const params = channel?.trim() ? `?channel=${encodeURIComponent(channel.trim())}` : "";
  return request<TwitchVod[]>(`/api/vods${params}`);
}

export function createJobs(jobs: SelectedVodDraft[]): Promise<UploadJob[]> {
  return request<UploadJob[]>("/api/jobs", {
    method: "POST",
    body: JSON.stringify({ jobs })
  });
}

export function getJobs(): Promise<UploadJob[]> {
  return request<UploadJob[]>("/api/jobs");
}

export function retryJob(jobId: number): Promise<UploadJob> {
  return request<UploadJob>(`/api/jobs/${jobId}/retry`, { method: "POST" });
}

export function cancelJob(jobId: number): Promise<UploadJob> {
  return request<UploadJob>(`/api/jobs/${jobId}/cancel`, { method: "POST" });
}
