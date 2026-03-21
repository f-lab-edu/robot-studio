import pytest
from unittest.mock import AsyncMock, patch

with patch("rclpy.logging.get_logger"):
    from robot_ui.services.upload_service import UploadService


@pytest.fixture
def mock_api_client():
    client = AsyncMock()
    client.get_presigned_url = AsyncMock(return_value="https://s3.example.com/presigned")
    client.upload_to_s3 = AsyncMock(return_value=None)
    return client


@pytest.fixture
def service(mock_api_client):
    return UploadService(api_client=mock_api_client, max_retries=3)


@pytest.mark.asyncio
async def test_first_attempt_success_returns_true(service, mock_api_client):
    result = await service.upload_with_retry("/tmp/video.mp4", "topic/ep_0001.mp4")
    assert result is True


@pytest.mark.asyncio
async def test_first_attempt_success_calls_get_presigned_url_once(service, mock_api_client):
    await service.upload_with_retry("/tmp/video.mp4", "topic/ep_0001.mp4")
    mock_api_client.get_presigned_url.assert_called_once_with("topic/ep_0001.mp4")


@pytest.mark.asyncio
async def test_retry_on_first_failure_returns_true(mock_api_client):
    mock_api_client.upload_to_s3.side_effect = [Exception("fail"), None]
    service = UploadService(api_client=mock_api_client, max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        result = await service.upload_with_retry("/tmp/video.mp4", "topic/ep.mp4")

    assert result is True
    assert mock_api_client.get_presigned_url.call_count == 2


@pytest.mark.asyncio
async def test_all_retries_fail_returns_false(mock_api_client):
    mock_api_client.upload_to_s3.side_effect = Exception("always fail")
    service = UploadService(api_client=mock_api_client, max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        result = await service.upload_with_retry("/tmp/video.mp4", "topic/ep.mp4")

    assert result is False


@pytest.mark.asyncio
async def test_all_retries_fail_calls_get_presigned_url_max_times(mock_api_client):
    mock_api_client.upload_to_s3.side_effect = Exception("always fail")
    service = UploadService(api_client=mock_api_client, max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        await service.upload_with_retry("/tmp/video.mp4", "topic/ep.mp4")

    assert mock_api_client.get_presigned_url.call_count == 3


@pytest.mark.asyncio
async def test_exponential_backoff_sleep_delays(mock_api_client):
    mock_api_client.upload_to_s3.side_effect = [
        Exception("fail"),
        Exception("fail"),
        None,
    ]
    service = UploadService(api_client=mock_api_client, max_retries=3)

    with patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
        await service.upload_with_retry("/tmp/video.mp4", "topic/ep.mp4")

    sleep_calls = [call.args[0] for call in mock_sleep.call_args_list]
    assert sleep_calls == [1, 2]  # 2^0=1, 2^1=2
