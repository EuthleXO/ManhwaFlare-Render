
"""Quick my channels list."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb, btn
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def panel_mych(q, context, user, is_owner, is_admin) -> None:
    chs = await db.get_channels(admin_only=False, owner_id=None if is_owner else user.id)
    lines = [f"<b>{sc('my channels')}</b> · {len(chs)}", ""]
    for c in chs[:25]:
        lines.append(f"• {(c.get('title') or c.get('chat_id'))[:40]}")
    await panel_edit(q, "\n".join(lines) or sc("none"), back_kb([btn(sc("add channel"), "p:addch", "success")]))

async def cmd_mych(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    is_owner = await db.is_owner(uid)
    chs = await db.get_channels(admin_only=False, owner_id=None if is_owner else uid)
    lines = [f"<b>{sc('my channels')}</b> · {len(chs)}"]
    for c in chs[:25]:
        lines.append(f"• {c.get('title') or c.get('chat_id')}")
    await update.message.reply_text("\n".join(lines) or sc("none"), parse_mode="HTML")

register_command("mychannels", cmd_mych, "List channels")
register_panel("mychannels", panel_mych)
