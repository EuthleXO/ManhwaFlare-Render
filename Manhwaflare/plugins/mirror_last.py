# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: show last completed upload info."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_last(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    doc = await db.get().jobs.find_one(
        {"admin_id": user.id, "status": "done"},
        sort=[("updated_at", -1)],
    )
    if not doc:
        await update.message.reply_text(sc("no completed jobs"))
        return
    await update.message.reply_text(
        f"<b>{sc('last upload')}</b>\n"
        f"{doc.get('manga_title')}\n"
        f"ch {doc.get('chapter_num')}\n"
        f"{sc('channel')}: {doc.get('channel_title','')}",
        parse_mode="HTML",
    )


async def panel_last(q, context, user, is_owner, is_admin) -> None:
    doc = await db.get().jobs.find_one(
        {"admin_id": user.id, "status": "done"},
        sort=[("updated_at", -1)],
    )
    if not doc:
        await panel_edit(q, sc("no completed jobs"), back_kb())
        return
    await panel_edit(
        q,
        f"<b>{sc('last upload')}</b>\n{doc.get('manga_title')}\nch {doc.get('chapter_num')}",
        back_kb(),
    )


register_command("last", cmd_last, "Last upload")
register_panel("last", panel_last)
