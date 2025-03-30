def js_lexer_string(js: str):
    idx = 0
    len_js = len(js)
    while idx < len_js:
        idx = js.find('"', idx)
        if idx == -1:
            break
        current_char = js[idx]
        start_char = current_char
        start_idx = idx

        idx += 1  # Move past the opening quote
        while idx < len_js:
            idx = js.find('"', idx)
            if idx == -1:
                break
            elif js[idx-1] == "\\":
                idx += 1
            elif js[idx] == start_char:
                idx += 1  # Move past the closing quote
                yield (start_idx, idx)
                break
