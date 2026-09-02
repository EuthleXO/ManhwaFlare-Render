# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: daily bonus quota claim."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def _claim(uid: int) -> str:
    doc = await db.ensure_user(uid)
    today = db.utcnow().strftime("%Y-%m-%d")
    if doc.get("bonus_date") == today:
        return "already"
    await db.get().users.update_one(
        {"user_id": uid},
        {"$set": {"bonus_date": today}, "$inc": {"daily_used": -2}},
    )
    return "ok"


async def cmd_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    r = await _claim(user.id)
    if r == "already":
        await update.message.reply_text(sc("bonus already claimed today"))
    else:
        await update.message.reply_text(f"<b>{sc('bonus claimed')}</b>\n+2 {sc('chapters today')}", parse_mode="HTML")


async def panel_bonus(q, context, user, is_owner, is_admin) -> None:
    r = await _claim(user.id)
    msg = sc("bonus already claimed today") if r == "already" else f"<b>{sc('bonus claimed')}</b>\n+2 {sc('chapters today')}"
    await panel_edit(q, msg, back_kb())


register_command("bonus", cmd_bonus, "Daily bonus +2")
register_panel("bonus", panel_bonus)
