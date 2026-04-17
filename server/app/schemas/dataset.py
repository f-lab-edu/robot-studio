from pydantic import BaseModel


class DatasetSummary(BaseModel):
    name: str


class DatasetListResponse(BaseModel):
    datasets: list[DatasetSummary]


class DatasetInfoResponse(BaseModel):
    name: str
    robot_type: str
    fps: int
    total_episodes: int
    total_frames: int
    total_successes: int
    features: dict


class EpisodeResponse(BaseModel):
    episode_index: int
    length: int
    success: bool
    language_instruction: str
    chunk_index: int
    timestamp: str


class EpisodeListResponse(BaseModel):
    dataset_name: str
    episodes: list[EpisodeResponse]


class FrameData(BaseModel):
    frame_index: int
    timestamp: float
    observation_state: list[float]
    action: list[float]


class EpisodeFramesResponse(BaseModel):
    fps: int
    frames: list[FrameData]


class VideoUrlResponse(BaseModel):
    camera: str
    url: str
    expires_in: int
