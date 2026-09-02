
"""Show remaining daily quota."""
from telegram import Update
from telegram.ext import ContextTypes
from Manhwaflare import db
from Manhwaflare.plans import get_plan
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import back_kb, btn
from Manhwaflare.ui.wait import panel_edit
from Manhwaflare.plugins import register_command, register_panel

async def cmd_quota(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    uid = update.effective_user.id
    plan_id = await db.get_user_plan_id(uid)
    plan = get_plan(plan_id)
    ok, used, limit = await db.check_daily_quota(uid, plan_id, need=0)
    await update.message.reply_text(
        f"<b>{sc('quota')}</b>\n{plan['name']}\n{used}/{limit}",
        parse_mode="HTML",
    )

async def panel_quota(q, context, user, is_owner, is_admin) -> None:
    plan_id = await db.get_user_plan_id(user.id)
    plan = get_plan(plan_id)
    ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=0)
    await panel_edit(
        q,
        f"<b>{sc('quota')}</b>\n{plan['name']}\n{used}/{limit}",
        back_kb([btn(sc("premium"), "p:premium", "success")]),
    )

register_command("quota", cmd_quota, "Daily quota")
register_panel("quota", panel_quota)
