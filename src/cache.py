import dbm.dumb
import os


class Cache:
    def __init__(self):
        if os.path.exists("cache") is False:
            os.mkdir("cache")
        self.cache = dbm.dumb.open("cache/post_data", "c")

    def __getitem__(self, key):
        return self.cache[key]

    def __setitem__(self, key, value):
        self.cache[key] = value

    def __contains__(self, key):
        return key in self.cache

cache = Cache()
