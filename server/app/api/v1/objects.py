from fastapi import APIRouter, HTTPException, Depends

from app.schemas.object import PresignedUploadUrlRequest, PresignedUrlResponse
from app.services.object_service import ObjectService
from app.infra.s3 import get_s3_client
from app.api.v1.auth import get_current_user
from app.models.user import User

router = APIRouter(prefix="/objects", tags=["objects"])


def get_object_service(
    s3_client=Depends(get_s3_client)
) -> ObjectService:
    return ObjectService(s3_client)


@router.post("/presigned-upload-url", response_model=PresignedUrlResponse)
async def get_upload_url(
    request: PresignedUploadUrlRequest,
    current_user: User = Depends(get_current_user),
    service: ObjectService = Depends(get_object_service)
):
    try:
        url = service.create_presigned_upload_url(
            object_key=request.object_name
        )
        return PresignedUrlResponse(url=url)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate presigned URL: {str(e)}"
        )
