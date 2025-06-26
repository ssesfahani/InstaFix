import os
import sqlite3
import time


class SQLiteCache:
    def __init__(self, db_path="cache.db", ttl=300):
        self.db_path = db_path
        self.ttl = ttl
        self._counter = 0
        self.init_cache()

    def init_cache(self):
        self.conn = sqlite3.connect(self.db_path)
        self.cursor = self.conn.cursor()
        self.create_table()
        self.evict()

    def create_table(self):
        self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                timestamp INTEGER
            )
            """
        )
        self.conn.commit()

    def set(self, key, value):
        timestamp = int(time.time())
        self.cursor.execute(
            "REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
            (key, value, timestamp),
        )
        self.conn.commit()

        # Evict every 1000 requests
        self._counter += 1
        if self._counter % 1000 == 0:
            self.evict()
            remove_grid_cache(max_cache=10_000)

            self._counter = 0

    def get(self, key):
        self.cursor.execute("SELECT value, timestamp FROM cache WHERE key = ?", (key,))
        row = self.cursor.fetchone()
        if row:
            value, timestamp = row
            if int(time.time()) - timestamp < self.ttl:
                return value
            else:
                self.delete(key)  # Remove expired entry
        return None

    def delete(self, key):
        self.cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
        self.conn.commit()

    def clear(self):
        self.cursor.execute("DELETE FROM cache")
        self.conn.commit()

    def close(self):
        self.conn.close()

    def evict(self):
        self.cursor.execute(
            "DELETE FROM cache WHERE timestamp < ?", (int(time.time()) - self.ttl,)
        )
        self.conn.commit()


def remove_grid_cache(max_cache: int = 5_000):
    current_cached = 0
    for file in os.listdir("cache/grid"):
        current_cached += 1
        if current_cached > max_cache:
            os.remove(f"cache/grid/{file}")


if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
post_cache = SQLiteCache(db_path="cache/post_data.db", ttl=24 * 60 * 60)
shareid_cache = SQLiteCache(db_path="cache/shareid_data.db", ttl=365 * 24 * 60 * 60)
