import os

import tomli

# config loader
if os.path.exists("config.toml"):
    with open("config.toml", "rb") as f:
        config = tomli.load(f)
else:
    config = {}
