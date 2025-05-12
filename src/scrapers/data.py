import asyncio

import aiohttp
from typing_extensions import List, NotRequired, TypedDict

from config import config

proxy_limit = asyncio.Semaphore(50)


class User(TypedDict):
    username: str
    full_name: NotRequired[str]
    profile_pic: str


class Media(TypedDict):
    url: str
    type: str
    width: int
    height: int
    duration: int
    preview_url: NotRequired[str]  # needed only for graphvideo


class Post(TypedDict):
    timestamp: int
    post_id: str
    user: User
    caption: str
    medias: List[Media]
    blocked: bool


# https://github.com/aio-libs/aiohttp/issues/4932#issuecomment-1611759696
class HTTPSession:
    def __init__(self, headers: dict[str, str] = {}):
        self._session = aiohttp.ClientSession(
            headers=headers, proxy=config.get("HTTP_PROXY", "")
        )

    async def __aenter__(self) -> "HTTPSession":
        return self

    async def __aexit__(
        self,
        exc_type: Exception,
        exc_val,
        traceback,
    ) -> None:
        await self.close()

    async def close(self) -> None:
        await self._session.close()

    async def http_get(self, url: str) -> str:
        async with proxy_limit:
            async with self._session.request("GET", url, verify_ssl=False) as response:
                response.raise_for_status()
                return await response.text()

    async def http_post(self, url: str, data: dict) -> str:
        async with proxy_limit:
            async with self._session.request(
                "POST", url, data=data, verify_ssl=False
            ) as response:
                response.raise_for_status()
                return await response.text()

    async def http_redirect(self, url: str) -> str:
        async with proxy_limit:
            async with self._session.request(
                "HEAD", url, allow_redirects=False, verify_ssl=False
            ) as response:
                response.raise_for_status()
                return response.headers.get("location", "")
