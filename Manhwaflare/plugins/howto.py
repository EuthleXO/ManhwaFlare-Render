# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: quick how-to guide."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

GUIDE = (
    f"<b>{sc('how to use')}</b>\n\n"
    "1. /search name — find manhwa\n"
    "2. Pick source → open title\n"
    "3. Pick chapter → pick your channel\n"
    "4. Bot builds PDF & uploads\n\n"
    f"<b>{sc('channels')}</b>\n"
    "• Add bot as admin in your channel\n"
    "• /addch -100xxxxxxxxxx\n"
    "• Only you see your channels\n\n"
    f"<b>{sc('limits')}</b>\n"
    "• Free: 5 chapters/day, no bulk\n"
    "• /premium — upgrade plans\n"
    "• /bonus — daily +2\n"
    "• /ref — referral bonus\n"
)


async def cmd_howto(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(GUIDE, parse_mode="HTML")


async def panel_howto(q, context, user, is_owner, is_admin) -> None:
    await panel_edit(q, GUIDE, back_kb())


register_command("howto", cmd_howto, "How to use")
register_panel("howto", panel_howto)
