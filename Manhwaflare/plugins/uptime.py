# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: bot uptime / health."""
from __future__ import annotations
import time
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.config import APP_VERSION
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

_STARTED = time.time()


def _uptime_str() -> str:
    sec = int(time.time() - _STARTED)
    h, r = divmod(sec, 3600)
    m, s = divmod(r, 60)
    return f"{h}h {m}m {s}s"


async def cmd_uptime(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = await db.count_queue()
    await update.message.reply_text(
        f"<b>{sc('status')}</b>\n"
        f"v{APP_VERSION}\n"
        f"{sc('uptime')}: <code>{_uptime_str()}</code>\n"
        f"{sc('pending')}: {q['pending']} · {sc('running')}: {q['running']}",
        parse_mode="HTML",
    )


async def panel_uptime(q, context, user, is_owner, is_admin) -> None:
    info = await db.count_queue()
    await panel_edit(
        q,
        f"<b>{sc('status')}</b>\nv{APP_VERSION}\n"
        f"{sc('uptime')}: <code>{_uptime_str()}</code>\n"
        f"{sc('pending')}: {info['pending']} · {sc('running')}: {info['running']}",
        back_kb(),
    )


register_command("uptime", cmd_uptime, "Bot uptime")
register_panel("uptime", panel_uptime)
