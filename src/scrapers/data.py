import asyncio
from urllib.parse import urlparse

import aiohttp
from typing_extensions import List, NotRequired, Optional, TypedDict

from config import config

global_dns_cache = {}
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


class RestrictedError(Exception):
    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


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

    def cache_dns(self, url: str):
        domain_name = urlparse(url).netloc
        headers = {"Host": domain_name}

        if domain_name in global_dns_cache:
            ip_addr = global_dns_cache[domain_name]
            url = url.replace(domain_name, ip_addr)
        return url, headers

    # https://stackoverflow.com/a/72187901
    def extract_addr(self, response: aiohttp.ClientResponse) -> Optional[str]:
        if response.connection is None:
            return None
        if response.connection.transport is None:
            return None
        return response.connection.transport.get_extra_info("peername")[0]

    async def http_get(
        self, url: str, params: dict = {}, ignore_status: bool = False
    ) -> str:
        url, headers = self.cache_dns(url)
        async with proxy_limit:
            async with self._session.request(
                "GET", url, params=params, verify_ssl=False, headers=headers
            ) as response:
                if not ignore_status:
                    response.raise_for_status()
                if ip_addr := self.extract_addr(response):
                    global_dns_cache[headers["Host"]] = ip_addr
                return await response.text()

    async def http_post(self, url: str, data: dict, ignore_status: bool = False) -> str:
        url, headers = self.cache_dns(url)
        async with proxy_limit:
            async with self._session.request(
                "POST", url, data=data, verify_ssl=False, headers=headers
            ) as response:
                if not ignore_status:
                    response.raise_for_status()
                if ip_addr := self.extract_addr(response):
                    global_dns_cache[headers["Host"]] = ip_addr
                return await response.text()

    async def http_redirect(self, url: str) -> str:
        url, headers = self.cache_dns(url)
        async with proxy_limit:
            async with self._session.request(
                "HEAD", url, allow_redirects=False, verify_ssl=False, headers=headers
            ) as response:
                response.raise_for_status()
                if ip_addr := self.extract_addr(response):
                    global_dns_cache[headers["Host"]] = ip_addr
                return response.headers.get("location", "")
