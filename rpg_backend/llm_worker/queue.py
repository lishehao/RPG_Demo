from __future__ import annotations

import asyncio
from collections import deque
from dataclasses import dataclass
from typing import Any, Literal


TaskKind = Literal["json_object"]


@dataclass
class QueuedTask:
    kind: TaskKind
    payload: Any
    request_id: str | None
    created_monotonic: float
    deadline_monotonic: float
    future: asyncio.Future[Any]


class WeightedTaskQueue:
    def __init__(
        self,
        *,
        max_size: int,
        weights: dict[TaskKind, int],
    ) -> None:
        self._max_size = max(1, int(max_size))
        self._queues: dict[TaskKind, deque[QueuedTask]] = {"json_object": deque()}
        self._size = 0
        self._cond = asyncio.Condition()
        self._schedule = self._build_schedule(weights)
        self._cursor = 0

    @staticmethod
    def _build_schedule(weights: dict[TaskKind, int]) -> list[TaskKind]:
        weight = max(1, int(weights.get("json_object", 1)))
        return ["json_object"] * weight

    async def put_nowait(self, task: QueuedTask) -> bool:
        async with self._cond:
            if self._size >= self._max_size:
                return False
            self._queues[task.kind].append(task)
            self._size += 1
            self._cond.notify()
            return True

    async def requeue(self, task: QueuedTask) -> bool:
        async with self._cond:
            if self._size >= self._max_size:
                return False
            self._queues[task.kind].appendleft(task)
            self._size += 1
            self._cond.notify()
            return True

    async def get(self) -> QueuedTask:
        async with self._cond:
            while True:
                while self._size <= 0:
                    await self._cond.wait()
                kind = self._schedule[self._cursor % len(self._schedule)]
                self._cursor = (self._cursor + 1) % len(self._schedule)
                queue = self._queues[kind]
                if queue:
                    self._size -= 1
                    return queue.popleft()
                self._size = sum(len(queue) for queue in self._queues.values())

    async def size(self) -> int:
        async with self._cond:
            return self._size
