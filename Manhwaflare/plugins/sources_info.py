# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: list active scrape sources."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.scrapers import SOURCES
from Manhwaflare.text import sc, mono
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_sources(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"<b>{sc('sources')}</b>", ""]
    for s in SOURCES:
        lines.append(f"• <b>{s['name']}</b>\n  {mono(s['host'])}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def panel_sources(q, context, user, is_owner, is_admin) -> None:
    lines = [f"<b>{sc('sources')}</b>", ""]
    for s in SOURCES:
        lines.append(f"• <b>{s['name']}</b> — {s['host']}")
    await panel_edit(q, "\n".join(lines), back_kb())


register_command("sources", cmd_sources, "Active sources")
register_panel("sources", panel_sources)
