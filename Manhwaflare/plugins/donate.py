
"""Support / donate info."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.config import OWNER_ID, SUPPORT_CHANNEL
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb, url_btn
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

TEXT = (
    f"<blockquote><b>{sc('support project')}</b></blockquote>\n"
    f"{sc('premium keeps the bot online')}\n"
    f"/premium · @{SUPPORT_CHANNEL}"
)

async def cmd_donate(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(TEXT, parse_mode="HTML")

async def panel_donate(q, context, user, is_owner, is_admin) -> None:
    await panel_edit(q, TEXT, back_kb(
        [url_btn(sc("owner"), f"tg://user?id={OWNER_ID}")],
    ))

register_command("donate", cmd_donate, "Support bot")
register_panel("donate", panel_donate)
