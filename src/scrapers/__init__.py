import msgspec

from cache import post_cache
from scrapers.api import get_query_api
from scrapers.data import Post
from scrapers.embed import get_embed


async def get_post(post_id: str, proxy: str = "") -> Post | None:
    post = post_cache.get(post_id)
    if post:
        return msgspec.json.decode(post, type=Post)

    post = await get_embed(post_id, proxy)
    if not post:
        post = await get_query_api(post_id, proxy)
    if post:
        post_cache.set(post_id, msgspec.json.encode(post))
    return post
