"""Plugin: referral deep-link (no codes)."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def _ref_link(context, uid: int) -> str:
    me = await context.bot.get_me()
    return f"https://t.me/{me.username}?start=ref_{uid}"


async def cmd_ref(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.get_or_create_referral(user.id)
    stats = await db.get_referral_stats(user.id)
    link = await _ref_link(context, user.id)
    await update.message.reply_text(
        f"<blockquote><b>{sc('referral')}</b></blockquote>\n"
        f"<b>{sc('your link')}:</b>\n<code>{link}</code>\n\n"
        f"<b>{sc('total referred')}:</b> {stats['uses']}\n\n"
        f"{sc('share this link — both get +3 chapters')}",
        parse_mode="HTML",
        disable_web_page_preview=True,
    )


async def panel_ref(q, context, user, is_owner, is_admin) -> None:
    await db.get_or_create_referral(user.id)
    stats = await db.get_referral_stats(user.id)
    link = await _ref_link(context, user.id)
    await panel_edit(
        q,
        f"<blockquote><b>{sc('referral')}</b></blockquote>\n"
        f"<b>{sc('your link')}:</b>\n<code>{link}</code>\n\n"
        f"<b>{sc('total referred')}:</b> {stats['uses']}\n\n"
        f"{sc('share this link — both get +3 chapters')}",
        back_kb(),
    )


register_command("ref", cmd_ref, "Referral link")
register_panel("ref", panel_ref)
