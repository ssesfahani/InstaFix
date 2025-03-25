import asyncio
from typing import List

import msgspec

proxy_limit = asyncio.Semaphore(50)


class Media(msgspec.Struct):
    url: str
    type: str


class Post(msgspec.Struct):
    post_id: str
    username: str
    caption: str
    medias: List[Media]
