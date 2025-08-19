import json
from typing import List

import aiohttp.client_exceptions
from loguru import logger
from selectolax.parser import HTMLParser

from internal.jslex import js_lexer_string
from scrapers.data import HTTPSession, Media, Post, User


async def get_embed(post_id: str, proxy: str = "") -> Post | None:
    try:
        async with HTTPSession() as session:
            html = await session.http_get(
                f"https://www.instagram.com/p/{post_id}/embed/captioned/",
            )
    except Exception as e:
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
                                preview_url=media.get("display_url"),
                            )
                        )

                    # Extract timestamp if available
                    timestamp = None
                    if "taken_at_timestamp" in shortcode_media:
                        timestamp = int(shortcode_media["taken_at_timestamp"])

                    # Extract likes and comments count - try multiple possible field names
                    likes_count = 0
                    comments_count = 0
                    
                    # Try different possible field names for likes
                    if "edge_media_preview_like" in shortcode_media:
                        likes_count = shortcode_media["edge_media_preview_like"].get("count", 0)
                    elif "edge_liked_by" in shortcode_media:
                        likes_count = shortcode_media["edge_liked_by"].get("count", 0)
                    elif "like_count" in shortcode_media:
                        likes_count = shortcode_media["like_count"]
                    elif "edge_media_to_like" in shortcode_media:
                        likes_count = shortcode_media["edge_media_to_like"].get("count", 0)
                    
                    # Try different possible field names for comments
                    if "edge_media_to_parent_comment" in shortcode_media:
                        comments_count = shortcode_media["edge_media_to_parent_comment"].get("count", 0)
                    elif "edge_media_to_comment" in shortcode_media:
                        comments_count = shortcode_media["edge_media_to_comment"].get("count", 0)
                    elif "comment_count" in shortcode_media:
                        comments_count = shortcode_media["comment_count"]
                    

                    if len(medias) > 0:
                        break

    # ---- from html parsing (mostly single image post) ----
    if usernameFind := tree.css_first("span.UsernameText"):
        username = usernameFind.text()
    else:
        return None

    if pfpFind := tree.css_first("a.Avatar > img"):
        profile_pic = pfpFind.attributes["src"] or ""
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

    user = User(username=username, profile_pic=profile_pic)
    
    # Prepare post data
    post_data_dict = {
        "post_id": post_id,
        "user": user,
        "caption": caption,
        "medias": medias,
        "blocked": "WatchOnInstagram" in html,
    }
    
    # Add timestamp if we found it
    if 'timestamp' in locals() and timestamp is not None:
        post_data_dict["timestamp"] = timestamp
        
    post_data = Post(**post_data_dict)
    
    # Add likes and comments count if available
    if 'likes_count' in locals():
        post_data["likes_count"] = likes_count
    if 'comments_count' in locals():
        post_data["comments_count"] = comments_count
        
    return post_data
