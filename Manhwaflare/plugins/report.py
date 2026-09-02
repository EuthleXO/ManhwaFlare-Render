# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: report broken chapter / title."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.config import OWNER_ID
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        context.user_data["await"] = "report"
        await update.message.reply_text(sc("send report details now"))
        return
    user = update.effective_user
    await db.add_log("report", text[:500], user.id if user else 0)
    try:
        if OWNER_ID:
            await context.bot.send_message(
                OWNER_ID,
                f"<b>report</b> from <code>{user.id}</code>\n{text[:1000]}",
                parse_mode="HTML",
            )
    except Exception:
        pass
    await update.message.reply_text(sc("report sent — thanks"))


async def panel_report(q, context, user, is_owner, is_admin) -> None:
    context.user_data["await"] = "report"
    await panel_edit(q, f"<b>{sc('report')}</b>\n{sc('send details as text now')}", back_kb())


register_command("report", cmd_report, "Report issue")
register_panel("report", panel_report)
