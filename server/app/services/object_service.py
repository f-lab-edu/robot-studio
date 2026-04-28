from app.core.config import settings

class ObjectService:
    def __init__(self, s3_client):
        self.client = s3_client

    def create_presigned_upload_url(self, object_key: str) -> str:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": settings.S3_BUCKET_NAME,
                "Key": object_key,
                "ContentType": "video/mp4",
            },
            ExpiresIn=settings.PRESIGNED_URL_EXPIRE_MINUTES * 60,
        )

        return url
