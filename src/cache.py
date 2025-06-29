import os
import time

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


def remove_grid_cache(max_cache: int = 5_000):
    current_cached = 0
    for file in os.listdir("cache/grid"):
        current_cached += 1
        if current_cached > max_cache:
            os.remove(f"cache/grid/{file}")


if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
post_cache = Cache(db_path="cache/post_data.db", ttl=24 * 60 * 60)
shareid_cache = Cache(db_path="cache/shareid_data.db", ttl=365 * 24 * 60 * 60)
