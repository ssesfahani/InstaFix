import os
import time

import aiofiles.os
import aiosqlite


class SQLiteCache:
    def __init__(self, db_path="cache.db", ttl=300):
        self.db_path = db_path
        self.ttl = ttl
        self._counter = 0

    async def init_cache(self):
        self.conn = await aiosqlite.connect(self.db_path)
        self.cursor = await self.conn.cursor()
        await self.create_table()
        await self.evict()

    async def create_table(self):
        await self.cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS cache (
                key TEXT PRIMARY KEY,
                value BLOB,
                timestamp INTEGER
            )
            """
        )
        await self.cursor.execute("PRAGMA journal_mode = WAL")
        await self.cursor.execute("CREATE INDEX IF NOT EXISTS key_index ON cache(key)")
        await self.conn.commit()

    async def set(self, key, value):
        timestamp = int(time.time())
        await self.cursor.execute(
            "REPLACE INTO cache (key, value, timestamp) VALUES (?, ?, ?)",
            (key, value, timestamp),
        )
        await self.conn.commit()

        # Evict every 1000 requests
        self._counter += 1
        if self._counter % 1000 == 0:
            await self.evict()
            await remove_grid_cache()
            self._counter = 0

    async def get(self, key):
        await self.cursor.execute(
            "SELECT value, timestamp FROM cache WHERE key = ?", (key,)
        )
        row = await self.cursor.fetchone()
        if row:
            value, timestamp = row
            if int(time.time()) - timestamp < self.ttl:
                return value
            else:
                await self.delete(key)  # Remove expired entry
        return None

    async def delete(self, key):
        await self.cursor.execute("DELETE FROM cache WHERE key = ?", (key,))
        await self.conn.commit()

    async def clear(self):
        await self.cursor.execute("DELETE FROM cache")
        await self.conn.commit()

    async def close(self):
        await self.conn.close()

    async def evict(self):
        await self.cursor.execute(
            "DELETE FROM cache WHERE timestamp < ?", (int(time.time()) - self.ttl,)
        )
        await self.conn.commit()


async def remove_grid_cache(max_cache: int = 5_000):
    current_cached = 0
    for file in os.listdir("cache/grid"):
        current_cached += 1
        if current_cached > max_cache:
            await aiofiles.os.remove(f"cache/grid/{file}")


if os.path.exists("cache") is False:
    os.makedirs("cache")
    os.makedirs("cache/grid")
post_cache = SQLiteCache(db_path="cache/post_data.db", ttl=24 * 60 * 60)
shareid_cache = SQLiteCache(db_path="cache/shareid_data.db", ttl=365 * 24 * 60 * 60)
