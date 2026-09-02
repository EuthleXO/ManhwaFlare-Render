
"""Cancel all pending jobs for user."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_canceljobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = await db.cancel_user_jobs(update.effective_user.id)
    await update.message.reply_text(f"<b>{sc('cancelled')}</b>: {n}", parse_mode="HTML")

async def panel_canceljobs(q, context, user, is_owner, is_admin) -> None:
    n = await db.cancel_user_jobs(user.id)
    await panel_edit(q, f"<b>{sc('cancelled')}</b>: {n}", back_kb())

register_command("canceljobs", cmd_canceljobs, "Cancel my jobs")
register_panel("canceljobs", panel_canceljobs)
