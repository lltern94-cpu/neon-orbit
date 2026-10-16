"""Изолированные сессии пользователей.

Каждый пользователь хранит свои настройки и путь к загруженному фото.
Данные одного пользователя не влияют на другого.
"""

from __future__ import annotations

import asyncio
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from config import DEFAULT_SCALE, TEMP_DIR


@dataclass
class UserSession:
    scale: int = DEFAULT_SCALE
    waiting_for_photo: bool = False
    photo_path: Optional[Path] = None
    photo_job_dir: Optional[Path] = None
    processing: bool = False


class SessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, UserSession] = {}
        self._global_lock = asyncio.Lock()
        self._user_locks: dict[int, asyncio.Lock] = {}

    async def get(self, user_id: int) -> UserSession:
        async with self._global_lock:
            if user_id not in self._sessions:
                self._sessions[user_id] = UserSession()
            return self._sessions[user_id]

    async def lock_for(self, user_id: int) -> asyncio.Lock:
        async with self._global_lock:
            if user_id not in self._user_locks:
                self._user_locks[user_id] = asyncio.Lock()
            return self._user_locks[user_id]

    async def clear_photo(self, user_id: int) -> None:
        session = await self.get(user_id)
        job_dir = session.photo_job_dir
        session.photo_path = None
        session.photo_job_dir = None
        session.waiting_for_photo = False
        if job_dir and job_dir.exists():
            shutil.rmtree(job_dir, ignore_errors=True)

    async def reset_flow(self, user_id: int) -> None:
        session = await self.get(user_id)
        session.waiting_for_photo = False
        session.processing = False
        await self.clear_photo(user_id)


store = SessionStore()


def ensure_temp_dir() -> Path:
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR
