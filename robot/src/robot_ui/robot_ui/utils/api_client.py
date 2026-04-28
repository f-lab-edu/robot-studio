import aiohttp


class ApiClient:
    """백엔드 API 클라이언트"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self._session: aiohttp.ClientSession | None = None
        self._token: str | None = None
        self._refresh_token: str | None = None

    @property
    def session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()

    def set_token(self, access_token: str, refresh_token: str) -> None:
        self._token = access_token
        self._refresh_token = refresh_token

    async def _refresh_tokens(self) -> None:
        if not self._refresh_token:
            raise ValueError("refresh_token이 없습니다")
        async with self.session.post(
            f"{self.base_url}/api/v1/auth/refresh",
            json={"refresh_token": self._refresh_token},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 401:
                raise ValueError("refresh_token이 만료되었습니다")
            response.raise_for_status()
            data = await response.json()
            self._token = data["access_token"]
            self._refresh_token = data["refresh_token"]

    def _auth_headers(self) -> dict:
        if self._token:
            return {"Authorization": f"Bearer {self._token}"}
        return {}

    async def exchange_code(self, code: str) -> dict:
        """서버에 1회용 코드를 제출하고 토큰을 교환"""
        async with self.session.post(
            f"{self.base_url}/api/v1/auth/token-exchange",
            params={"code": code},
            timeout=aiohttp.ClientTimeout(total=10),
        ) as response:
            if response.status == 401:
                raise ValueError("유효하지 않거나 만료된 코드입니다")
            response.raise_for_status()
            return await response.json()

    async def get_presigned_url(self, object_name: str) -> str:
        """단일 presigned URL 요청"""
        for attempt in range(2):
            async with self.session.post(
                f"{self.base_url}/api/v1/objects/presigned-upload-url",
                json={"object_name": object_name},
                headers=self._auth_headers(),
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status == 401 and attempt == 0:
                    await self._refresh_tokens()
                    continue
                response.raise_for_status()
                data = await response.json()
                return data["url"]

    async def upload_to_s3(self, presigned_url: str, video_path: str):
        """Presigned URL로 파일 업로드"""
        with open(video_path, 'rb') as f:
            video_data = f.read()

        async with self.session.put(
            presigned_url,
            data=video_data,
            headers={'Content-Type': 'video/mp4'},
        ) as response:
            response.raise_for_status()
