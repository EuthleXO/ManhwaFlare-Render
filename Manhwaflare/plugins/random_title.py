# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
"""Plugin: random trending title."""
from __future__ import annotations
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.scrapers import multi_trending
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel
import random


async def cmd_random(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await db.ensure_user(user.id, user.username or "", user.first_name or "")
    msg = await update.message.reply_text(f"<b>› › {sc('wait a second')}...</b>", parse_mode="HTML")
    try:
        items = await multi_trending(20)
    except Exception as e:
        await msg.edit_text(f"{sc('error')}: {e}")
        return
    if not items:
        await msg.edit_text(sc("no results"))
        return
    it = random.choice(items)
    title = it.get("title") or "?"
    src = it.get("source") or ""
    await db.add_history(user.id, "random", title, {"source": src})
    await msg.edit_text(
        f"<b>{sc('random')}</b>\n\n<b>{title}</b>\n{sc('source')}: {src}\n\n"
        f"{sc('use search to open this title')}",
        parse_mode="HTML",
    )


async def panel_random(q, context, user, is_owner, is_admin) -> None:
    try:
        items = await multi_trending(20)
    except Exception as e:
        await panel_edit(q, f"{sc('error')}: {e}", back_kb())
        return
    if not items:
        await panel_edit(q, sc("no results"), back_kb())
        return
    it = random.choice(items)
    title = it.get("title") or "?"
    await db.add_history(user.id, "random", title, {})
    await panel_edit(
        q,
        f"<b>{sc('random')}</b>\n\n<b>{title}</b>\n{sc('source')}: {it.get('source','')}",
        back_kb([btn(sc("again"), "p:random", "success")]),
    )


register_command("random", cmd_random, "Random title")
register_panel("random", panel_random)
