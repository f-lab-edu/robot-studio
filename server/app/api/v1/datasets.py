from fastapi import APIRouter, Depends, HTTPException

from app.infra.s3 import get_s3_client
from app.services.dataset_service import DatasetService
from app.schemas.dataset import (
    DatasetListResponse,
    DatasetInfoResponse,
    EpisodeListResponse,
    EpisodeResponse,
    EpisodeFramesResponse,
    VideoUrlResponse,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


def get_dataset_service(s3_client=Depends(get_s3_client)) -> DatasetService:
    return DatasetService(s3_client)


@router.get("/", response_model=DatasetListResponse)
def list_datasets(service: DatasetService = Depends(get_dataset_service)):
    datasets = service.list_datasets()
    return DatasetListResponse(datasets=datasets)


@router.get("/{dataset_name}", response_model=DatasetInfoResponse)
def get_dataset(dataset_name: str, service: DatasetService = Depends(get_dataset_service)):
    try:
        info = service.get_dataset_info(dataset_name)
        return DatasetInfoResponse(
            name=info["name"],
            robot_type=info.get("robot_type", ""),
            fps=info.get("fps", 30),
            total_episodes=info.get("total_episodes", 0),
            total_frames=info.get("total_frames", 0),
            total_successes=info.get("total_successes", 0),
            features=info.get("features", {}),
        )
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dataset_name}/episodes", response_model=EpisodeListResponse)
def list_episodes(dataset_name: str, service: DatasetService = Depends(get_dataset_service)):
    try:
        episodes = service.list_episodes(dataset_name)
        return EpisodeListResponse(dataset_name=dataset_name, episodes=episodes)
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{dataset_name}/episodes/{episode_index}", response_model=EpisodeResponse)
def get_episode(
    dataset_name: str,
    episode_index: int,
    service: DatasetService = Depends(get_dataset_service),
):
    episode = service.get_episode(dataset_name, episode_index)
    if episode is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return episode


@router.get("/{dataset_name}/episodes/{episode_index}/video-urls", response_model=list[VideoUrlResponse])
def get_video_urls(
    dataset_name: str,
    episode_index: int,
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        return service.get_video_urls(dataset_name, episode_index)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{dataset_name}/episodes/{episode_index}/frames", response_model=EpisodeFramesResponse)
def get_episode_frames(
    dataset_name: str,
    episode_index: int,
    service: DatasetService = Depends(get_dataset_service),
):
    try:
        fps, frames = service.get_episode_frames(dataset_name, episode_index)
        return EpisodeFramesResponse(fps=fps, frames=frames)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
