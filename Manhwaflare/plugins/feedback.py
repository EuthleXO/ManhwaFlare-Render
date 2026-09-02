# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: user feedback to owners."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.config import OWNER_IDS, OWNER_ID
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def _send_fb(context, user, text: str) -> None:
    await db.add_log("feedback", text[:800], user.id if user else 0)
    body = (
        f"<b>feedback</b>\n"
        f"from <code>{user.id}</code> @{user.username or '-'}\n\n"
        f"{text[:1500]}"
    )
    targets = set(OWNER_IDS) | ({OWNER_ID} if OWNER_ID else set())
    for oid in targets:
        try:
            await context.bot.send_message(oid, body, parse_mode="HTML")
        except Exception:
            pass


async def cmd_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        context.user_data["await"] = "feedback"
        await update.message.reply_text(sc("send your feedback now"))
        return
    await _send_fb(context, update.effective_user, text)
    await update.message.reply_text(sc("thanks for feedback"))


async def panel_feedback(q, context, user, is_owner, is_admin) -> None:
    context.user_data["await"] = "feedback"
    await panel_edit(q, f"<b>{sc('feedback')}</b>\n{sc('send your message as text')}", back_kb())


register_command("feedback", cmd_feedback, "Send feedback")
register_panel("feedback", panel_feedback)
