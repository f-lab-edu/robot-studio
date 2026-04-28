from pydantic import BaseModel

class PresignedUploadUrlRequest(BaseModel):
    object_name: str

class PresignedUrlResponse(BaseModel):
    url: str
