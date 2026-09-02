# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: top uploaders leaderboard."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_top(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await db.leaderboard_uploaders(10)
    lines = [f"<b>{sc('leaderboard')}</b>", ""]
    if not rows:
        lines.append(sc("no data yet"))
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <code>{r.get('user_id')}</code> — {r.get('count')} uploads")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def panel_top(q, context, user, is_owner, is_admin) -> None:
    rows = await db.leaderboard_uploaders(10)
    lines = [f"<b>{sc('leaderboard')}</b>", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <code>{r.get('user_id')}</code> — {r.get('count')}")
    if len(lines) == 2:
        lines.append(sc("no data yet"))
    await panel_edit(q, "\n".join(lines), back_kb())


register_command("top", cmd_top, "Top uploaders")
register_panel("top", panel_top)
