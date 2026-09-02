
"""Bookmark last opened title."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_bm(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    sel = context.user_data.get("sel") or {}
    title = sel.get("title") or ""
    if not title:
        await update.message.reply_text(sc("open a title first"))
        return
    await db.add_favorite(update.effective_user.id, sel.get("slug") or title, title, sel.get("url") or "", sel.get("source") or "")
    await update.message.reply_text(f"<b>{sc('bookmarked')}</b>\n{title}", parse_mode="HTML")

async def panel_bm(q, context, user, is_owner, is_admin) -> None:
    sel = context.user_data.get("sel") or {}
    title = sel.get("title") or ""
    if title:
        await db.add_favorite(user.id, sel.get("slug") or title, title, sel.get("url") or "", sel.get("source") or "")
        await panel_edit(q, f"<b>{sc('bookmarked')}</b>\n{title}", back_kb())
    else:
        await panel_edit(q, sc("open a title first"), back_kb())

register_command("bm", cmd_bm, "Bookmark current")
register_panel("bm", panel_bm)
