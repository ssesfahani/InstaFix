import os
from io import BytesIO
from typing import Union

import aiohttp
import msgspec
from aiohttp import web
from jinja2 import Environment, FileSystemLoader, select_autoescape
from PIL import Image

from cache import post_cache
from internal.grid_layout import generate_grid
from scrapers.data import Post
from scrapers.embed import get_embed
from scrapers.share import resolve_share_id
from loguru import logger

env = Environment(loader=FileSystemLoader("templates"), autoescape=select_autoescape())
embed_template = env.get_template("embed.html")


async def home(request):
    return web.Response(text="Hello, world")


async def embed(request):
    post_id = request.match_info.get("post_id", "")
    if post_id[0] == "B":
        resolve_id = await resolve_share_id(post_id)
        if resolve_id:
            post_id = resolve_id
        else:
            raise web.HTTPFound(
                f"https://www.instagram.com/p/{post_id}",
            )

    post = post_cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            post_cache.set(post_id, msgspec.json.encode(post))
    else:
        post = msgspec.json.decode(post, type=Post)

    logger.debug(f"embed({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    jinja_ctx = {
        "theme_color": "#0084ff",
        "twitter_title": post.username,
        "og_site_name": "InstaFix",
        "og_url": f"https://www.instagram.com/{post.username}/p/{post.post_id}",
        "og_description": post.caption,
        "redirect_url": f"https://www.instagram.com/{post.username}/p/{post.post_id}",
    }
    if post.medias[0].type == "GraphImage" and len(post.medias) > 2:
        jinja_ctx["image_url"] = f"/grid/{post.post_id}/"
    elif post.medias[0].type == "GraphVideo":
        jinja_ctx["video_url"] = f"/videos/{post.post_id}/1"
    else:
        jinja_ctx["image_url"] = f"/images/{post.post_id}/1"

    return web.Response(body=embed_template.render(**jinja_ctx).encode())


async def media_redirect(request):
    post_id = request.match_info.get("post_id", "")
    media_id = request.match_info.get("media_id", "")
    post = post_cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            post_cache.set(post_id, msgspec.json.encode(post))
    else:
        post = msgspec.json.decode(post, type=Post)

    logger.debug(f"media_redirect({post_id})")
    # Return to original post if no post found
    if not post:
        raise web.HTTPFound(
            f"https://www.instagram.com/p/{post_id}",
        )

    media = post.medias[int(media_id) - 1]
    raise web.HTTPFound(media.url)


async def grid(request):
    post_id = request.match_info.get("post_id", "")
    if os.path.exists(f"cache/grid/{post_id}.jpeg"):
        with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
            return web.Response(body=f.read())

    post = post_cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            post_cache.set(post_id, msgspec.json.encode(post))
    else:
        post = msgspec.json.decode(post, type=Post)

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
        return web.Response(body=f.read())


if __name__ == "__main__":
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
        ]
    )
    web.run_app(app)
