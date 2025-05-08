import json
import time
from typing import List

import aiohttp.client_exceptions
from loguru import logger
from selectolax.parser import HTMLParser

from internal.jslex import js_lexer_string
from scrapers.data import HTTPSession, Media, Post


async def get_embed(post_id: str, proxy: str = "") -> Post | None:
    try:
        async with HTTPSession() as session:
            html = await session.http_get(
                f"https://www.instagram.com/p/{post_id}/embed/captioned/",
            )
    except aiohttp.client_exceptions.ClientResponseError as e:
        logger.error(f"[{post_id}] Error when fetching post from embed: {e}")
        return None

    medias: List[Media] = []
    tree = HTMLParser(html)
    # ---- from timesliceimpl ----
    for script in tree.css("script"):
        script_text = script.text()
        if "shortcode_media" not in script_text:
            continue

        for tok in js_lexer_string(script_text):
            if "shortcode_media" in tok:
                shortcode_media = (
                    json.loads(json.loads(tok))
                    .get("gql_data", {})
                    .get("shortcode_media")
                )
                if shortcode_media:
                    post_medias = shortcode_media.get(
                        "edge_sidecar_to_children", {}
                    ).get("edges", [shortcode_media])
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

                    if len(medias) > 0:
                        break

    # ---- from html parsing (mostly single image post) ----
    if usernameFind := tree.css_first("span.UsernameText"):
        username = usernameFind.text()
    else:
        return None

    caption = ""
    if captionFind := tree.css_first("div.Caption"):
        caption = captionFind.text(deep=False, separator="\n").strip()

    # Find media
    if len(medias) == 0:
        media_html = tree.css_first(".EmbeddedMediaImage").attributes
        if media_html:
            media_url = media_html["src"]
            if media_url:
                medias.append(
                    Media(
                        url=media_url, type="GraphImage", width=0, height=0, duration=0
                    )
                )

    if len(medias) == 0:
        return None

    return Post(
        timestamp=int(time.time()),
        post_id=post_id,
        username=username,
        caption=caption,
        medias=medias,
        blocked="WatchOnInstagram" in html,
    )
