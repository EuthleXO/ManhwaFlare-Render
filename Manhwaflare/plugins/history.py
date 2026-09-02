# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: user activity history."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_history(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    rows = await db.list_history(user.id, 15)
    lines = [f"<b>{sc('history')}</b>", ""]
    if not rows:
        lines.append(sc("empty"))
    for r in rows:
        lines.append(f"• [{r.get('kind')}] {r.get('title','')[:40]}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def panel_history(q, context, user, is_owner, is_admin) -> None:
    rows = await db.list_history(user.id, 15)
    lines = [f"<b>{sc('history')}</b>", ""]
    if not rows:
        lines.append(sc("empty"))
    for r in rows:
        lines.append(f"• [{r.get('kind')}] {r.get('title','')[:40]}")
    await panel_edit(q, "\n".join(lines), back_kb())


register_command("history", cmd_history, "Recent activity")
register_panel("history", panel_history)
