import re

# Pre-compile the optimized regex (genned from Gemini 2.5)
# Regex breakdown:
# "          - Match the opening double quote
# [^"\\]*    - Match 0 or more characters that are NOT a quote or backslash (greedily)
# (?:        - Start a non-capturing group (for escapes and subsequent normal chars)
#   \\.      - Match an escaped character (backslash followed by ANY character)
#   [^"\\]*  - Match 0 or more non-quote, non-backslash characters following the escape
# )*         - Repeat this group 0 or more times
# "          - Match the closing double quote
JS_STRING_REGEX = re.compile(r'"[^"\\]*(?:\\.[^"\\]*)*"')


def js_lexer_string(js: str):
    return JS_STRING_REGEX.findall(js)
