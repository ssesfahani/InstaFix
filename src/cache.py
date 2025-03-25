import dbm.dumb
import os

if os.path.exists("cache") is False:
    os.mkdir("cache")
cache = dbm.dumb.open("cache/post_data", "c")
