# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Auth decorators — users + admin + owner."""
from __future__ import annotations
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.text import sc


def admin_only(fn: Callable) -> Callable:
    @wraps(fn)
    async def w(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **k) -> Any:
        u = update.effective_user
        if not u or not await db.is_admin(u.id):
            if update.callback_query:
                await update.callback_query.answer(sc("access denied"), show_alert=True)
            elif update.message:
                await update.message.reply_text(
                    f"<b>{sc('access denied')}</b>\n{sc('owner / admins only')}",
                    parse_mode="HTML",
                )
            return
        return await fn(update, context, *a, **k)
    return w


def owner_only(fn: Callable) -> Callable:
    @wraps(fn)
    async def w(update: Update, context: ContextTypes.DEFAULT_TYPE, *a, **k) -> Any:
        u = update.effective_user
        if not u or not await db.is_owner(u.id):
            if update.callback_query:
                await update.callback_query.answer(sc("owner only"), show_alert=True)
            elif update.message:
                await update.message.reply_text(f"<b>{sc('owner only')}</b>", parse_mode="HTML")
            return
        return await fn(update, context, *a, **k)
    return w


async def register_touch(update: Update) -> None:
    """Ensure user exists in DB on any interaction."""
    u = update.effective_user
    if not u:
        return
    await db.ensure_user(u.id, u.username or "", u.first_name or "")
