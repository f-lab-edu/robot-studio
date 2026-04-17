import json
from io import BytesIO

import pyarrow.parquet as pq

from app.core.config import settings
from app.schemas.dataset import (
    DatasetSummary,
    EpisodeResponse,
    FrameData,
    VideoUrlResponse,
)


class DatasetService:
    def __init__(self, s3_client):
        self.client = s3_client
        self.bucket = settings.S3_BUCKET_NAME

    def list_datasets(self) -> list[DatasetSummary]:
        resp = self.client.list_objects_v2(Bucket=self.bucket, Delimiter="/")
        prefixes = resp.get("CommonPrefixes") or []
        return [DatasetSummary(name=p["Prefix"].rstrip("/")) for p in prefixes]

    def get_dataset_info(self, name: str) -> dict:
        obj = self.client.get_object(Bucket=self.bucket, Key=f"{name}/meta/info.json")
        data = json.loads(obj["Body"].read())
        data["name"] = name
        return data

    def list_episodes(self, name: str) -> list[EpisodeResponse]:
        obj = self.client.get_object(Bucket=self.bucket, Key=f"{name}/meta/episodes.jsonl")
        lines = obj["Body"].read().decode().splitlines()
        return [EpisodeResponse(**json.loads(line)) for line in lines if line.strip()]

    def get_episode(self, name: str, episode_index: int) -> EpisodeResponse | None:
        episodes = self.list_episodes(name)
        for ep in episodes:
            if ep.episode_index == episode_index:
                return ep
        return None

    def get_video_urls(self, name: str, episode_index: int) -> list[VideoUrlResponse]:
        info = self.get_dataset_info(name)
        episode = self.get_episode(name, episode_index)
        if episode is None:
            return []

        cameras = [k for k in info.get("features", {}) if k.startswith("observation.images.")]
        chunk = episode.chunk_index
        ep_str = f"episode_{episode_index:06d}"
        expires = 3600

        urls = []
        for camera in cameras:
            key = f"{name}/videos/chunk-{chunk:03d}/{camera}/{ep_str}.mp4"
            url = self.client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket, "Key": key},
                ExpiresIn=expires,
            )
            urls.append(VideoUrlResponse(camera=camera, url=url, expires_in=expires))
        return urls

    def get_episode_frames(self, name: str, episode_index: int) -> tuple[int, list[FrameData]]:
        info = self.get_dataset_info(name)
        fps = info.get("fps", 30)
        episode = self.get_episode(name, episode_index)
        if episode is None:
            return fps, []

        chunk = episode.chunk_index
        key = f"{name}/data/chunk-{chunk:03d}/episode_{episode_index:06d}.parquet"
        obj = self.client.get_object(Bucket=self.bucket, Key=key)
        table = pq.read_table(BytesIO(obj["Body"].read()))

        frame_indices = table.column("frame_index").to_pylist()
        timestamps = table.column("timestamp").to_pylist()
        states = table.column("observation.state").to_pylist()
        actions = table.column("action").to_pylist()

        frames = [
            FrameData(
                frame_index=int(frame_indices[i]),
                timestamp=float(timestamps[i]),
                observation_state=list(states[i]),
                action=list(actions[i]),
            )
            for i in range(len(frame_indices))
        ]
        return fps, frames
