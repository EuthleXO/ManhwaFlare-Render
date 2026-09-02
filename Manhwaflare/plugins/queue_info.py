# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: global upload queue status."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_queue(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = await db.count_queue()
    await update.message.reply_text(
        f"<b>{sc('queue')}</b>\n"
        f"{sc('pending')}: <b>{q['pending']}</b>\n"
        f"{sc('running')}: <b>{q['running']}</b>",
        parse_mode="HTML",
    )


async def panel_queue(q, context, user, is_owner, is_admin) -> None:
    info = await db.count_queue()
    await panel_edit(
        q,
        f"<b>{sc('queue')}</b>\n"
        f"{sc('pending')}: <b>{info['pending']}</b>\n"
        f"{sc('running')}: <b>{info['running']}</b>",
        back_kb(),
    )


register_command("queue", cmd_queue, "Queue status")
register_panel("queue", panel_queue)
