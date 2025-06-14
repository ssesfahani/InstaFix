from templates import escape_html


def render_error(
    theme_color,
    post_url,
    error_message,
):
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <link rel="canonical" href="{post_url}"/>
        <meta property="og:url" content="{post_url}"/>
        <meta property="twitter:site" content="InstaFix" />
        <meta property="twitter:creator" content="InstaFix" />
        <meta property="theme-color" content="{theme_color}" />
        <meta property="twitter:title" content="InstaFix" />
        <meta http-equiv="refresh" content="0;url={post_url}"/>

        <meta property="og:title" content="InstaFix" />
        <meta property="og:description" content="Post might be blocked. Reason: '{escape_html(error_message or '')}'"/>
        <meta property="og:site_name" content="InstaFix" />
        <meta property="twitter:card" content="summary"/>
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
