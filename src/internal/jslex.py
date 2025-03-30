def js_lexer_string(js: str):
    idx = 0
    len_js = len(js)
    while idx < len_js:
        c = js[idx]
        if c == "'" or c == '"':
            start_char = c
            start_idx = idx
            idx += 1  # Move past the opening quote

            while idx < len_js:
                next_char = js[idx]
                if next_char == start_char:
                    idx += 1  # Move past the closing quote
                    yield (start_idx, idx)
                    break
                elif next_char == "\\" and idx + 1 < len_js:
                    idx += 2  # Skip the escape character and the escaped character
                else:
                    idx += 1
        else:
            idx += 1
