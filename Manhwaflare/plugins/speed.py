
"""Bot latency test."""
import time
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_speed(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    t0 = time.perf_counter()
    m = await update.message.reply_text("…")
    ms = int((time.perf_counter() - t0) * 1000)
    await m.edit_text(f"<b>{sc('speed')}</b>\n<code>{ms} ms</code>", parse_mode="HTML")

async def panel_speed(q, context, user, is_owner, is_admin) -> None:
    await panel_edit(q, f"<b>{sc('speed')}</b>\n<code>ok</code>", back_kb())

register_command("speed", cmd_speed, "Latency test")
register_panel("speed", panel_speed)
