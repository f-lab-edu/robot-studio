import asyncio
from pathlib import Path
from rclpy.logging import get_logger

from ..utils.api_client import ApiClient

logger = get_logger('UploadService')


class UploadService:
    """S3 업로드 서비스 (presigned URL 요청 + 업로드 + 재시도)"""

    def __init__(self, api_client: ApiClient, max_retries: int = 3):
        self.api_client = api_client
        self.max_retries = max_retries

    async def upload_with_retry(
        self,
        file_path: str,
        object_name: str,
        content_type: str = "application/octet-stream",
    ) -> bool:
        for attempt in range(self.max_retries):
            try:
                presigned_url = await self.api_client.get_presigned_url(object_name, content_type)
                await self.api_client.upload_to_s3(presigned_url, file_path, content_type)
                return True

            except Exception as e:
                logger.warning(
                    f"Upload attempt {attempt + 1}/{self.max_retries} failed "
                    f"for '{object_name}': {e}"
                )
                if attempt < self.max_retries - 1:
                    delay = 2 ** attempt
                    logger.info(f"Retrying in {delay}s...")
                    await asyncio.sleep(delay)

        logger.error(f"Upload failed after {self.max_retries} attempts: '{object_name}'")
        return False

    async def upload_episode(
        self,
        session_dir: Path,
        dataset_name: str,
        episode_index: int,
        chunk_index: int,
        camera_roles: list[str],
    ) -> bool:
        """비디오(role별) + parquet 파일을 병렬 업로드"""
        chunk = f"chunk-{chunk_index:03d}"
        ep    = f"episode_{episode_index:06d}"

        tasks = []
        for role in camera_roles:
            local  = session_dir / "videos" / chunk / f"observation.images.{role}" / f"{ep}.mp4"
            s3_key = f"{dataset_name}/videos/{chunk}/observation.images.{role}/{ep}.mp4"
            tasks.append(self.upload_with_retry(str(local), s3_key, "video/mp4"))

        parquet_local = session_dir / "data" / chunk / f"{ep}.parquet"
        parquet_s3    = f"{dataset_name}/data/{chunk}/{ep}.parquet"
        tasks.append(self.upload_with_retry(str(parquet_local), parquet_s3, "application/octet-stream"))

        results = await asyncio.gather(*tasks)
        return all(results)

    async def upload_meta(self, session_dir: Path, dataset_name: str):
        """meta/ 디렉토리 전체 업로드"""
        for meta_file in (session_dir / "meta").iterdir():
            s3_key = f"{dataset_name}/meta/{meta_file.name}"
            await self.upload_with_retry(str(meta_file), s3_key, "application/json")
