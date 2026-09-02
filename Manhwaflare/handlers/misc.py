# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Inline query + chat member updates."""
from __future__ import annotations
import logging

from telegram import (
    Update, InlineQueryResultArticle, InputTextMessageContent,
)
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.scraper import search_manhwa
from Manhwaflare.text import sc

log = logging.getLogger("mf.misc")

async def on_inline(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = (update.inline_query.query or "").strip()
    user = update.inline_query.from_user
    if not query or len(query) < 2:
        await update.inline_query.answer([], cache_time=10, is_personal=True)
        return
    if not await db.is_admin(user.id):
        from uuid import uuid4
        await update.inline_query.answer([
            InlineQueryResultArticle(
                id=str(uuid4()), title=sc("access denied"),
                input_message_content=InputTextMessageContent(sc("owner / admins only")),
            )
        ], cache_time=30, is_personal=True)
        return
    results, _ = await search_manhwa(query, page=1)
    from uuid import uuid4
    arts = []
    for r in results[:12]:
        arts.append(InlineQueryResultArticle(
            id=str(uuid4()),
            title=r["title"][:60],
            description=sc(f"slug: {r['slug']}"),
            thumbnail_url=r.get("poster") or None,
            input_message_content=InputTextMessageContent(f"/search {r['title']}"),
        ))
    await update.inline_query.answer(arts, cache_time=20, is_personal=True)


# ── channel auto-detect ───────────────────────────────────

async def on_my_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    mcm = update.my_chat_member
    if not mcm:
        return
    chat = mcm.chat
    if chat.type not in ("channel", "supergroup", "group"):
        return
    st = mcm.new_chat_member.status
    is_admin = st in ("administrator", "creator")
    left = st in ("left", "kicked")
    await db.upsert_channel(
        str(chat.id), chat.title or "", chat.username or "", chat.type,
        is_bot_admin=is_admin and not left,
        added_by=mcm.from_user.id if mcm.from_user else None,
    )
    await db.add_log("info", f"channel {'add' if is_admin else 'rm'}: {chat.title} ({chat.id})",
                     mcm.from_user.id if mcm.from_user else 0)


# ── lifecycle ─────────────────────────────────────────────

