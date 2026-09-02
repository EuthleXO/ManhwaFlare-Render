
"""Notify when queue finishes."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_notify(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    cur = await db.get_user_setting(uid, "notify_done", "1")
    new = "0" if cur == "1" else "1"
    await db.set_user_setting(uid, "notify_done", new)
    await update.message.reply_text(sc("notify on") if new == "1" else sc("notify off"))

async def panel_notify(q, context, user, is_owner, is_admin) -> None:
    cur = await db.get_user_setting(user.id, "notify_done", "1")
    await panel_edit(q, f"<b>{sc('notify')}</b>\n{sc('status')}: {'ON' if cur=='1' else 'OFF'}", back_kb(
        [[__import__("Manhwaflare.ui.keyboards", fromlist=["btn"]).btn(sc("toggle"), "p:notify", "success")]]
    ))
    if q.data and q.data.endswith("notify") and context.user_data.get("_toggled"):
        pass

register_command("notify", cmd_notify, "Toggle job done notify")
register_panel("notify", panel_notify)
