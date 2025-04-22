import os
import time
from typing import Optional

import lmdb


class KVCache:
    def __init__(self, db_path="cache.db", ttl=300):
        self.env = lmdb.open(db_path, max_dbs=2)
        self.data_db = self.env.open_db(b"data")
        self.meta_db = self.env.open_db(b"meta")
        self.ttl = ttl
        self._counter = 0

        self.evict()

    def set(self, key: str, value: bytes):
        timestamp = time.time_ns()
        with self.env.begin(write=True, db=self.data_db) as txn:
            txn.put(key.encode(), value)
        with self.env.begin(write=True, db=self.meta_db) as txn:
            txn.put(timestamp.to_bytes(8, "little"), key.encode())

        self._counter += 1
        if self._counter % 1000 == 0:
            remove_grid_cache()
            self.evict()
            self._counter = 0

    def get(self, key: str | bytes) -> Optional[bytes]:
        if isinstance(key, str):
            key = key.encode()
        with self.env.begin(write=False, buffers=True, db=self.data_db) as txn:
            buf = txn.get(key)
            if buf is None:
                return None
            buf_copy = bytes(buf)
            return buf_copy

    def evict(self):
        ns_ttl = self.ttl * 1000 * 1000
        ns_time = time.time_ns()
        to_remove = set()
        with self.env.begin(write=True, db=self.meta_db) as txn:
            with txn.cursor() as curs:
                while curs.next():
                    if len(curs.key()) != 8 and len(curs.value()) == 0:
                        continue
                    timestamp = int.from_bytes(curs.key(), "little")
                    if (
                        timestamp == 0
                        or ns_time - timestamp < ns_ttl
                    ):
                        continue
                    to_remove.add(curs.value())
                    txn.delete(curs.key())

        with self.env.begin(write=True, db=self.data_db) as txn:
            for key in to_remove:
                txn.delete(key)


def remove_grid_cache(max_cache: int = 5_000):
    current_cached = 0
    for file in os.listdir("cache/grid"):
        current_cached += 1
        if current_cached > max_cache:
            os.remove(f"cache/grid/{file}")


if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
post_cache = KVCache(db_path="cache/post_data", ttl=24 * 60 * 60)
shareid_cache = KVCache(db_path="cache/shareid_data", ttl=365 * 24 * 60 * 60)
