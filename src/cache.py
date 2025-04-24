import os
import time
from typing import Optional

import lmdb


class KVCache:
    def __init__(self, db_path="cache.db", ttl=300):
        self.env = lmdb.open(db_path, max_dbs=2, map_size=int(1e9))
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
        # 1. Compute TTL in *nanoseconds*
        ns_ttl = self.ttl * 1_000_000_000
        now_ns = time.time_ns()

        # 2. Collect meta-keys to delete and corresponding data-DB keys
        meta_keys_to_delete = []
        data_keys_to_delete = []

        with self.env.begin(write=True, db=self.meta_db) as txn:
            curs = txn.cursor()
            if not curs.first():
                return  # nothing in meta_db

            for k, v in curs:
                # skip invalid entries
                if len(k) != 8 or len(v) == 0:
                    continue

                ts = int.from_bytes(k, byteorder="little")
                # skip non-expiring or not-yet-expired
                if ts == 0 or (now_ns - ts) < ns_ttl:
                    continue

                meta_keys_to_delete.append(k)
                data_keys_to_delete.append(v)

        # 3. Delete expired metadata
        if meta_keys_to_delete:
            with self.env.begin(write=True, db=self.meta_db) as txn:
                for k in meta_keys_to_delete:
                    txn.delete(k)

        # 4. Delete corresponding data entries
        if data_keys_to_delete:
            with self.env.begin(write=True, db=self.data_db) as txn:
                for data_key in data_keys_to_delete:
                    txn.delete(data_key)


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
