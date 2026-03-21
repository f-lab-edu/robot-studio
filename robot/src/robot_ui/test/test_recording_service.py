import asyncio
import pytest
import numpy as np
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch


# rclpy / cv_bridge / sensor_msgs / cv2 를 import 전에 mock
with patch("rclpy.logging.get_logger"), \
     patch("cv_bridge.CvBridge"), \
     patch("cv2.VideoWriter"), \
     patch("cv2.VideoWriter_fourcc", return_value=0x6d703476):
    from robot_ui.services.recording_service import RecordingService


def make_service():
    mock_upload = AsyncMock()
    mock_upload.upload_with_retry = AsyncMock(return_value=True)
    with patch("cv_bridge.CvBridge"):
        service = RecordingService(upload_service=mock_upload)
    return service, mock_upload


FAKE_FRAME = np.zeros((480, 640, 3), dtype=np.uint8)


# ──────────────────────────────────────────────
# on_frame_received
# ──────────────────────────────────────────────

def test_on_frame_received_appends_frame():
    service, _ = make_service()
    service.bridge.imgmsg_to_cv2 = MagicMock(return_value=FAKE_FRAME)

    msg = MagicMock()
    service.on_frame_received(msg)

    assert len(service.collected_frames) == 1


def test_on_frame_received_multiple_frames():
    service, _ = make_service()
    service.bridge.imgmsg_to_cv2 = MagicMock(return_value=FAKE_FRAME)

    for _ in range(5):
        service.on_frame_received(MagicMock())

    assert len(service.collected_frames) == 5


def test_on_frame_received_bridge_error_ignored():
    service, _ = make_service()
    service.bridge.imgmsg_to_cv2 = MagicMock(side_effect=Exception("bridge error"))

    service.on_frame_received(MagicMock())

    assert len(service.collected_frames) == 0


# ──────────────────────────────────────────────
# _save_video
# ──────────────────────────────────────────────

def test_save_video_returns_none_when_no_frames():
    service, _ = make_service()
    assert service._save_video() is None


def test_save_video_returns_path_when_frames_exist():
    service, _ = make_service()
    service.collected_frames = [FAKE_FRAME.copy(), FAKE_FRAME.copy()]

    mock_writer = MagicMock()
    with patch("cv2.VideoWriter", return_value=mock_writer), \
         patch("cv2.VideoWriter_fourcc", return_value=0):
        path = service._save_video()

    assert path is not None
    assert isinstance(path, str)


def test_save_video_file_created():
    service, _ = make_service()
    service.collected_frames = [FAKE_FRAME.copy()]

    mock_writer = MagicMock()
    with patch("cv2.VideoWriter", return_value=mock_writer), \
         patch("cv2.VideoWriter_fourcc", return_value=0):
        path = service._save_video()

    # tempfile은 생성되지만 VideoWriter는 mock이므로 실제 파일은 비어있음
    # 경로가 문자열인지만 확인
    assert isinstance(path, str)
    # 정리
    Path(path).unlink(missing_ok=True)


# ──────────────────────────────────────────────
# _upload_episodes
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_upload_episodes_calls_upload_with_retry():
    service, mock_upload = make_service()
    queue = asyncio.Queue()

    import tempfile, os
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    await queue.put((0, tmp.name))
    await queue.put(None)

    settings = {"topic": "camera", "episodes": 1}
    await service._upload_episodes(settings, queue, None, None)

    mock_upload.upload_with_retry.assert_called_once_with(
        tmp.name, "camera/episode_0000.mp4"
    )


@pytest.mark.asyncio
async def test_upload_episodes_calls_on_progress_on_success():
    service, mock_upload = make_service()
    on_progress = MagicMock()
    queue = asyncio.Queue()

    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()

    await queue.put((0, tmp.name))
    await queue.put(None)

    settings = {"topic": "camera", "episodes": 1}
    await service._upload_episodes(settings, queue, None, on_progress)

    on_progress.assert_called_once_with(0)


@pytest.mark.asyncio
async def test_upload_episodes_deletes_temp_file():
    service, mock_upload = make_service()
    queue = asyncio.Queue()

    import tempfile
    tmp = tempfile.NamedTemporaryFile(suffix=".mp4", delete=False)
    tmp.close()
    tmp_path = tmp.name

    await queue.put((0, tmp_path))
    await queue.put(None)

    settings = {"topic": "camera", "episodes": 1}
    await service._upload_episodes(settings, queue, None, None)

    assert not Path(tmp_path).exists()


@pytest.mark.asyncio
async def test_upload_episodes_stops_on_none():
    service, mock_upload = make_service()
    queue = asyncio.Queue()
    await queue.put(None)

    settings = {"topic": "camera", "episodes": 0}
    await service._upload_episodes(settings, queue, None, None)

    mock_upload.upload_with_retry.assert_not_called()


# ──────────────────────────────────────────────
# _collect_episodes
# ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_collect_episodes_calls_on_status_per_episode():
    service, _ = make_service()
    on_status = MagicMock()
    queue = asyncio.Queue()

    service.collected_frames = [FAKE_FRAME.copy()]

    mock_writer = MagicMock()
    with patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("cv2.VideoWriter", return_value=mock_writer), \
         patch("cv2.VideoWriter_fourcc", return_value=0):
        settings = {"episodes": 3, "data_length": 1.0, "term_length": 0}
        await service._collect_episodes(settings, queue, on_status)

    assert on_status.call_count >= 3


@pytest.mark.asyncio
async def test_collect_episodes_puts_none_at_end():
    service, _ = make_service()
    queue = asyncio.Queue()

    service.collected_frames = [FAKE_FRAME.copy()]

    mock_writer = MagicMock()
    with patch("asyncio.sleep", new_callable=AsyncMock), \
         patch("cv2.VideoWriter", return_value=mock_writer), \
         patch("cv2.VideoWriter_fourcc", return_value=0):
        settings = {"episodes": 1, "data_length": 1.0, "term_length": 0}
        await service._collect_episodes(settings, queue, None)

    sentinel = await queue.get()
    assert sentinel is None


@pytest.mark.asyncio
async def test_collect_episodes_calls_sleep_with_data_length():
    service, _ = make_service()
    queue = asyncio.Queue()

    service.collected_frames = [FAKE_FRAME.copy()]

    mock_writer = MagicMock()
    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep, \
         patch("cv2.VideoWriter", return_value=mock_writer), \
         patch("cv2.VideoWriter_fourcc", return_value=0):
        settings = {"episodes": 1, "data_length": 5.0, "term_length": 0}
        await service._collect_episodes(settings, queue, None)

    sleep_args = [call.args[0] for call in mock_sleep.call_args_list]
    assert 5.0 in sleep_args
