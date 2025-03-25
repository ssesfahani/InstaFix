import json

import aiohttp
from selectolax.parser import HTMLParser

from src.internal.jslex import JsLexer
from src.scrapers.data import Media, Post, proxy_limit


async def get_embed(post_id: str) -> Post | None:
    async with proxy_limit:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"https://www.instagram.com/p/{post_id}/embed/captioned/"
            ) as response:
                html = await response.text()

    medias = []
    tree = HTMLParser(html)
    # ---- from timesliceimpl (mostly single image post) ----
    for script in tree.css("script"):
        script_text = script.text()
        if "shortcode_media" not in script_text:
            continue

        lexer = JsLexer()
        for name, tok in lexer.lex(script_text):
            if name == "string" and "shortcode_media" in tok:
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
                        if video_url := media.get("video_url"):
                            medias.append(Media(url=video_url, type="GraphVideo"))
                        elif media_url := media.get("display_url"):
                            medias.append(Media(url=media_url, type="GraphImage"))

    # ---- from html parsing (mostly single image post) ----
    if usernameFind := tree.css_first("span.UsernameText"):
        username = usernameFind.text()
    else:
        print("username not found")
        return None

    caption = ""
    if captionFind := tree.css_first("div.Caption"):
        caption = captionFind.text(deep=False)

    # Find media
    if len(medias) == 0:
        media_html = tree.css_first(".EmbeddedMediaImage").attributes
        if media_html:
            media_url = media_html["src"]
            if media_url:
                medias.append(Media(url=media_url, type="GraphImage"))

    if len(medias) == 0:
        print("empty medias")
        return None

    return Post(
        post_id=post_id,
        username=username,
        caption=caption,
        medias=medias,
    )
