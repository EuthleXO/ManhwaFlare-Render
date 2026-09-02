
"""Tip: jump to chapter by number via search."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

MSG = (
    f"<b>{sc('chapter tip')}</b>\n"
    f"1. Search title\n"
    f"2. Open series\n"
    f"3. Tap chapter · pick channel"
)

async def cmd_newchap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(MSG, parse_mode="HTML")

async def panel_newchap(q, context, user, is_owner, is_admin) -> None:
    await panel_edit(q, MSG, back_kb())

register_command("newchap", cmd_newchap, "How chapters work")
register_panel("newchap", panel_newchap)
