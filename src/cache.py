import dbm.dumb
import os

if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
cache = dbm.dumb.open("cache/post_data", "c")
