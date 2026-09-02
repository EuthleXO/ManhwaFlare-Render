# ManhwaFlare about plugin
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.config import APP_VERSION, OWNER_DISPLAY, SUPPORT_GROUP, SUPPORT_CHANNEL
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb, url_btn
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel
from telegram import InlineKeyboardMarkup


async def cmd_about(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    owners = ", ".join(
        f"@{o.get('username')}" if o.get("username") else str(o.get("id"))
        for o in OWNER_DISPLAY
    )
    await update.message.reply_text(
        f"<b>ManhwaFlare</b> {APP_VERSION}\n"
        f"{sc('multi source manhwa pdf bot')}\n\n"
        f"Owner: {owners}\n"
        f"Support: @{SUPPORT_CHANNEL}",
        parse_mode="HTML",
    )


async def panel_about(q, context, user, is_owner, is_admin) -> None:
    owners = ", ".join(
        f"@{o.get('username')}" if o.get("username") else str(o.get("id"))
        for o in OWNER_DISPLAY
    )
    ch = SUPPORT_CHANNEL.lstrip("@")
    rows = [
        [url_btn(sc("support channel"), f"https://t.me/{ch}")],
        [url_btn(sc("support group"), SUPPORT_GROUP)],
    ]
    await panel_edit(
        q,
        f"<b>ManhwaFlare</b> {APP_VERSION}\nOwner: {owners}\n@{SUPPORT_CHANNEL}",
        back_kb(*rows),
    )


register_command("about", cmd_about, "About bot")
register_panel("about", panel_about)
