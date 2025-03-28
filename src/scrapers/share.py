import urllib.parse

import aiohttp

from cache import shareid_cache
from scrapers.data import proxy_limit


async def resolve_share_id(post_id: str, proxy: str = "") -> str | None:
    if cached := shareid_cache.get(post_id):
        return cached
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

                new_post_id = parts.path.strip("/").split("/")[-1]
                shareid_cache.set(post_id, new_post_id)
                return new_post_id
