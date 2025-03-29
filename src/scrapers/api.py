import json
import time

import aiohttp

from scrapers.data import HTTPSession, Media, Post


async def get_query_api(post_id: str, proxy: str = "") -> Post | None:
    data = {
        "fb_api_caller_class": "RelayModern",
        "fb_api_req_friendly_name": "PolarisPostActionLoadPostQueryQuery",
        "server_timestamps": "true",
        "doc_id": "8845758582119845",
    }
    data["variables"] = json.dumps(
        {
            "shortcode": post_id,
            "fetch_tagged_user_count": None,
            "hoisted_comment_id": None,
            "hoisted_reply_id": None,
        }
    )

    async with HTTPSession() as session:
        text = await session.http_post(
            "https://www.instagram.com/graphql/query", data=data
        )
        query_json = json.loads(text)

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
        if video_url := media.get("video_url"):
            medias.append(Media(url=video_url, type="GraphVideo"))
        elif media_url := media.get("display_url"):
            medias.append(Media(url=media_url, type="GraphImage"))

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
