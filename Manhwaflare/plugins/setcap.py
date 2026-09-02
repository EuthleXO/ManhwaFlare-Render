# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: personal caption tag."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.config import CAPTION_TAG
from Manhwaflare.text import sc, mono
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_setcap(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    tag = " ".join(context.args).strip() if context.args else ""
    if not tag:
        cur = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        context.user_data["await"] = "setcap"
        await update.message.reply_text(
            f"<b>{sc('caption tag')}</b>\n"
            f"{sc('current')}: {mono(cur)}\n"
            f"{sc('send new tag now')} (e.g. @MyChannel)",
            parse_mode="HTML",
        )
        return
    await db.set_user_setting(user.id, "caption_tag", tag[:64])
    await update.message.reply_text(f"<b>{sc('saved')}</b>\n{mono(tag)}", parse_mode="HTML")


async def panel_setcap(q, context, user, is_owner, is_admin) -> None:
    cur = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
    context.user_data["await"] = "setcap"
    await panel_edit(
        q,
        f"<b>{sc('caption tag')}</b>\n{sc('current')}: <code>{cur}</code>\n"
        f"{sc('send new tag as text')}",
        back_kb(),
    )


register_command("setcap", cmd_setcap, "Set caption tag")
register_panel("setcap", panel_setcap)
