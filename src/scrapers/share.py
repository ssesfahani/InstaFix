import urllib.parse

import aiohttp

from src.scrapers.data import proxy_limit


async def resolve_share_id(post_id: str) -> str | None:
    async with proxy_limit:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=5)) as session:
            async with session.head(
                f"https://www.instagram.com/share/reel/{post_id}/"
            ) as response:
                location = response.headers.get("location", "")
                if "/login" in location:
                    return None
                parts = urllib.parse.urlparse(location)
                return parts.path.strip("/").split("/")[-1]
