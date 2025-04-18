import asyncio
import dataclasses
import io
from typing import List

import aiohttp

from config import config

proxy_limit = asyncio.Semaphore(50)


@dataclasses.dataclass
class Media:
    url: str
    type: str


@dataclasses.dataclass
class Post:
    timestamp: int
    post_id: str
    username: str
    caption: str
    medias: List[Media]
    blocked: bool


def serialize_post(post: Post) -> bytes:
    ret = bytearray()
    ret.extend(post.timestamp.to_bytes(8, "little"))

    bs = post.post_id.encode()
    ret.extend(len(bs).to_bytes(4, "little"))
    ret.extend(bs)

    bs = post.username.encode()
    ret.extend(len(bs).to_bytes(4, "little"))
    ret.extend(bs)

    bs = post.caption.encode()
    ret.extend(len(bs).to_bytes(4, "little"))
    ret.extend(bs)

    ret.extend(len(post.medias).to_bytes(4, "little"))
    for media in post.medias:
        bs = media.url.encode()
        ret.extend(len(bs).to_bytes(4, "little"))
        ret.extend(bs)
        bs = media.type.encode()
        ret.extend(len(bs).to_bytes(4, "little"))
        ret.extend(bs)
    ret.extend(post.blocked.to_bytes(1, "little"))
    return ret


def deserialize_post(data: bytes) -> Post:
    buf = io.BytesIO(data)
    timestamp = int.from_bytes(buf.read(8), "little")

    blen = int.from_bytes(buf.read(4), "little")
    post_id = buf.read(blen).decode()

    blen = int.from_bytes(buf.read(4), "little")
    username = buf.read(blen).decode()

    blen = int.from_bytes(buf.read(4), "little")
    caption = buf.read(blen).decode()

    blen = int.from_bytes(buf.read(4), "little")
    medias = []
    for _ in range(blen):
        blen = int.from_bytes(buf.read(4), "little")
        media_url = buf.read(blen).decode()

        blen = int.from_bytes(buf.read(4), "little")
        media_type = buf.read(blen).decode()
        medias.append(Media(media_url, media_type))
    blocked = bool(int.from_bytes(buf.read(1), "little"))
    return Post(timestamp, post_id, username, caption, medias, blocked)


# https://github.com/aio-libs/aiohttp/issues/4932#issuecomment-1611759696
class HTTPSession:
    def __init__(self) -> None:
        self._session = aiohttp.ClientSession(proxy=config.get("HTTP_PROXY", ""))

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
            async with self._session.request("POST", url, data=data, verify_ssl=False) as response:
                response.raise_for_status()
                return await response.text()

    async def http_redirect(self, url: str) -> str:
        async with proxy_limit:
            async with self._session.request(
                "HEAD", url, allow_redirects=False, verify_ssl=False
            ) as response:
                response.raise_for_status()
                return response.headers.get("location", "")
