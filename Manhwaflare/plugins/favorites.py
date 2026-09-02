# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: favorites / bookmarks."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel


async def cmd_favs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    favs = await db.list_favorites(user.id, 20)
    lines = [f"<b>{sc('favorites')}</b>", ""]
    if not favs:
        lines.append(sc("no favorites yet"))
        lines.append(sc("open a title then tap save fav"))
    for f in favs:
        lines.append(f"• {f.get('title','?')[:40]} · {f.get('source','')}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def panel_favs(q, context, user, is_owner, is_admin) -> None:
    favs = await db.list_favorites(user.id, 20)
    lines = [f"<b>{sc('favorites')}</b>", ""]
    if not favs:
        lines.append(sc("no favorites yet"))
    for f in favs:
        lines.append(f"• {f.get('title','?')[:40]}")
    await panel_edit(q, "\n".join(lines), back_kb())


register_command("favs", cmd_favs, "Your favorites")
register_panel("favs", panel_favs)
