const BASE = "/api/v1";

export interface DatasetSummary {
  name: string;
}

export interface DatasetInfo {
  name: string;
  robot_type: string;
  fps: number;
  total_episodes: number;
  total_frames: number;
  total_successes: number;
  features: Record<string, { dtype: string; shape: number[]; names?: string[] }>;
}

export interface Episode {
  episode_index: number;
  length: number;
  success: boolean;
  language_instruction: string;
  chunk_index: number;
  timestamp: string;
}

export interface FrameData {
  frame_index: number;
  timestamp: number;
  observation_state: number[];
  action: number[];
}

export interface EpisodeFramesResponse {
  fps: number;
  frames: FrameData[];
}

export interface VideoUrl {
  camera: string;
  url: string;
  expires_in: number;
}

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.json();
}

export const listDatasets = () =>
  apiFetch<{ datasets: DatasetSummary[] }>("/datasets/").then((r) => r.datasets);

export const getDatasetInfo = (name: string) =>
  apiFetch<DatasetInfo>(`/datasets/${encodeURIComponent(name)}`);

export const listEpisodes = (name: string) =>
  apiFetch<{ dataset_name: string; episodes: Episode[] }>(
    `/datasets/${encodeURIComponent(name)}/episodes`
  ).then((r) => r.episodes);

export const getVideoUrls = (name: string, episodeIndex: number) =>
  apiFetch<VideoUrl[]>(
    `/datasets/${encodeURIComponent(name)}/episodes/${episodeIndex}/video-urls`
  );

export const getEpisodeFrames = (name: string, episodeIndex: number) =>
  apiFetch<EpisodeFramesResponse>(
    `/datasets/${encodeURIComponent(name)}/episodes/${episodeIndex}/frames`
  );

export const getVideoProxyUrl = (name: string, episodeIndex: number, camera: string) =>
  `/api/v1/datasets/${encodeURIComponent(name)}/episodes/${episodeIndex}/video?camera=${encodeURIComponent(camera)}`;
