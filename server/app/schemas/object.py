from pydantic import BaseModel

class PresignedUploadUrlRequest(BaseModel):
    object_name: str
    content_type: str = "application/octet-stream"

class PresignedUrlResponse(BaseModel):
    url: str
