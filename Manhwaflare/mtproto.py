"""MTProto client (Pyrogram) for large media uploads (~2GB)."""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable, Optional

from Manhwaflare.config import API_ID, API_HASH, BOT_TOKEN, USE_MTPROTO, BASE_DIR

log = logging.getLogger("mf.mtproto")

_client = None
_lock = asyncio.Lock()


def mtproto_enabled() -> bool:
    return bool(USE_MTPROTO)


async def get_client():
    """Lazy-start Pyrogram bot client."""
    global _client
    if not USE_MTPROTO:
        return None
    async with _lock:
        if _client is not None:
            return _client
        try:
            from pyrogram import Client
        except ImportError:
            log.error("pyrogram not installed — MTProto disabled")
            return None
        workdir = os.path.join(BASE_DIR, "sessions")
        os.makedirs(workdir, exist_ok=True)
        app = Client(
            name="manhwaflare_bot",
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workdir=workdir,
            in_memory=False,
        )
        await app.start()
        _client = app
        me = await app.get_me()
        log.info("MTProto started as @%s (max file ~2GB)", me.username)
        return _client


async def stop_client() -> None:
    global _client
    async with _lock:
        if _client is not None:
            try:
                await _client.stop()
            except Exception as e:
                log.warning("mtproto stop: %s", e)
            _client = None


async def send_video_file(
    chat_id: int,
    path: str,
    caption: str = "",
    progress: Optional[Callable] = None,
) -> bool:
    """
    Upload video via MTProto. Returns True on success.
    progress(current: int, total: int) optional callback.
    """
    client = await get_client()
    if not client:
        return False
    if not os.path.isfile(path):
        return False

    async def _prog(current, total):
        if progress:
            try:
                if asyncio.iscoroutinefunction(progress):
                    await progress(current, total)
                else:
                    progress(current, total)
            except Exception:
                pass

    try:
        await client.send_video(
            chat_id=chat_id,
            video=path,
            caption=caption[:1024] if caption else None,
            supports_streaming=True,
            progress=_prog if progress else None,
        )
        return True
    except Exception as e:
        log.warning("send_video failed: %s — try document", e)
        try:
            await client.send_document(
                chat_id=chat_id,
                document=path,
                caption=caption[:1024] if caption else None,
                progress=_prog if progress else None,
            )
            return True
        except Exception as e2:
            log.error("send_document failed: %s", e2)
            return False


async def send_photos(chat_id: int, paths: list, caption: str = "") -> bool:
    client = await get_client()
    if not client or not paths:
        return False
    try:
        from pyrogram.types import InputMediaPhoto
        media = []
        for i, p in enumerate(paths[:10]):
            if not os.path.isfile(p):
                continue
            media.append(
                InputMediaPhoto(p, caption=caption[:1024] if i == 0 and caption else None)
            )
        if not media:
            return False
        await client.send_media_group(chat_id, media)
        return True
    except Exception as e:
        log.error("send_photos: %s", e)
        return False
