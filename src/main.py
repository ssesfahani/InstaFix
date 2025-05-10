import os
import re

import aiohttp
import aiohttp.web_request
from aiohttp import web
from loguru import logger

from config import config
from internal.grid_layout import grid_from_urls
from internal.singleflight import Singleflight
from scrapers import get_post
from scrapers.share import resolve_share_id
from templates.embed import render_embed


def instagram_id_to_url(instagram_id):
    # Split if there's an underscore
    if "_" in str(instagram_id):
        parts = str(instagram_id).split("_")
        instagram_id = int(parts[0])  # only use the media ID part
        # userid = parts[1]  # not used in the URL
    else:
        instagram_id = int(instagram_id)

    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
    url_suffix = ""

    while instagram_id > 0:
        remainder = instagram_id % 64
        instagram_id = instagram_id // 64
        url_suffix = alphabet[remainder] + url_suffix

    return url_suffix


async def home(request: aiohttp.web_request.Request):
    return web.Response(text="Hello, world")


async def embed(request: aiohttp.web_request.Request):
    ig_url = str(
        request.url.with_host("www.instagram.com").with_port(None).with_scheme("https")
    )
    if not re.search(
        r"(discordbot|telegrambot|facebook|whatsapp|firefox\/92|vkshare|revoltchat|preview|iframely)",
        request.headers.get("User-Agent", "").lower(),
    ):
        return web.Response(status=307, headers={"Location": ig_url})

    post_id = request.match_info.get("post_id", "")
    if post_id.isdigit():  # stories
        post_id = instagram_id_to_url(post_id)

    try:
        media_num = int(request.match_info.get("media_num", 0))
    except ValueError:
        logger.error(f"Invalid media_num: {request.path}")
        return web.Response(status=404)

    if post_id[0] == "B" or post_id[0] == "_":
        resolve_id = await resolve_share_id(post_id)
        if resolve_id:
            post_id = resolve_id
        else:
            logger.error(f"[{post_id}] Failed to resolve share id")
            raise web.HTTPFound(ig_url)

    post = await get_post(post_id)
    # logger.debug(f"embed({post_id})")
    # Return to original post if no post found
    if not post:
        logger.warning(f"[{post_id}] Failed to get post, might be not found")
        raise web.HTTPFound(ig_url)

    jinja_ctx = {
        "theme_color": "#0084ff",
        "username": post["user"]["username"],
        "full_name": post["user"].get("full_name", ""),
        "og_site_name": "InstaFix",
        "og_url": ig_url,
        "og_description": post["caption"],
        "redirect_url": ig_url,
        "media_width": post["medias"][max(1, media_num) - 1]["width"],
        "media_height": post["medias"][max(1, media_num) - 1]["height"],
    }
    if (
        media_num == 0
        and post["medias"][0]["type"] == "GraphImage"
        and len(post["medias"]) > 1
    ):
        jinja_ctx["image_url"] = f"/grid/{post['post_id']}/"
        # TODO: add media_width and media_height
        jinja_ctx["media_width"] = 0
        jinja_ctx["media_height"] = 0
    elif post["medias"][max(1, media_num) - 1]["type"] == "GraphImage":
        jinja_ctx["image_url"] = f"/images/{post['post_id']}/{max(1, media_num)}"
    else:
        jinja_ctx["video_url"] = f"/videos/{post['post_id']}/{max(1, media_num)}"

    # direct = redirect to media url
    if request.query.get("direct"):
        return web.Response(
            status=307,
            headers={
                "Location": jinja_ctx.get("image_url", jinja_ctx.get("video_url", ""))
            },
        )

    # gallery = no caption
    if request.query.get("gallery"):
        jinja_ctx.pop("og_description", None)

    return web.Response(
        body=render_embed(**jinja_ctx).encode(), content_type="text/html"
    )


async def media_redirect(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    media_id = request.match_info.get("media_id", "")
    post = await get_post(post_id)

    # logger.debug(f"media_redirect({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    media = post["medias"][int(media_id) - 1]
    return web.Response(status=307, headers={"Location": media["url"]})


grid_sf = Singleflight[str, str | None]()


async def grid(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    if os.path.exists(f"cache/grid/{post_id}.jpeg"):
        with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
            return web.Response(body=f.read(), content_type="image/jpeg")

    post = await get_post(post_id)
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    images = [media["url"] for media in post["medias"] if media["type"] == "GraphImage"]

    try:
        await grid_sf.do(post_id, grid_from_urls, images, f"cache/grid/{post_id}.jpeg")
    except Exception as e:
        logger.error(f"[{post_id}] Failed to generate grid image: {e}")
        raise web.HTTPFound(f"/images/{post_id}/1")

    with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
        return web.Response(body=f.read(), content_type="image/jpeg")


if __name__ == "__main__":
    import asyncio

    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())

    app = web.Application()
    app.add_routes(
        [
            web.get("/", home),
            web.get("/p/{post_id}", embed),
            web.get("/p/{post_id}/{media_num}", embed),
            web.get("/{username}/p/{post_id}", embed),
            web.get("/{username}/p/{post_id}/{media_num}", embed),
            web.get("/{username}/reel/{post_id}", embed),
            web.get("/tv/{post_id}", embed),
            web.get("/reel/{post_id}", embed),
            web.get("/reels/{post_id}", embed),
            web.get("/stories/{username}/{post_id}", embed),
            web.get("/images/{post_id}/{media_id}", media_redirect),
            web.get("/videos/{post_id}/{media_id}", media_redirect),
            web.get("/grid/{post_id}", grid),
            web.get("/p/{post_id}/", embed),
            web.get("/p/{post_id}/{media_num}/", embed),
            web.get("/{username}/p/{post_id}/", embed),
            web.get("/{username}/p/{post_id}/{media_num}/", embed),
            web.get("/{username}/reel/{post_id}/", embed),
            web.get("/tv/{post_id}/", embed),
            web.get("/reel/{post_id}/", embed),
            web.get("/reels/{post_id}/", embed),
            web.get("/share/{post_id}/", embed),
            web.get("/share/{post_id}/{media_num}/", embed),
            web.get("/share/p/{post_id}/", embed),
            web.get("/share/p/{post_id}/{media_num}/", embed),
            web.get("/share/reel/{post_id}/", embed),
            web.get("/share/reel/{post_id}/{media_num}/", embed),
            web.get("/stories/{username}/{post_id}/", embed),
            web.get("/images/{post_id}/{media_id}/", media_redirect),
            web.get("/videos/{post_id}/{media_id}/", media_redirect),
            web.get("/grid/{post_id}/", grid),
        ]
    )
    web.run_app(
        app, host=config.get("HOST", "127.0.0.1"), port=config.get("PORT", 3000)
    )
