import os
import time

from cachetools import LFUCache, cached
from lsm import LSM


class Cache:
    def __init__(self, db_path="cache.db", ttl=300):
        self.db_path = db_path
        self.ttl_path = db_path + ".ttl"
        self.ttl_ns = ttl * 1000 * 1000 * 1000
        self._counter = 0
        self.init_cache()

    def init_cache(self):
        self.db = LSM(self.db_path)
        self.ttl_db = LSM(self.ttl_path)
        self.evict()

    def set(self, key, value):
        self.db[key] = value
        self.ttl_db[str(time.time_ns() + self.ttl_ns)] = key

        # Evict every 1000 requests
        self._counter += 1
        if self._counter % 1000 == 0:
            self._counter = 0
            self.evict()

    def get(self, key):
        try:
            return self.db[key]
        except KeyError:
            return None

    def evict(self):
        expired = list(self.ttl_db["0" : str(time.time_ns())])
        with self.ttl_db.transaction() as txn:
            for key, value in expired:
                self.ttl_db.delete(key)
            txn.commit()

        with self.db.transaction() as txn:
            for key, value in expired:
                self.db.delete(value)
            txn.commit()


class LFUGridCache(LFUCache):
    def __init__(self, maxsize, getsizeof=None):
        LFUCache.__init__(self, maxsize, getsizeof)

    def popitem(self):
        key, val = LFUCache.popitem(self)
        # Evict grid by removing the file
        try:
            (fname,) = key
            os.remove(f"cache/grid/{fname}.jpeg")
        except FileNotFoundError:
            pass
        return key, val


@cached(LFUGridCache(maxsize=10_000, getsizeof=None))
def grid_cache_cb(post_id: str):
    return f"cache/grid/{post_id}.jpeg"


if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
post_cache = Cache(db_path="cache/post_data.db", ttl=24 * 60 * 60)
shareid_cache = Cache(db_path="cache/shareid_data.db", ttl=365 * 24 * 60 * 60)

# Populate cache
for file in os.listdir("cache/grid"):
    grid_cache_cb(file.split(".")[0])
