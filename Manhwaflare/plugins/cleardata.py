
"""Clear personal search cache in session."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    for k in list(context.user_data.keys()):
        if k not in ("nav_stack",):
            context.user_data.pop(k, None)
    await update.message.reply_text(sc("session cleared"))

async def panel_clear(q, context, user, is_owner, is_admin) -> None:
    for k in list(context.user_data.keys()):
        if k not in ("nav_stack",):
            context.user_data.pop(k, None)
    await panel_edit(q, sc("session cleared"), back_kb())

register_command("clear", cmd_clear, "Clear session")
register_panel("clear", panel_clear)
