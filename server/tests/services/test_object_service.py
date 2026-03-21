from unittest.mock import MagicMock
from app.services.object_service import ObjectService
from app.core.config import settings


class TestObjectService:
    def _make_service(self, mock_url: str = "https://s3.example.com/presigned"):
        mock_s3 = MagicMock()
        mock_s3.generate_presigned_url.return_value = mock_url
        return ObjectService(mock_s3), mock_s3

    def test_returns_presigned_url(self):
        service, _ = self._make_service()
        url = service.create_presigned_upload_url("dataset/episode_0001.mp4")
        assert url == "https://s3.example.com/presigned"

    def test_calls_put_object_operation(self):
        service, mock_s3 = self._make_service()
        service.create_presigned_upload_url("dataset/episode_0001.mp4")
        args, kwargs = mock_s3.generate_presigned_url.call_args
        assert args[0] == "put_object"

    def test_passes_correct_bucket_and_key(self):
        service, mock_s3 = self._make_service()
        object_key = "my-topic/episode_0001.mp4"
        service.create_presigned_upload_url(object_key)
        _, kwargs = mock_s3.generate_presigned_url.call_args
        assert kwargs["Params"]["Bucket"] == settings.S3_BUCKET_NAME
        assert kwargs["Params"]["Key"] == object_key

    def test_passes_video_mp4_content_type(self):
        service, mock_s3 = self._make_service()
        service.create_presigned_upload_url("video.mp4")
        _, kwargs = mock_s3.generate_presigned_url.call_args
        assert kwargs["Params"]["ContentType"] == "video/mp4"

    def test_passes_correct_expiry(self):
        service, mock_s3 = self._make_service()
        service.create_presigned_upload_url("video.mp4")
        _, kwargs = mock_s3.generate_presigned_url.call_args
        expected_expires = settings.PRESIGNED_URL_EXPIRE_MINUTES * 60
        assert kwargs["ExpiresIn"] == expected_expires
