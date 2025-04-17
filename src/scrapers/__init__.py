from loguru import logger

from cache import post_cache
from internal.singleflight import Singleflight
from scrapers.api import get_query_api
from scrapers.data import Post, deserialize_post, serialize_post
from scrapers.embed import get_embed

scraper_sf = Singleflight[str, Post | None]()


async def get_post(post_id: str, proxy: str = "") -> Post | None:
    post = await post_cache.get(post_id)
    if post:
        return deserialize_post(post)

    return await scraper_sf.do(post_id, _get_post, post_id, proxy)


async def _get_post(post_id: str, proxy: str = "") -> Post | None:
    # logger.debug(f"get_post({post_id})")

    post = await get_embed(post_id, proxy)
    if not post or post.blocked:
        post = await get_query_api(post_id, proxy)
    if post:
        await post_cache.set(post_id, serialize_post(post))
    return post
