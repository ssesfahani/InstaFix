import json
import time

import aiohttp
import aiohttp.client_exceptions
from loguru import logger

from scrapers.data import HTTPSession, Media, Post


async def get_query_api(post_id: str, proxy: str = "") -> Post | None:
    headers = {
        "x-csrftoken": "-",
    }

    data = {
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "PolarisPostActionLoadPostQueryQuery",
        "server_timestamps": "true",
        "doc_id": "9510064595728286",
    }
    data["variables"] = json.dumps(
        {
            "shortcode": post_id,
            "fetch_tagged_user_count": None,
            "hoisted_comment_id": None,
            "hoisted_reply_id": None,
        }
    )

    MAX_RETRIES = 5
    for i in range(MAX_RETRIES):
        try:
            async with HTTPSession(headers=headers) as session:
                text = await session.http_post(
                    "https://www.instagram.com/graphql/query", data=data
                )
                query_json = json.loads(text)
                break
        except aiohttp.client_exceptions.ClientResponseError as e:
            if i == MAX_RETRIES - 1:
                logger.error(f"[{post_id}] Error when fetching post from API: {e}")
    else:
        return None

    data = query_json.get("data")
    if not data:
        return None

    shortcode_media = data.get("shortcode_media", data).get("xdt_shortcode_media")
    if not shortcode_media:
        return None
    medias = []
    post_medias = shortcode_media.get("edge_sidecar_to_children", {}).get(
        "edges", [shortcode_media]
    )
    for media in post_medias:
        media = media.get("node", media)
        media_url = media.get("video_url")
        if not media_url:
            media_url = media.get("display_url")
        medias.append(
            Media(
                url=media_url,
                type=media["__typename"],
                width=media["dimensions"]["width"],
                height=media["dimensions"]["height"],
                duration=0,
            )
        )

    username = shortcode_media.get("owner", {}).get("username")
    caption = ""
    caption_edges = shortcode_media.get("edge_media_to_caption", {}).get("edges", [])
    if len(caption_edges) > 0:
        caption = caption_edges[0].get("node", {}).get("text", "")
    return Post(
        timestamp=int(time.time()),
        post_id=post_id,
        username=username,
        caption=caption,
        medias=medias,
        blocked=False,
    )
