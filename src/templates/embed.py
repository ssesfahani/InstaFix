from templates import escape_html


def render_embed(
    theme_color,
    post_url,
    username,
    full_name,
    og_site_name,
    media_width,
    media_height,
    og_description=None,
    image_url=None,
    video_url=None,
    oembed_url=None,
    mastodon_statuses_url=None,
):
    if media_height == 0:
        media_height = ""

    shown_name = f"{username} (@{username})"
    if username and full_name:
        shown_name = f"{full_name} (@{username})"

    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <link rel="canonical" href="{post_url}"/>
        <meta property="og:url" content="{post_url}"/>
        <meta property="twitter:site" content="@{username}" />
        <meta property="twitter:creator" content="@{username}" />
        <meta property="theme-color" content="{theme_color}" />
        <meta property="twitter:title" content="{escape_html(shown_name)}" />
        <meta http-equiv="refresh" content="0;url={post_url}"/>

        <meta property="og:title" content="{escape_html(shown_name)}" />
        <meta property="og:description" content="{escape_html(og_description or '')}"/>
        <meta property="og:site_name" content="{og_site_name}" />
        <meta property="twitter:card" content="summary_large_image"/>
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

    if mastodon_statuses_url:
        html += f"""
        <link href="{mastodon_statuses_url}" rel="alternate" type="application/activity+json">
    """

    html += f"""
    </head>
    <body>
        Redirecting you to the post in a moment. 
        <a href="{post_url}">Or click here.</a>
    </body>
    </html>
    """
    return html
