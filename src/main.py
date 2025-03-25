import os
from io import BytesIO
from typing import Union

import aiohttp
import msgspec
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from PIL import Image

from src.cache import cache
from src.internal.grid_layout import generate_grid
from src.scrapers.data import Post
from src.scrapers.embed import get_embed

app = FastAPI()
templates = Jinja2Templates(directory="templates")


@app.get("/")
async def home():
    return "Henlo!"


@app.get("/tv/{post_id}")
@app.get("/reel/{post_id}")
@app.get("/reels/{post_id}")
@app.get("/stories/{username}/{post_id}")
@app.get("/p/{post_id}")
@app.get("/p/{post_id}/{media_num}")
@app.get("/{username}/p/{post_id}")
@app.get("/{username}/p/{post_id}/{media_num}")
@app.get("/{username}/reel/{post_id}")
async def embed(request: Request, post_id: str, media_num: Union[str, None] = None):
    post = cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            cache[post_id] = msgspec.json.encode(post)
    else:
        post = msgspec.json.decode(post, type=Post)

    # Return to original post if no post found
    if not post:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}", status_code=302)

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

    return templates.TemplateResponse(
        request=request,
        name="embed.html",
        context=jinja_ctx,
    )


@app.get("/videos/{post_id}/{media_id}")
@app.get("/images/{post_id}/{media_id}")
async def media_redirect(post_id: str, media_id: str):
    post = cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            cache[post_id] = msgspec.json.encode(post)
    else:
        post = msgspec.json.decode(post, type=Post)

    # Return to original post if no post found
    if not post:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}", status_code=302)

    media = post.medias[int(media_id) - 1]
    return RedirectResponse(media.url)


@app.get("/grid/{post_id}")
async def grid(post_id: str):
    if os.path.exists(f"cache/grid/{post_id}.jpeg"):
        return FileResponse(f"cache/grid/{post_id}.jpeg", media_type="image/jpeg")

    post = cache.get(post_id)
    if post is None:
        post = await get_embed(post_id)
        if post:
            cache[post_id] = msgspec.json.encode(post)
    else:
        post = msgspec.json.decode(post, type=Post)

    # Return to original post if no post found
    if not post:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}", status_code=302)

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
    return FileResponse(f"cache/grid/{post_id}.jpeg", media_type="image/jpeg")
