"""Simple async scheduler."""

import asyncio
from collections.abc import Awaitable, Callable


class Scheduler:
    def __init__(self) -> None:
        self._tasks: list[asyncio.Task] = []

    def schedule(
        self,
        coro_factory: Callable[[], Awaitable[None]],
        interval_seconds: int,
    ) -> None:
        async def _loop() -> None:
            while True:
                try:
                    await coro_factory()
                except Exception:
                    pass
                await asyncio.sleep(interval_seconds)

        self._tasks.append(asyncio.create_task(_loop()))

    async def shutdown(self) -> None:
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
