import asyncio
import subprocess
import tempfile
import time
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


# ---------------------------------------------------------------------------
# MultiCameraRecordingService
# ---------------------------------------------------------------------------

def _check_av1_support() -> bool:
    result = subprocess.run(["ffmpeg", "-encoders"], capture_output=True, text=True)
    return "libsvtav1" in result.stdout


def _encode_video_sync(frames_dir: Path, output_path: Path, fps: int = 30):
    """PNG 시퀀스를 AV1(또는 H264) MP4로 인코딩 (동기 — asyncio.to_thread로 호출)"""
    codec = "libsvtav1" if _check_av1_support() else "libx264"
    crf   = "50" if codec == "libsvtav1" else "23"
    extra = ["-preset", "6"] if codec == "libsvtav1" else ["-preset", "fast"]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run([
        "ffmpeg", "-y",
        "-f", "image2", "-framerate", str(fps),
        "-i", str(frames_dir / "%06d.png"),
        "-vcodec", codec, "-pix_fmt", "yuv420p",
        "-crf", crf, *extra,
        str(output_path),
    ], check=True, capture_output=True)


multi_camera_logger = get_logger('MultiCameraRecordingService')


class MultiCameraRecordingService:
    """
    camera_roles: dict[str, str]  — {"top": "/camera_0/image_raw", "wrist": "/camera_2/image_raw"}
    joint_collector: JointStateCollector — 필수 (Optional 아님)
    """

    def __init__(self, upload_service, joint_collector, metadata_service, parquet_writer):
        self.upload_service   = upload_service
        self.joint_collector  = joint_collector
        self.metadata_service = metadata_service
        self.parquet_writer   = parquet_writer
        self.bridge           = CvBridge()

        self._frame_dirs: dict[str, Path] = {}
        self._frame_timestamps: dict[str, list] = {}
        self._frame_counters: dict[str, int] = {}

    def start_episode(self, session_dir: Path, episode_index: int, camera_roles: dict):
        """에피소드 시작 시 role별 PNG 저장 디렉토리 초기화"""
        self._frame_dirs.clear()
        self._frame_timestamps.clear()
        self._frame_counters.clear()
        for role in camera_roles:
            png_dir = session_dir / "frames" / f"episode_{episode_index:06d}" / role
            png_dir.mkdir(parents=True, exist_ok=True)
            self._frame_dirs[role] = png_dir
            self._frame_timestamps[role] = []
            self._frame_counters[role] = 0

    def on_frame_received(self, role: str, msg: Image):
        """프레임 수신 즉시 PNG로 저장 — 메모리 버퍼 없음"""
        if role not in self._frame_dirs:
            return
        try:
            cv_image = self.bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            idx = self._frame_counters[role]
            cv2.imwrite(str(self._frame_dirs[role] / f"{idx:06d}.png"), cv_image)
            self._frame_timestamps[role].append(time.time())
            self._frame_counters[role] += 1
        except Exception as e:
            multi_camera_logger.error(f"[{role}] frame save failed: {e}")

    async def run(
        self,
        settings: dict,
        session_dir: Path,
        on_status: Optional[Callable[[str], None]] = None,
        on_progress: Optional[Callable[[int], None]] = None,
        ask_result: Optional[Callable[[int], bool]] = None,
    ):
        queue = asyncio.Queue()
        await asyncio.gather(
            self._collect_episodes(settings, session_dir, queue, on_status, on_progress, ask_result),
            self._process_episodes(settings, session_dir, queue, on_status, on_progress),
        )

    async def _collect_episodes(
        self,
        settings: dict,
        session_dir: Path,
        queue: asyncio.Queue,
        on_status, on_progress, ask_result,
    ):
        """수집 루프 (producer): 에피소드 수집 후 episode_data를 queue에 넣는다."""
        episodes     = settings.get('episodes', 1)
        data_length  = settings.get('data_length', 10.0)
        term_length  = settings.get('term_length', 1.0)
        camera_roles = settings['camera_roles']
        language     = settings.get('language_instruction', '')
        chunk_index  = 0

        for i in range(episodes):
            if on_status:
                on_status(f"Recording episode {i + 1}/{episodes}...")

            self.start_episode(session_dir, i, camera_roles)
            self.joint_collector.start_episode()

            await asyncio.sleep(data_length)

            # 성공/실패 팝업
            success = True
            if ask_result:
                success = await ask_result(i)

            # align_to_frames는 start_episode() 전에 호출해야 버퍼가 유효함
            primary_role     = next(iter(camera_roles))
            frame_timestamps = list(self._frame_timestamps[primary_role])  # 복사
            joint_records    = self.joint_collector.align_to_frames(frame_timestamps)

            await queue.put({
                'episode_index':        i,
                'chunk_index':          chunk_index,
                'frame_timestamps':     frame_timestamps,
                'joint_records':        joint_records,
                'success':              success,
                'language_instruction': language,
            })

            if i < episodes - 1 and term_length > 0:
                if on_status:
                    on_status(f"Waiting {term_length}s before next episode...")
                await asyncio.sleep(term_length)

        await queue.put(None)  # sentinel: 워커 종료 신호

    async def _process_episodes(
        self,
        settings: dict,
        session_dir: Path,
        queue: asyncio.Queue,
        on_status, on_progress,
    ):
        """인코딩+업로드 워커 (consumer): queue에서 하나씩 꺼내 순서대로 처리한다."""
        dataset_name = settings['dataset_name']
        camera_roles = settings['camera_roles']

        while True:
            item = await queue.get()
            if item is None:
                break

            i             = item['episode_index']
            chunk_index   = item['chunk_index']
            timestamps    = item['frame_timestamps']
            joint_records = item['joint_records']
            success       = item['success']
            language      = item['language_instruction']

            if on_status:
                on_status(f"Encoding episode {i + 1}...")

            # ffmpeg 인코딩 — asyncio.to_thread로 실행 (subprocess 블로킹 방지)
            for role in camera_roles:
                png_dir  = session_dir / "frames" / f"episode_{i:06d}" / role
                out_path = (session_dir / "videos" / f"chunk-{chunk_index:03d}"
                            / f"observation.images.{role}" / f"episode_{i:06d}.mp4")
                await asyncio.to_thread(_encode_video_sync, png_dir, out_path)

            # Parquet 저장
            parquet_path = (session_dir / "data" / f"chunk-{chunk_index:03d}"
                            / f"episode_{i:06d}.parquet")
            self.parquet_writer.write(
                output_path=parquet_path,
                episode_index=i,
                joint_records=joint_records,
                frame_timestamps=timestamps,
                language_instruction=language,
                success=success,
            )

            # 메타데이터 업데이트
            self.metadata_service.append_episode(
                episode_index=i,
                length=len(timestamps),
                success=success,
                language_instruction=language,
                chunk_index=chunk_index,
            )

            if on_status:
                on_status(f"Uploading episode {i + 1}...")

            await self.upload_service.upload_episode(
                session_dir=session_dir,
                dataset_name=dataset_name,
                episode_index=i,
                chunk_index=chunk_index,
                camera_roles=list(camera_roles.keys()),
            )

            if on_progress:
                on_progress(i)

        # 모든 에피소드 처리 완료 후 메타 업로드
        self.metadata_service.finalize()
        await self.upload_service.upload_meta(session_dir, dataset_name)
