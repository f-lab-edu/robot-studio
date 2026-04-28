import aiohttp


class ApiClient:
    """백엔드 API 클라이언트"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._session: aiohttp.ClientSession | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_presigned_url(self, object_name: str) -> str:
        """단일 presigned URL 요청"""
        async with self.session.post(
            f"{self.base_url}/api/v1/objects/presigned-upload-url",
            json={"object_name": object_name},
            timeout=aiohttp.ClientTimeout(total=10)
        ) as response:
            response.raise_for_status()
            data = await response.json()
            return data['url']

    async def upload_to_s3(
        self,
        presigned_url: str,
        file_path: str,
        content_type: str = "video/mp4",
    ):
        """Presigned URL로 파일 업로드"""
        with open(file_path, 'rb') as f:
            data = f.read()

        async with self.session.put(
            presigned_url,
            data=data,
            headers={'Content-Type': content_type},
        ) as response:
            response.raise_for_status()
