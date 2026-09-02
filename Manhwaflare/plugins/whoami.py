# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: show user / chat ids."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    chat = update.effective_chat
    if user:
        await db.ensure_user(user.id, user.username or "", user.first_name or "")
    text = (
        f"<b>{sc('your id')}</b>\n"
        f"User: <code>{user.id if user else '-'}</code>\n"
        f"Chat: <code>{chat.id if chat else '-'}</code>\n"
        f"Username: @{user.username if user and user.username else '-'}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def panel_id(q, context, user, is_owner, is_admin) -> None:
    await panel_edit(
        q,
        f"<b>{sc('your id')}</b>\n"
        f"User: <code>{user.id}</code>\n"
        f"Username: @{user.username or '-'}",
        back_kb(),
    )


register_command("id", cmd_id, "Show your Telegram ID")
register_panel("id", panel_id)
