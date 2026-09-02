
"""Live sources status."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.scrapers import SOURCES
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_srcstat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"<b>{sc('sources')}</b>", ""]
    for s in SOURCES:
        lines.append(f"• {s.get('name')} · <code>{s.get('id')}</code>")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def panel_srcstat(q, context, user, is_owner, is_admin) -> None:
    lines = [f"<b>{sc('sources')}</b>", ""]
    for s in SOURCES:
        lines.append(f"• {s.get('name')}")
    await panel_edit(q, "\n".join(lines), back_kb())

register_command("srcstat", cmd_srcstat, "Sources status")
register_panel("srcstat", panel_srcstat)
