export type PrivacyStatus = "private" | "unlisted" | "public";
export type JobStatus = "queued" | "downloading" | "downloaded" | "uploading" | "uploaded" | "failed" | "cancelled";

export interface AuthStatus {
  twitch: boolean;
  google: boolean;
}

export interface TwitchVod {
  id: string;
  title: string;
  url: string;
  thumbnail_url: string | null;
  created_at: string | null;
  duration: string | null;
  view_count: number | null;
  uploader: string | null;
  uploader_id: string | null;
  game_name: string | null;
}

export interface SelectedVodDraft {
  twitch_vod_id: string;
  twitch_url: string;
  twitch_title: string;
  youtube_title: string;
  youtube_description: string;
  privacy_status: PrivacyStatus;
  youtube_playlist_id?: string | null;
  youtube_playlist_title?: string | null;
}

export interface UploadJob {
  id: number;
  twitch_vod_id: string;
  twitch_url: string;
  twitch_title: string;
  youtube_title: string;
  youtube_description: string | null;
  privacy_status: PrivacyStatus;
  status: JobStatus;
  progress: number;
  local_file_path: string | null;
  youtube_video_id: string | null;
  youtube_url: string | null;
  youtube_playlist_id: string | null;
  youtube_playlist_title: string | null;
  youtube_playlist_item_id: string | null;
  error_message: string | null;
  retry_count: number;
  created_at: string;
  updated_at: string;
  started_at: string | null;
  finished_at: string | null;
}

export interface YouTubePlaylist {
  id: string;
  title: string;
  description: string | null;
  privacy_status: string | null;
  item_count: number | null;
}
