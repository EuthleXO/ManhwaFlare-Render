# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Wait animation + safe panel edit / home reset."""
from __future__ import annotations
import asyncio
import logging
import random
from io import BytesIO

import aiohttp
from telegram import InlineKeyboardMarkup, InputFile
from telegram.error import BadRequest, TimedOut, NetworkError

from Manhwaflare.config import START_IMAGES
from Manhwaflare.text import sc

log = logging.getLogger("ui.wait")


def wait_html() -> str:
    return f"<b>› › {sc('wait a second')}...</b>"


async def _edit_raw(q, text: str, kb: InlineKeyboardMarkup | None = None) -> None:
    text = (text or "")[:4000]
    msg = q.message
    try:
        if msg and msg.photo:
            if len(text) > 1020:
                try:
                    await msg.delete()
                except Exception:
                    pass
                await q.message.chat.send_message(
                    text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
                )
            else:
                await q.edit_message_caption(caption=text[:1024], parse_mode="HTML", reply_markup=kb)
        else:
            await q.edit_message_text(
                text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
            )
    except BadRequest as e:
        if "not modified" in str(e).lower():
            return
        try:
            await q.message.chat.send_message(
                text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
            )
        except Exception:
            pass
    except (TimedOut, NetworkError):
        pass


async def panel_edit(q, text: str, kb: InlineKeyboardMarkup, photo: bool = False) -> None:
    text = (text or "")[:4000]
    try:
        await _edit_raw(q, wait_html(), None)
        await asyncio.sleep(0.22)
    except Exception:
        pass
    await _edit_raw(q, text, kb)


async def panel_home(q, context, text: str, kb: InlineKeyboardMarkup) -> None:
    """Force clean home: delete poster photo message if needed, send start panel."""
    try:
        await _edit_raw(q, wait_html(), None)
        await asyncio.sleep(0.15)
    except Exception:
        pass
    msg = q.message
    # Always leave photo-detail panels: delete + fresh start message
    try:
        if msg and (msg.photo or msg.document):
            try:
                await msg.delete()
            except Exception:
                pass
            await panel_photo_chat(context.bot, msg.chat_id, text, kb)
            return
    except Exception as e:
        log.warning("panel_home: %s", e)
    await _edit_raw(q, text, kb)


async def panel_photo(update, context, text: str, kb: InlineKeyboardMarkup) -> None:
    await panel_photo_chat(context.bot, update.effective_chat.id, text, kb, reply_to=update.message)


async def panel_photo_chat(bot, chat_id: int, text: str, kb: InlineKeyboardMarkup, reply_to=None) -> None:
    text = (text or "")[:1024]
    imgs = list(START_IMAGES)
    random.shuffle(imgs)
    for url in imgs[:5]:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url, timeout=aiohttp.ClientTimeout(total=12),
                    headers={"User-Agent": "Mozilla/5.0"},
                ) as resp:
                    if resp.status != 200:
                        continue
                    data = await resp.read()
                    if len(data) < 1000:
                        continue
            kwargs = dict(
                chat_id=chat_id,
                photo=InputFile(BytesIO(data), filename="start.jpg"),
                caption=text, parse_mode="HTML", reply_markup=kb,
            )
            await bot.send_photo(**kwargs)
            return
        except Exception as e:
            log.warning("start photo: %s", e)
            continue
    await bot.send_message(
        chat_id, text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
    )
