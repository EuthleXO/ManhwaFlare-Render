
"""Show referral leaderboard of uses."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def _top():
    try:
        cur = db.get().referrals.find().sort("uses", -1).limit(10)
        return await cur.to_list(10)
    except Exception:
        return []

async def cmd_invites(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    rows = await _top()
    lines = [f"<b>{sc('top inviters')}</b>", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <code>{r.get('owner_id')}</code> · {r.get('uses', 0)}")
    if not rows:
        lines.append(sc("none yet"))
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

async def panel_invites(q, context, user, is_owner, is_admin) -> None:
    rows = await _top()
    lines = [f"<b>{sc('top inviters')}</b>", ""]
    for i, r in enumerate(rows, 1):
        lines.append(f"{i}. <code>{r.get('owner_id')}</code> · {r.get('uses', 0)}")
    stats = await db.get_referral_stats(user.id)
    lines += ["", f"{sc('you')}: {stats['uses']}"]
    await panel_edit(q, "\n".join(lines), back_kb())

register_command("invites", cmd_invites, "Top inviters")
register_panel("invites", panel_invites)
