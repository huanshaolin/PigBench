import asyncio
from contextlib import asynccontextmanager

MAX_CONCURRENT_IMAGE   = 3
MAX_CONCURRENT_VIDEO   = 2
QUEUE_TIMEOUT_SECONDS  = 300


class RequestQueue:
    def __init__(self, max_concurrent: int, name: str):
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._max  = max_concurrent
        self._name = name
        self.active:  int = 0
        self.waiting: int = 0

    @asynccontextmanager
    async def process(self):
        self.waiting += 1
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=QUEUE_TIMEOUT_SECONDS)
        except asyncio.TimeoutError:
            self.waiting -= 1
            raise asyncio.TimeoutError(
                f"[{self._name}] Request timed out after {QUEUE_TIMEOUT_SECONDS}s "
                f"(active={self.active}, waiting={self.waiting})."
            )
        self.waiting -= 1
        self.active += 1
        try:
            yield
        finally:
            self.active -= 1
            self._semaphore.release()

    def status(self) -> dict:
        return {"max_concurrent": self._max, "active": self.active, "waiting": self.waiting}


image_queue = RequestQueue(MAX_CONCURRENT_IMAGE, name="image")
video_queue = RequestQueue(MAX_CONCURRENT_VIDEO, name="video")
