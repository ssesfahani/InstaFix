from typing import Union

import msgspec
from fastapi import FastAPI, Request
from fastapi.templating import Jinja2Templates

from src.cache import cache
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
    if post_id in cache:
        post = msgspec.json.decode(cache[post_id], type=Post)
    else:
        post = await get_embed(post_id)
        cache[post_id] = msgspec.json.encode(post)

    return templates.TemplateResponse(
        request=request,
        name="embed.html",
        context={
            "theme_color": "#0084ff",
            "twitter_title": post.username,
            "twitter_image": post.medias[0].url,
            "og_site_name": "InstaFix",
            "og_url": f"https://www.instagram.com/{post.username}/p/{post.post_id}",
            "og_description": post.caption,
            "og_image": post.medias[0].url,
            "redirect_url": f"https://www.instagram.com/{post.username}/p/{post.post_id}",
        },
    )

@app.get("/images/{post_id}/{image_id}")
async def image(post_id: str, image_id: str):
    return "Image"

@app.get("/videos/{post_id}/{video_id}")
async def video(post_id: str, video_id: str):
    return "Video"
