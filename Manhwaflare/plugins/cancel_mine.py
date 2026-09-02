# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: cancel all own pending jobs."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    res = await db.get().jobs.update_many(
        {"admin_id": user.id, "status": "pending"},
        {"$set": {"cancel_requested": True, "status": "cancelled"}},
    )
    await update.message.reply_text(
        f"<b>{sc('cancelled')}</b> {res.modified_count} {sc('pending jobs')}",
        parse_mode="HTML",
    )


async def panel_cancel(q, context, user, is_owner, is_admin) -> None:
    res = await db.get().jobs.update_many(
        {"admin_id": user.id, "status": "pending"},
        {"$set": {"cancel_requested": True, "status": "cancelled"}},
    )
    await panel_edit(q, f"<b>{sc('cancelled')}</b> {res.modified_count}", back_kb())


register_command("cancel", cmd_cancel, "Cancel my pending jobs")
register_panel("cancelmine", panel_cancel)
