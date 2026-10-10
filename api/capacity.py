"""One shared compute budget across legacy and background measurement routes."""
import asyncio
import os


def bounded_env(name, default, upper):
    try:
        value = int(os.environ.get(name, default))
    except ValueError:
        return default
    return max(1, min(upper, value))


class ComputeGate:
    def __init__(self, limit=1):
        self.limit = limit
        self.active = 0
        self._semaphore = asyncio.Semaphore(limit)

    def locked(self):
        return self.active >= self.limit

    async def acquire(self):
        await self._semaphore.acquire()
        self.active += 1

    def release(self):
        self.active -= 1
        self._semaphore.release()

    async def __aenter__(self):
        await self.acquire()
        return self

    async def __aexit__(self, *args):
        self.release()
