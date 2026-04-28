import asyncio
import tempfile
import cv2
from pathlib import Path
from typing import Callable, Optional
from rclpy.logging import get_logger
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from .upload_service import UploadService

logger = get_logger('RecordingService')


class RecordingService:
    """에피소드 수집 + 인코딩 + 업로드 파이프라인"""

    def __init__(self, upload_service: UploadService):
        self.upload_service = upload_service
        self.collected_frames: list = []
        self.bridge = CvBridge()

    def on_frame_received(self, msg: Image):
        """ROS2 Image 메시지 → cv2 프레임 변환 후 수집"""
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            self.collected_frames.append(cv_image.copy())
        except Exception as e:
            logger.error(f"Failed to convert frame: {e}")

    async def run(
        self,
        settings: dict,
        on_status: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
    ):
        """수집 → 인코딩 → 업로드 파이프라인 실행"""
        queue = asyncio.Queue()
        await asyncio.gather(
            self._collect_episodes(settings, queue, on_status),
            self._upload_episodes(settings, queue, on_status, on_progress),
        )

    async def _collect_episodes(
        self,
        settings: dict,
        queue: asyncio.Queue,
        on_status: Optional[Callable[[str], None]],
    ):
        episodes = settings.get('episodes', 1)
        data_length = settings.get('data_length', 10.0)
        term_length = settings.get('term_length', 1.0)

        for i in range(episodes):
            if on_status:
                on_status(f"Recording episode {i + 1}/{episodes}...")

            self.collected_frames = []
            await asyncio.sleep(data_length)

            if self.collected_frames:
                video_path = self._save_video()
                if video_path:
                    await queue.put((i, video_path))
                else:
                    logger.error(f"Failed to save video for episode {i + 1}")
            else:
                logger.error(f"No frames collected for episode {i + 1}")

            if i < episodes - 1 and term_length > 0:
                if on_status:
                    on_status(f"Waiting {term_length}s...")
                await asyncio.sleep(term_length)

        await queue.put(None)

    async def _upload_episodes(
        self,
        settings: dict,
        queue: asyncio.Queue,
        on_status: Optional[Callable[[str], None]],
        on_progress: Optional[Callable[[int], None]],
    ):
        topic = settings.get('topic', '')
        safe_topic = topic.strip('/').replace('/', '_')
        episodes = settings.get('episodes', 1)

        while True:
            item = await queue.get()
            if item is None:
                break

            episode_index, video_path = item
            object_name = f"{safe_topic}/episode_{episode_index:04d}.mp4"

            if on_status:
                on_status(f"Uploading episode {episode_index + 1}...")

            uploaded = await self.upload_service.upload_with_retry(video_path, object_name)
            Path(video_path).unlink(missing_ok=True)

            if uploaded:
                if on_progress:
                    on_progress(episode_index)
                logger.info(f"Episode {episode_index + 1}/{episodes} uploaded")
            else:
                logger.error(f"Episode {episode_index + 1} upload failed after max retries")

    def _save_video(self) -> Optional[str]:
        """수집된 프레임을 비디오 파일로 저장"""
        if not self.collected_frames:
            return None

        fps = 30
        height, width = self.collected_frames[0].shape[:2]

        temp_file = tempfile.NamedTemporaryFile(suffix='.mp4', delete=False)
        video_path = temp_file.name
        temp_file.close()

        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        out = cv2.VideoWriter(video_path, fourcc, fps, (width, height))

        for frame in self.collected_frames:
            out.write(frame)

        out.release()

        logger.info(f"Saved video: {video_path} ({len(self.collected_frames)} frames)")
        return video_path
