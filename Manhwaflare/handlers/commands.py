# ManhwaFlare commands
from __future__ import annotations
import logging
import time

from telegram import Update
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.auth import admin_only, owner_only
from Manhwaflare.config import OWNER_USERNAME, APP_VERSION
from Manhwaflare.helpers import FakeQuery
from Manhwaflare.plans import PLANS, PLAN_ORDER, get_plan, can_ai
from Manhwaflare.scrapers import SOURCES
from Manhwaflare.text import sc, mono
from Manhwaflare.ui.home import start_caption, main_kb
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_photo
from Manhwaflare.handlers.aivideo import _show_ai_videos

log = logging.getLogger("mf.commands")


async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    t0 = time.perf_counter()
    msg = await update.message.reply_text("pong...")
    ms = int((time.perf_counter() - t0) * 1000)
    await msg.edit_text(f"<b>pong</b> · <code>{ms}ms</code>", parse_mode="HTML")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await db.ensure_user(user.id, user.username or "", user.first_name or "")
    # Deep link: /start ref_123456789
    if context.args:
        arg = (context.args[0] or "").strip()
        if arg.startswith("ref_"):
            res = await db.apply_referral(user.id, arg)
            if res == "ok":
                try:
                    await update.message.reply_text(
                        f"<b>{sc('welcome')}</b>\n{sc('referral applied +3 bonus')}",
                        parse_mode="HTML",
                    )
                except Exception:
                    pass
    is_owner = await db.is_owner(user.id)
    is_admin = await db.is_admin(user.id)
    plan_id = await db.get_user_plan_id(user.id)
    plan = get_plan(plan_id)
    _ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=0)
    cap = start_caption(user, is_owner, plan.get("name", "Free"), f"{used}/{limit}")
    await panel_photo(update, context, cap, main_kb(is_owner, is_admin))


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = (
        f"<blockquote><b>{sc('help')}</b></blockquote>\n"
        f"/start — home\n"
        f"/search query — search\n"
        f"/trending — trending\n"
        f"/aivid — AI videos\n"
        f"/premium — plans\n"
        f"/profile — your plan\n"
        f"/myjobs — uploads\n"
        f"/ping — latency\n"
        f"/help — this message\n\n"
        f"<b>{sc('admin')}</b>\n"
        f"/broadcast · /addch\n\n"
        f"<b>{sc('owner')}</b>\n"
        f"/setplan · /addadmin · /rmadmin · /stats"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_premium(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    lines = [f"<blockquote><b>{sc('premium plans')}</b></blockquote>", ""]
    for pid in PLAN_ORDER:
        pl = PLANS[pid]
        lines.append(f"<b>{pl['name']}</b> · {pl['price']}")
        for perk in pl["perks"]:
            lines.append(f"  • {perk}")
        lines.append("")
    if OWNER_USERNAME:
        lines.append(f"{sc('contact')} @{OWNER_USERNAME.lstrip('@')}")
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


async def cmd_profile(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    await db.ensure_user(user.id, user.username or "", user.first_name or "")
    plan_id = await db.get_user_plan_id(user.id)
    plan = get_plan(plan_id)
    _ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=0)
    udoc = await db.get_user(user.id) or {}
    is_owner = await db.is_owner(user.id)
    is_admin = await db.is_admin(user.id)
    text = (
        f"<blockquote><b>{sc('profile')}</b></blockquote>\n"
        f"<b>ID:</b> <code>{user.id}</code>\n"
        f"<b>{sc('plan')}:</b> {plan['name']} ({plan['price']})\n"
        f"<b>{sc('today')}:</b> {used}/{limit}\n"
        f"<b>{sc('total uploads')}:</b> {udoc.get('total_uploads', 0)}\n"
        f"<b>{sc('role')}:</b> {'owner' if is_owner else ('admin' if is_admin else 'user')}"
    )
    await update.message.reply_text(text, parse_mode="HTML")


async def cmd_ai_vid(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not user:
        return
    await db.ensure_user(user.id, user.username or "", user.first_name or "")
    plan_id = await db.get_user_plan_id(user.id)
    if not can_ai(plan_id) and not await db.is_admin(user.id):
        await update.message.reply_text(
            f"<b>{sc('premium required')}</b>\n{sc('AI videos need Pro+')}\n/premium",
            parse_mode="HTML",
        )
        return
    msg = await update.message.reply_text(
        f"<b>› › {sc('wait a second')}...</b>",
        parse_mode="HTML",
    )
    q = FakeQuery(msg, user, data="p:aivideos")
    await _show_ai_videos(q, context, 1)


async def cmd_search(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user:
        await db.ensure_user(user.id, user.username or "", user.first_name or "")
    query = " ".join(context.args).strip() if context.args else ""
    if not query:
        await update.message.reply_text(
            f"{sc('usage')}: {mono('/search solo leveling')}", parse_mode="HTML"
        )
        return
    context.user_data["search_q"] = query
    lines = [
        f"<b>{sc('search')}</b> · <code>{query}</code>",
        "",
        f"<b>{sc('choose source')}</b>",
    ]
    rows = [[btn(sc("all sources"), "p:srcpick:all", "success")]]
    row = []
    for s in SOURCES:
        row.append(btn(sc(s["name"]), f"p:srcpick:{s['id']}", "primary"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    await update.message.reply_text(
        "\n".join(lines), parse_mode="HTML", reply_markup=back_kb(*rows),
    )


async def cmd_trending(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    from Manhwaflare.scrapers import multi_trending
    user = update.effective_user
    if user:
        await db.ensure_user(user.id, user.username or "", user.first_name or "")
    msg = await update.message.reply_text(f"› › {sc('wait a second')}...")
    try:
        items = await multi_trending(16)
    except Exception as e:
        await msg.edit_text(f"{sc('error')}: {e}")
        return
    lines = [f"<blockquote><b>{sc('trending')}</b></blockquote>", ""]
    for it in items[:16]:
        title = (it.get("title") or "?")[:30]
        src = it.get("source") or ""
        lines.append(f"• {title} · {src}")
    await msg.edit_text("\n".join(lines)[:3500], parse_mode="HTML")


async def cmd_myjobs(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    try:
        cur = db.get().jobs.find({"admin_id": user.id}).sort("created_at", -1).limit(15)
        mine = await cur.to_list(15)
    except Exception:
        mine = []
    lines = [f"<blockquote><b>{sc('my jobs')}</b></blockquote>", ""]
    if not mine:
        lines.append(sc("no jobs yet"))
    for j in mine:
        lines.append(
            f"• ch{j.get('chapter_num')} · {j.get('status')} · {(j.get('manga_title') or '')[:24]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")


@admin_only
async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    text = " ".join(context.args).strip() if context.args else ""
    if not text:
        context.user_data["await"] = "broadcast"
        await update.message.reply_text(sc("send the message to broadcast now"))
        return
    ids = await db.list_all_user_ids()
    ok = fail = 0
    status = await update.message.reply_text(f"{sc('broadcasting')} 0/{len(ids)}...")
    for i, uid in enumerate(ids):
        try:
            await context.bot.send_message(uid, text, parse_mode="HTML", disable_web_page_preview=True)
            ok += 1
        except Exception:
            fail += 1
        if i % 25 == 0:
            try:
                await status.edit_text(f"{sc('broadcasting')} {i}/{len(ids)}...")
            except Exception:
                pass
    await status.edit_text(f"<b>{sc('broadcast done')}</b>\nOK {ok} · fail {fail}", parse_mode="HTML")


async def cmd_addch(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        context.user_data["await"] = "addch"
        await update.message.reply_text(
            f"<b>{sc('usage')}:</b> <code>/addch -100xxxxxxxxxx</code>\n"
            f"{sc('bot must be admin in that channel')}",
            parse_mode="HTML",
        )
        return
    raw = context.args[0].strip()
    try:
        chat_id = int(raw)
    except ValueError:
        await update.message.reply_text(sc("invalid chat id"))
        return
    try:
        chat = await context.bot.get_chat(chat_id)
        title = chat.title or str(chat_id)
    except Exception as e:
        await update.message.reply_text(f"{sc('failed')}: {e}")
        return
    await db.upsert_channel(
        chat_id=str(chat_id),
        title=title,
        is_bot_admin=True,
        added_by=update.effective_user.id,
    )
    await db.add_log("info", f"channel +{chat_id} {title}", update.effective_user.id)
    await update.message.reply_text(
        f"<b>{sc('channel added')}</b>\n{title}\n<code>{chat_id}</code>",
        parse_mode="HTML",
    )


@owner_only
async def cmd_setplan(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            f"{sc('usage')}: <code>/setplan 123456 pro</code>\nfree pro ultra max flare",
            parse_mode="HTML",
        )
        return
    try:
        target = int(context.args[0])
    except ValueError:
        await update.message.reply_text(sc("invalid user id"))
        return
    plan = context.args[1].lower()
    if plan not in PLANS:
        await update.message.reply_text(sc("invalid plan"))
        return
    days = 30
    if len(context.args) >= 3:
        try:
            days = int(context.args[2])
        except ValueError:
            days = 30
    await db.set_user_plan(target, plan, days=days)
    await update.message.reply_text(
        f"<b>{sc('plan set')}</b>\n<code>{target}</code> → <b>{plan}</b> ({days}d)",
        parse_mode="HTML",
    )


@owner_only
async def cmd_addadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(f"{sc('usage')}: /addadmin id")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text(sc("invalid id"))
        return
    ok = await db.add_admin(uid, update.effective_user.id)
    await update.message.reply_text(sc("admin added") if ok else sc("already admin"))


@owner_only
async def cmd_rmadmin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        await update.message.reply_text(f"{sc('usage')}: /rmadmin id")
        return
    try:
        uid = int(context.args[0])
    except ValueError:
        await update.message.reply_text(sc("invalid id"))
        return
    await db.rm_admin(uid)
    await update.message.reply_text(sc("admin removed"))


@owner_only
async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    n = await db.count_users()
    await update.message.reply_text(
        f"<blockquote><b>{sc('stats')}</b></blockquote>\n"
        f"<b>{sc('users')}:</b> {n}\n"
        f"<b>{sc('version')}:</b> {APP_VERSION}",
        parse_mode="HTML",
    )


@owner_only
async def cmd_pip(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    import asyncio
    import sys
    pkg = " ".join(context.args).strip()
    if not pkg:
        await update.message.reply_text(f"{sc('usage')}: /pip package")
        return
    m = await update.message.reply_text(f"{sc('installing')} {mono(pkg)}...", parse_mode="HTML")
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "pip", "install", "--upgrade", pkg,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        out, err = await proc.communicate()
        raw = ((out or b"").decode()[-800:] + (err or b"").decode()[-300:])
        await m.edit_text(
            f"<b>{'ok' if proc.returncode == 0 else 'fail'}</b>\n<pre>{raw[-1200:]}</pre>",
            parse_mode="HTML",
        )
    except Exception as e:
        await m.edit_text(f"{sc('error')}: {e}")
