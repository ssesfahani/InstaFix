import urllib.parse

import aiohttp

from cache import shareid_cache
from scrapers.data import proxy_limit


async def resolve_share_id(post_id: str, proxy: str = "") -> str | None:
    if shareid_cache.get(post_id):
        return shareid_cache.get(post_id)
    async with proxy_limit:
        async with aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=5), proxy=proxy
        ) as session:
            async with session.head(
                f"https://www.instagram.com/share/reel/{post_id}/"
            ) as response:
                location = response.headers.get("location", "")
                if "/login" in location:
                    return None
                parts = urllib.parse.urlparse(location)
                return parts.path.strip("/").split("/")[-1]
