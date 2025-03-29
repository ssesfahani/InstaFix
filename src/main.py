import os
from io import BytesIO

import aiohttp
import aiohttp.web_request
import tomli
from aiohttp import web
from loguru import logger
from PIL import Image

from internal.grid_layout import generate_grid
from scrapers import get_post
from scrapers.share import resolve_share_id
from templates.embed import render_embed

# config loader
if os.path.exists("config.toml"):
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
else:
    config = {}


async def home(request: aiohttp.web_request.Request):
    return web.Response(text="Hello, world")


async def embed(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    media_num = int(request.match_info.get("media_num", 0))

    if post_id[0] == "B":
        resolve_id = await resolve_share_id(post_id, config.get("HTTP_PROXY", ""))
        if resolve_id:
            post_id = resolve_id
        else:
            raise web.HTTPFound(
                f"https://www.instagram.com/p/{post_id}",
            )

    post = await get_post(post_id, config.get("HTTP_PROXY", ""))
    # logger.debug(f"embed({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    ig_url = str(
        request.url.with_host("www.instagram.com").with_port(None).with_scheme("https")
    )
    jinja_ctx = {
        "theme_color": "#0084ff",
        "twitter_title": post.username,
        "og_site_name": "InstaFix",
        "og_url": ig_url,
        "og_description": post.caption,
        "redirect_url": ig_url,
    }
    if media_num == 0 and post.medias[0].type == "GraphImage" and len(post.medias) > 1:
        jinja_ctx["image_url"] = f"/grid/{post.post_id}/"
    elif post.medias[max(1, media_num) - 1].type == "GraphImage":
        jinja_ctx["image_url"] = f"/images/{post.post_id}/{max(1, media_num)}"
    else:
        jinja_ctx["video_url"] = f"/videos/{post.post_id}/{max(1, media_num)}"

    return web.Response(
        body=render_embed(**jinja_ctx).encode(), content_type="text/html"
    )


async def media_redirect(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    media_id = request.match_info.get("media_id", "")
    post = await get_post(post_id, config.get("HTTP_PROXY", ""))

    logger.debug(f"media_redirect({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    media = post.medias[int(media_id) - 1]
    return web.Response(status=307, headers={"Location": media.url})


async def grid(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    if os.path.exists(f"cache/grid/{post_id}.jpeg"):
        with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
            return web.Response(body=f.read(), content_type="image/jpeg")

    post = await get_post(post_id, config.get("HTTP_PROXY", ""))
    logger.debug(f"grid({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    images = []
    async with aiohttp.ClientSession() as session:
        for media in post.medias:
            if media.type != "GraphImage":
                continue
            async with session.get(media.url) as response:
                images.append(Image.open(BytesIO(await response.read())))

    grid_img = generate_grid(images)
    if grid_img is None:
        raise

    grid_img.save(f"cache/grid/{post_id}.jpeg", format="JPEG")
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
            web.get("/stories/{username}/{post_id}/", embed),
            web.get("/images/{post_id}/{media_id}/", media_redirect),
            web.get("/videos/{post_id}/{media_id}/", media_redirect),
            web.get("/grid/{post_id}/", grid),
        ]
    )
    web.run_app(
        app, host=config.get("HOST", "127.0.0.1"), port=config.get("PORT", 3000)
    )
