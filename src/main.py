import json
import os
import re
import urllib.parse

import aiohttp
import aiohttp.web_request
from aiohttp import web
from loguru import logger

from cache import grid_cache_cb
from config import config
from internal.grid_layout import grid_from_urls
from internal.singleflight import Singleflight
from scrapers import get_post
from scrapers.data import RestrictedError, PostJSON, MediaJSON
from scrapers.share import resolve_share_id
from templates.embed import render_embed
from templates.error import render_error


def RedirectResponse(url):
    return web.Response(status=307, headers={"Location": url})


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

    return str(url_suffix)


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
        return RedirectResponse(ig_url)

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
            return RedirectResponse(ig_url)

    try:
        post = await get_post(post_id)
    except RestrictedError as e:
        logger.error(f"[{post_id}] Failed to get post: {e}")
        error_resp = render_error(
            theme_color="#0084ff",
            post_url=ig_url,
            error_message=e.message,
        )
        return web.Response(
            body=error_resp.encode(), content_type="text/html", status=403
        )

    # logger.debug(f"embed({post_id})")
    # Return to original post if no post found
    if not post:
        logger.warning(f"[{post_id}] Failed to get post, might be not found")
        return RedirectResponse(ig_url)

    jinja_ctx = {
        "theme_color": "#0084ff",
        "username": post["user"]["username"],
        "full_name": post["user"].get("full_name", ""),
        "og_site_name": "InstaFix",
        "post_url": ig_url,
        "og_description": post["caption"],
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
        return RedirectResponse(
            jinja_ctx.get("image_url", jinja_ctx.get("video_url", ""))
        )

    # oembed only for discord
    if "discord" in request.headers.get("User-Agent", "").lower():
        host = request.headers.get("Host", "")
        oembed_endpoint = f"https://{host}/oembed/?"
        oembed_params = {"author_name": post["caption"], "author_url": ig_url}
        # if image, dont add caption to oembed
        if jinja_ctx.get("image_url"):
            oembed_params["author_name"] = ""

        jinja_ctx["oembed_url"] = oembed_endpoint + urllib.parse.urlencode(
            oembed_params
        )
        # must not have trailing slash
        jinja_ctx["mastodon_statuses_url"] = (
            f"https://{host}/users/{post['user']['username']}/statuses/{int.from_bytes(post['post_id'].encode(), 'big')}"
        )
    pass

    # use og embed if media is more than 4
    if "grid" in jinja_ctx.get("image_url", "") and len(post["medias"]) > 4:
        jinja_ctx["mastodon_statuses_url"] = None

    # gallery = no caption
    if request.query.get("gallery"):
        jinja_ctx["og_description"] = ""
        jinja_ctx["oembed_url"] = ""
        jinja_ctx["mastodon_statuses_url"] = None

    return web.Response(
        body=render_embed(**jinja_ctx).encode(), content_type="text/html"
    )


async def media_redirect(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    media_id = request.match_info.get("media_id", "")
    is_preview = request.query.get("preview", False)

    try:
        post = await get_post(post_id)
        if not post:
            raise RestrictedError(message="Unknown error (1)")
    except RestrictedError as e:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}")

    if len(post["medias"]) < int(media_id) and media_id != "0":
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}")

    media = post["medias"][int(media_id) - 1]
    if is_preview and media.get("preview_url"):
        return RedirectResponse(media.get("preview_url", ""))
    return RedirectResponse(media["url"])


grid_sf = Singleflight[str, str | None]()


async def grid(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    grid_cache_cb(post_id)  # for LFU caching

    if os.path.exists(f"cache/grid/{post_id}.jpeg"):
        with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
            return web.Response(body=f.read(), content_type="image/jpeg")

    try:
        post = await get_post(post_id)
        if not post:
            raise RestrictedError(message="Unknown error (1)")
    except RestrictedError as e:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}")

    images = [media["url"] for media in post["medias"] if media["type"] == "GraphImage"]
    if len(images) == 0:
        return RedirectResponse(f"/images/{post_id}/1")

    try:
        await grid_sf.do(post_id, grid_from_urls, images, f"cache/grid/{post_id}.jpeg")
    except Exception as e:
        logger.error(f"[{post_id}] Failed to generate grid image: {e}")
        return RedirectResponse(f"/images/{post_id}/1")

    with open(f"cache/grid/{post_id}.jpeg", "rb") as f:
        return web.Response(body=f.read(), content_type="image/jpeg")


async def oembed(request: aiohttp.web_request.Request):
    author_name = request.query.get("author_name", "")
    author_url = request.query.get("author_url", "")
    return web.Response(
        text=json.dumps(
            {
                "author_name": author_name,
                "author_url": author_url,
                "provider_name": "InstaFix - Fix Instagram Embed",
                "provider_url": "https://github.com/Wikidepia/InstaFix",
                "title": "Embed",
                "type": "rich",
                "version": "1.0",
            }
        )
    )


async def mastodon_statuses(request: aiohttp.web_request.Request):
    # Most code for this part are taken from FxEmbed
    # https://github.com/FxEmbed/FxEmbed
    try:
        int_post_id = int(request.match_info.get("int_post_id", ""))
    except ValueError:
        logger.error(f"Invalid actpub post_id: {request.path}")
        return web.Response(status=404)

    post_id = int.to_bytes(int_post_id, 24, "big").decode().strip("\x00")
    host = request.headers.get("Host", "")

    try:
        post = await get_post(post_id)
        if not post:
            raise RestrictedError(message="Unknown error (1)")
    except RestrictedError as e:
        return RedirectResponse(f"https://www.instagram.com/p/{post_id}")

    # activitypub caption/content must be a html
    caption = post["caption"].replace("\n", "<br>")

    # create media attachment
    media_attachments = []
    for i, media in enumerate(post["medias"]):
        if media["type"] == "GraphImage" and media["type"] == post["medias"][0]["type"]:
            media_attachments.append(
                {
                    "id": "114163769487684704",
                    "type": "image",
                    "url": f"https://{host}/images/{post['post_id']}/{i+1}",
                    "preview_url": None,
                    "remote_url": None,
                    "preview_remote_url": None,
                    "text_url": None,
                    "description": None,
                    # TODO: Add meta
                    # "meta": {
                    #     "original": {
                    #         "width": media["width"],
                    #         "height": media["height"],
                    #         "size": f"{media['width']}x{media['height']}",
                    #         "aspect": media["width"] / media["height"],
                    #     }
                    # },
                }
            )
        elif (
            media["type"] == "GraphVideo" and media["type"] == post["medias"][0]["type"]
        ):
            media_attachments.append(
                {
                    "id": "114163769487684704",
                    "type": "video",
                    "url": f"https://{host}/videos/{post['post_id']}/{i+1}",
                    "preview_url": f"https://{host}/videos/{post['post_id']}/{i+1}?preview=true",
                    "remote_url": None,
                    "preview_remote_url": None,
                    "text_url": None,
                    "description": None,
                    # TODO: Add meta
                    # "meta": {
                    #     "original": {
                    #         "width": 900,
                    #         "height": 900,
                    #         "size": f"900x900",
                    #         "aspect": 1,
                    #     }
                    # },
                }
            )

    return web.Response(
        text=json.dumps(
            {
                "id": 0,
                "url": f"https://www.instagram.com/p/{post['post_id']}",
                "uri": f"https://www.instagram.com/p/{post['post_id']}",
                # "created_at": "2025-04-11T06:34:46.886Z",
                "edited_at": None,
                "reblog": None,
                "in_reply_to_id": None,
                "in_reply_to_account_id": None,
                "language": "en",
                "content": caption,
                "spoiler_text": "",
                "visibility": "public",
                "application": {
                    "name": "InstaFix",
                    "website": None,
                },
                "media_attachments": media_attachments,
                "account": {
                    "id": 0,
                    "display_name": post["user"].get("full_name", ""),
                    "username": post["user"]["username"],
                    "acct": post["user"]["username"],
                    "url": f"https://www.instagram.com/{post['user']['username']}",
                    "uri": f"https://www.instagram.com/{post['user']['username']}",
                    # "created_at": "2025-05-11T06:34:46.886Z",
                    "locked": False,
                    "bot": False,
                    "discoverable": True,
                    "indexable": False,
                    "group": False,
                    "avatar": post["user"]["profile_pic"],
                    "avatar_static": post["user"]["profile_pic"],
                    "header": None,
                    "header_static": None,
                    "followers_count": 0,
                    "following_count": 0,
                    "statuses_count": 0,
                    "hide_collections": False,
                    "noindex": False,
                    "emojis": [],
                    "roles": [],
                    "fields": [],
                },
                "mentions": [],
                "tags": [],
                "emojis": [],
                "card": None,
                "poll": None,
            }
        )
    )


async def api_post_json(request: aiohttp.web_request.Request):
    post_id = request.match_info.get("post_id", "")
    if post_id[0] == "B" or post_id[0] == "_":
        resolve_id = await resolve_share_id(post_id)
        if resolve_id:
            post_id = resolve_id
        else:
            logger.error(f"[{post_id}] Failed to resolve share id")
            return web.Response(status=404, text="Post not found")

    try:
        post = await get_post(post_id)
    except RestrictedError as e:
        logger.error(f"[{post_id}] Failed to get post: {e}")
        return web.Response(status=403, text=f"Access denied: {e.message}")

    if not post:
        logger.warning(f"[{post_id}] Failed to get post, might be not found")
        return web.Response(status=404, text="Post not found")

    # Convert internal media format to API format
    medias_json = []
    is_video_only = True
    for media in post["medias"]:
        media_type = "video" if media["type"] == "GraphVideo" else "image"
        if media_type == "image":
            is_video_only = False
        medias_json.append(MediaJSON(type=media_type, url=media["url"]))

    # Build the response according to PostJSON structure
    response_data = PostJSON(
        post_id=post["post_id"],
        username=post["user"]["username"],
        caption=post["caption"],
        medias=medias_json,
    )

    # Add optional fields if available
    if "profile_pic" in post["user"]:
        response_data["avatar_url"] = post["user"]["profile_pic"]
    
    if len(post["medias"]) > 0 and all(m["type"] == "GraphVideo" for m in post["medias"]):
        response_data["is_video_only"] = True
    
    if "timestamp" in post:
        response_data["timestamp"] = post["timestamp"]
    
    if "likes_count" in post:
        response_data["likes_count"] = post["likes_count"]
    
    if "comments_count" in post:
        response_data["comments_count"] = post["comments_count"]

    return web.Response(
        text=json.dumps(response_data, indent=2),
        content_type="application/json"
    )


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
            web.get("/oembed/", oembed),
            web.get("/api/v1/statuses/{int_post_id}", mastodon_statuses),
            web.get("/api/v1/statuses/{int_post_id}/", mastodon_statuses),
            web.get("/api/p/{post_id}", api_post_json),
        ]
    )
    web.run_app(
        app, host=config.get("HOST", "127.0.0.1"), port=config.get("PORT", 3000)
    )
