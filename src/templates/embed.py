from templates import escape_html


def render_embed(
    theme_color,
    og_url,
    username,
    full_name,
    og_site_name,
    media_width,
    media_height,
    og_description=None,
    image_url=None,
    video_url=None,
    redirect_url=None,
    oembed_url=None,
):
    if media_height == 0:
        media_height = ""
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="utf-8"/>
        <meta property="theme-color" content="{theme_color}"/>

        <link rel="canonical" href="{og_url}" />
        <meta property="og:url" content="{og_url}"/>
        <meta http-equiv="refresh" content="0; url={og_url}" />

        <meta property="og:site_name" content="{og_site_name}"/>
    """

    if username and full_name:
        html += f"""
        <meta property="og:title" content="{full_name} (@{username})"/>
        <meta property="twitter:title" content="{full_name} (@{username})"/>
    """

    if username and not full_name:
        html += f"""
        <meta property="og:title" content="@{username}"/>
        <meta property="twitter:title" content="@{username}"/>
    """

    if og_description:
        html += f"""
        <meta property="og:description" content="{escape_html(og_description)}"/>
    """

    if image_url:
        html += f"""
        <meta property="og:image" content="{image_url}"/>
        <meta property="twitter:card" content="summary_large_image"/>
        <meta property="twitter:image" content="{image_url}"/>
    """

    if video_url:
        html += f"""
        <meta property="og:video" content="{video_url}"/>
        <meta property="og:video:secure_url" content="{video_url}"/>
        <meta property="og:video:type" content="video/mp4"/>
        <meta property="og:video:width" content="{media_width}"/>
        <meta property="og:video:height" content="{media_height}"/>

        <meta property="twitter:card" content="player"/>
        <meta property="twitter:player:stream" content="{video_url}"/>
        <meta property="twitter:player:stream:content_type" content="video/mp4"/>
        <meta property="twitter:player:width" content="{media_width}"/>
        <meta property="twitter:player:height" content="{media_height}"/>
    """

    if oembed_url:
        html += f"""
        <link rel="alternate" href="{oembed_url}" type="application/json+oembed">
    """

    html += f"""
    </head>
    <body>
        Redirecting you to the post in a moment. 
        <a href="{redirect_url}">Or click here.</a>
    </body>
    </html>
    """
    return html
