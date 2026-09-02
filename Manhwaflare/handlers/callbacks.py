# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Inline button callback router (p:*)."""
from __future__ import annotations
import asyncio
import logging
import os
import re
from datetime import datetime

from telegram import InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.auth import admin_only, owner_only
from Manhwaflare.config import (
    CAPTION_TAG, FILENAME_TEMPLATE, PAGE_SIZE, UPLOAD_RATE, UPSTREAM_REPO, BASE_DIR, APP_VERSION,
    OWNER_USERNAME, COPYRIGHT, OWNER_DISPLAY, OWNER_IDS,
    SUPPORT_GROUP, SUPPORT_CHANNEL, LOG_CHANNEL_ID,
)
from Manhwaflare.plans import PLANS, PLAN_ORDER, get_plan, can_bulk, bulk_max
from Manhwaflare.helpers import (
    FakeQuery, panel_poster, chapter_rows, _short_slug, build_caption, synopsis_block,
    send_action, react_ok,
)
from Manhwaflare.nav import nav_enter, nav_reset, nav_stack, _norm_panel_key
from Manhwaflare.panels import restore_panel, open_named_panel, open_dynamic_panel, show_sources_panel
from Manhwaflare.scrapers import (
    multi_search, multi_trending, get_detail_any, get_images_any, format_filename, SOURCES, SOURCE_BY_ID,
)
from Manhwaflare.scrapers import aivideos as aivideos_mod
from Manhwaflare.scraper import search_manhwa, get_detail, trending as fetch_trending
from Manhwaflare.text import sc, bsc, mono, hdr, ftr, bar
from Manhwaflare.ui.home import start_caption, main_kb
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit, panel_photo, panel_home, wait_html

log = logging.getLogger("mf.callbacks")

# late imports to avoid cycles — resolved at call time via functions below
from Manhwaflare.handlers.search import _show_search, _render_search_results, _show_source_picker
from Manhwaflare.handlers.aivideo import _show_ai_videos, _download_ai_video, _send_screenshots


async def _go_home(q, context, user, is_owner: bool, is_admin: bool = False) -> None:
    plan_id = await db.get_user_plan_id(user.id)
    plan = get_plan(plan_id)
    _ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=0)
    daily = f"{used}/{limit}"
    await panel_home(
        q, context,
        start_caption(user, is_owner, plan.get("name", "Free"), daily),
        main_kb(is_owner, is_admin or is_owner),
    )


async def on_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    q = update.callback_query
    if not q:
        return
    if not context.user_data.pop("_skip_answer", False):
        try:
            await q.answer()
        except Exception:
            pass
    user = getattr(q, "from_user", None) or getattr(q, "effective_user", None) or update.effective_user
    if not user:
        return
    await db.ensure_user(user.id, user.username or "", user.first_name or "")
    # ban check
    udoc = await db.get_user(user.id)
    if udoc and udoc.get("banned") and not await db.is_owner(user.id):
        await q.answer(sc("banned"), show_alert=True)
        return

    data = (q.data or "p:home")
    action = data.split(":", 1)[-1] if data.startswith("p:") else data
    is_owner = await db.is_owner(user.id)
    is_admin = await db.is_admin(user.id)
    plan_id = await db.get_user_plan_id(user.id)

    # Plugin panel routes (must be after action is defined)
    from Manhwaflare.plugins import PANEL_ACTIONS
    if action in PANEL_ACTIONS:
        try:
            await PANEL_ACTIONS[action](q, context, user, is_owner, is_admin)
        except Exception as e:
            log.exception("plugin %s", action)
            await panel_edit(q, f"{sc('error')}: {e}", back_kb())
        return

    if action == "home":
        nav_reset(context)
        await _go_home(q, context, user, is_owner, is_admin)
        return

    if action == "more":
        nav_enter(context, "more")
        rows = [
            [btn(sc("AI videos"), "p:aivideos", "primary"), btn(sc("premium"), "p:premium", "success")],
            [btn(sc("my channels"), "p:channels", "primary"), btn(sc("add channel"), "p:addch", "success")],
            [btn(sc("my jobs"), "p:myjobs", "primary"), btn(sc("profile"), "p:profile", "primary")],
            [btn(sc("support"), "p:support", "primary"), btn(sc("owner"), "p:owner", "danger")],
            [btn(sc("about"), "p:about", "primary"), btn(sc("home"), "p:home", "danger")],
        ]
        await panel_edit(q, f"<blockquote><b>{sc('more')}</b></blockquote>", InlineKeyboardMarkup(rows))
        return

    if action == "adminmenu":
        if not (is_admin or is_owner):
            await q.answer(sc("access denied"), show_alert=True)
            return
        nav_enter(context, "adminmenu")
        rows = [
            [btn(sc("pending"), "p:pending", "primary"), btn(sc("broadcast"), "p:broadcast", "danger")],
            [btn(sc("all channels"), "p:allchannels", "primary"), btn(sc("logs"), "p:logs", "primary")],
            [btn(sc("admins"), "p:admins", "primary"), btn(sc("stats"), "p:stats", "primary")],
            [btn(sc("set plan"), "p:setplan", "danger"), btn(sc("home"), "p:home", "danger")],
        ]
        await panel_edit(q, f"<blockquote><b>{sc('admin')}</b></blockquote>", InlineKeyboardMarkup(rows))
        return


    if action == "premium":
        nav_enter(context, "premium")
        lines = [
            f"<blockquote><b>{sc('premium plans')}</b></blockquote>",
            "",
        ]
        for pid in PLAN_ORDER:
            pl = PLANS[pid]
            lines.append(f"<b>{pl['name']}</b> · {pl['price']}")
            for perk in pl["perks"]:
                lines.append(f"  • {perk}")
            lines.append("")
        lines.append(sc("contact owner to upgrade"))
        for o in OWNER_DISPLAY:
            if o.get("username"):
                lines.append(f"  @{o['username']}")
            lines.append(f"  <code>{o.get('id')}</code>")
        lines.append(f"@{SUPPORT_CHANNEL}")
        lines.append(SUPPORT_GROUP)
        lines.append(f"@{OWNER_USERNAME}")
        await panel_edit(
            q, "\n".join(lines),
            back_kb(
                [btn(sc("owner"), "p:owner", "danger")],
                [btn(sc("profile"), "p:profile", "primary")],
            ),
        )
        return

    if action == "profile":
        nav_enter(context, "profile")
        plan_id = await db.get_user_plan_id(user.id)
        plan = get_plan(plan_id)
        _ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=0)
        udoc = await db.get_user(user.id) or {}
        text = (
            f"<blockquote><b>{sc('profile')}</b></blockquote>\n"
            f"<b>ID:</b> <code>{user.id}</code>\n"
            f"<b>{sc('name')}:</b> {user.first_name or '-'}\n"
            f"<b>{sc('plan')}:</b> {plan['name']} ({plan['price']})\n"
            f"<b>{sc('today')}:</b> {used}/{limit}\n"
            f"<b>{sc('total uploads')}:</b> {udoc.get('total_uploads', 0)}\n"
            f"<b>{sc('role')}:</b> {'owner' if is_owner else ('admin' if is_admin else 'user')}"
        )
        await panel_edit(q, text, back_kb([btn(sc("premium"), "p:premium", "success")]))
        return

    if action == "support":
        nav_enter(context, "support")
        from Manhwaflare.ui.keyboards import url_btn
        ch = SUPPORT_CHANNEL.lstrip("@")
        text = (
            "<blockquote><b>" + sc("support") + "</b></blockquote>" + chr(10)
            + "<b>" + sc("channel") + ":</b> @" + str(SUPPORT_CHANNEL) + chr(10)
            + "<b>" + sc("group") + ":</b>" + chr(10) + str(SUPPORT_GROUP)
        )
        await panel_edit(
            q,
            text,
            back_kb(
                [url_btn(sc("support channel"), "https://t.me/" + ch)],
                [url_btn(sc("support group"), SUPPORT_GROUP)],
            ),
        )
        return



    if action == "owner":

        nav_enter(context, "owner")
        lines = [
            f"<blockquote><b>{sc('owner')}</b></blockquote>",
            "",
        ]
        for o in OWNER_DISPLAY:
            un = o.get("username") or ""
            lines.append(f"• <b>{o.get('label','Owner')}</b>")
            if un:
                lines.append(f"  @{un}")
            lines.append(f"  <code>{o.get('id')}</code>")
        lines += [
            "",
            f"<b>{sc('support channel')}:</b> @{SUPPORT_CHANNEL}",
            f"<b>{sc('support group')}:</b>",
            SUPPORT_GROUP,
            "",
            sc("for premium / support contact owner"),
        ]
        await panel_edit(q, "\n".join(lines), back_kb(
            [btn(sc("premium"), "p:premium", "success"), btn(sc("support"), "p:support", "primary")],
        ))
        return


    if action == "allchannels":
        if not is_owner and not is_admin:
            await q.answer(sc("owner only"), show_alert=True)
            return
        nav_enter(context, "allchannels")
        channels = await db.get_channels(admin_only=False, owner_id=None)
        total = len(channels)
        lines = [
            f"<blockquote><b>{sc('all channels')}</b></blockquote>",
            f"<b>{sc('total')}:</b> {total}",
            "",
        ]
        for c in channels[:40]:
            title = c.get("title") or c.get("chat_id")
            by = c.get("added_by") or "?"
            lines.append(f"• {title}")
            lines.append(f"  id <code>{c.get('chat_id')}</code> · by <code>{by}</code>")
        if total > 40:
            lines.append(f"... +{total - 40} more")
        await panel_edit(q, "\n".join(lines)[:4000], back_kb())
        return

    if action == "myjobs":
        nav_enter(context, "myjobs")
        try:
            cur = db.get().jobs.find({"admin_id": user.id}).sort("created_at", -1).limit(12)
            mine = await cur.to_list(12)
        except Exception:
            mine = []
        lines = [f"<blockquote><b>{sc('my jobs')}</b></blockquote>", ""]
        if not mine:
            lines.append(sc("no jobs yet"))
        for j in mine:
            lines.append(
                f"• ch{j.get('chapter_num')} · {j.get('status')} · "
                f"{(j.get('manga_title') or '')[:24]}"
            )
        await panel_edit(q, "\n".join(lines), back_kb())
        return

    if action == "broadcast" and is_admin:
        nav_enter(context, "broadcast")
        context.user_data["await"] = "broadcast"
        n = await db.count_users()
        await panel_edit(
            q,
            f"<blockquote><b>{sc('broadcast')}</b></blockquote>\n"
            f"{sc('users')}: <b>{n}</b>\n\n"
            f"{sc('send the message to broadcast now')}",
            back_kb(),
        )
        return

    if action == "stats" and is_owner:
        nav_enter(context, "stats")
        n = await db.count_users()
        text = (
            f"<blockquote><b>{sc('stats')}</b></blockquote>\n"
            f"<b>{sc('users')}:</b> {n}\n"
            f"<b>{sc('version')}:</b> {APP_VERSION}\n"
        )
        await panel_edit(q, text, back_kb())
        return

    if action == "setplan" and is_owner:
        nav_enter(context, "setplan")
        context.user_data["await"] = "setplan"
        await panel_edit(
            q,
            f"<blockquote><b>{sc('set plan')}</b></blockquote>\n"
            f"{sc('send')}: <code>user_id plan</code>\n"
            f"{sc('example')}: <code>123456 pro</code>\n"
            f"free · pro · ultra · max · flare",
            back_kb(),
        )
        return

    if action == "back":
        st = nav_stack(context)
        if len(st) > 1:
            st.pop()
        prev = st[-1] if st else "home"
        context.user_data["nav_stack"] = st
        context.user_data["_nav_restore"] = True
        # NEVER mutate CallbackQuery.data — route by key
        return await restore_panel(q, context, user, is_owner, prev)


    if action == "help":
        nav_enter(context, "help")
        text = (
            f"<blockquote><b>{sc('help')}</b></blockquote>\n"
            f"{sc('tap a command to learn / use')}"
        )
        rows = [
            [btn(sc("search"), "p:search", "success"), btn(sc("trending"), "p:trending", "primary")],
            [btn(sc("AI videos"), "p:aivideos", "primary"), btn(sc("premium"), "p:premium", "success")],
            [btn(sc("my channels"), "p:channels", "primary"), btn(sc("add channel"), "p:addch", "success")],
            [btn(sc("my jobs"), "p:myjobs", "primary"), btn(sc("queue"), "p:queue", "primary")],
            [btn(sc("howto"), "p:howto", "success"), btn(sc("profile"), "p:profile", "primary")],
            [btn(sc("bonus"), "p:bonus", "success"), btn(sc("ref"), "p:ref", "primary")],
            [btn(sc("random"), "p:random", "primary"), btn(sc("favs"), "p:favs", "primary")],
            [btn(sc("history"), "p:history", "primary"), btn(sc("top"), "p:top", "primary")],
            [btn(sc("report"), "p:report", "danger"), btn(sc("feedback"), "p:feedback", "primary")],
            [btn(sc("about"), "p:about", "primary"), btn(sc("support"), "p:support", "primary")],
            [btn(sc("id"), "p:id", "primary"), btn(sc("uptime"), "p:uptime", "primary")],
            [btn(sc("home"), "p:home", "danger")],
        ]
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return


    if action == "settings":
        nav_enter(context, "settings")
        caption = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        fn = await db.get_user_setting(user.id, "filename_template", FILENAME_TEMPLATE)
        plan_id = await db.get_user_plan_id(user.id)
        text = (
            f"<blockquote><b>{sc('settings')}</b></blockquote>\n"
            f"<b>{sc('caption tag')}:</b> <code>{caption}</code>\n"
            f"<b>{sc('filename')}:</b> <code>{fn[:40]}</code>\n"
            f"<b>{sc('plan')}:</b> {plan_id}"
        )
        rows = [
            [btn(sc("set caption"), "p:setcap", "primary"), btn(sc("set filename"), "p:setfile", "primary")],
            [btn(sc("premium"), "p:premium", "success"), btn(sc("profile"), "p:profile", "primary")],
            [btn(sc("my channels"), "p:channels", "primary"), btn(sc("add channel"), "p:addch", "success")],
            [btn(sc("home"), "p:home", "danger")],
        ]
        if is_owner:
            rows.insert(-1, [btn(sc("set plan"), "p:setplan", "danger"), btn(sc("stats"), "p:stats", "primary")])
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return


    if action == "setfile":
        nav_enter(context, "setfile")
        context.user_data["await"] = "filename"
        cur = await db.get_user_setting(user.id, "filename_template", FILENAME_TEMPLATE)
        await panel_edit(
            q,
            f"<b>{sc('file name template')}</b>\n\n"
            f"<b>{sc('params')}:</b>\n"
            f"<code>{{manga_title}}</code> — {sc('manga name')}\n"
            f"<code>{{chapter_num}}</code> — {sc('chapter number')}\n"
            f"<code>{{tag}}</code> — {sc('caption tag')}\n\n"
            f"<b>{sc('current')}:</b>\n<code>{cur}</code>\n\n"
            f"{sc('send new template now')}",
            back_kb(),
        )
        return

    if action == "setcap":
        nav_enter(context, "setcap")
        context.user_data["await"] = "caption"
        await panel_edit(q, f"{hdr('caption')}\n\n{sc('send new caption tag now')}\n{sc('example')}: {mono('@MyChannel')}", back_kb())
        return

    if action == "search":
        nav_enter(context, "search")
        context.user_data["await"] = "search"
        text = (
            f"{hdr('search')}\n\n"
            f"{sc('send manhwa or manga title now')}\n"
            f"{sc('then pick a source')}"
        )
        await panel_edit(q, text, back_kb())
        return

    if action == "trending":
        nav_enter(context, "trending")
        await panel_edit(q, f"{hdr('trending')}\n\n<b>{sc('loading')}...</b>", back_kb())
        await send_action(context, q.message.chat_id, ChatAction.TYPING)
        try:
            items = await multi_trending(12)
        except Exception as e:
            await db.add_log("error", f"trending: {e}", user.id)
            items = []
        if not items:
            await panel_edit(
                q,
                f"{hdr('trending')}\n\n<b>{sc('no results')}</b>\n{sc('try search instead')}",
                back_kb([btn(sc("search"), "p:search", "success")]),
            )
            return
        context.user_data["trend"] = items
        context.user_data["search_results"] = items
        smap = {str(i): it for i, it in enumerate(items)}
        context.user_data["search_map"] = smap
        lines = [f"{hdr('trending')}", f"<b>{sc('all sources')}</b>", ""]
        rows = []
        for i, r in enumerate(items[:24]):
            title = (r.get("title") or "?")[:28]
            src = r.get("source") or "?"
            lines.append(f"<b>{i+1}.</b> {title} · {src}")
            rows.append([btn(sc(f"{title[:22]} · {src}")[:58], f"p:msel:{i}", "primary")])
        await panel_edit(q, "\n".join(lines), back_kb(*rows))
        return


    if action == "aivideos" or action.startswith("aivp:"):
        page = 1
        if action.startswith("aivp:"):
            try:
                page = max(1, int(action.split(":")[-1]))
            except Exception:
                page = 1
        await _show_ai_videos(q, context, page)
        return

    if action.startswith("aiv:"):
        # select video by index on current page cache
        try:
            idx = int(action.split(":")[-1])
        except Exception:
            await q.answer(sc("invalid"), show_alert=True)
            return
        items = context.user_data.get("ai_videos") or []
        if idx < 0 or idx >= len(items):
            await panel_edit(q, sc("session expired — use /aivid again"), back_kb())
            return
        item = items[idx]
        slug = item.get("slug") or ""
        await panel_edit(q, f"<blockquote><b>{sc('downloading video')}...</b></blockquote>\n<code>{item.get('title','')}</code>", back_kb())
        await _download_ai_video(q, context, slug, item)
        return

    if action.startswith("aivep:"):
        slug = action.split(":", 1)[-1]
        context.user_data["_aiv_force"] = True
        await panel_edit(q, f"<blockquote><b>{sc('downloading video')}...</b></blockquote>", back_kb())
        await _download_ai_video(q, context, slug, {"slug": slug, "title": slug})
        context.user_data.pop("_aiv_force", None)
        return

    if action.startswith("aivshots:"):
        nav_enter(context, "aivshots")
        slug = action.split(":", 1)[-1]
        await _send_screenshots(q, context, slug)
        return


    if action == "pending":
        nav_enter(context, "pending")
        active = await db.list_active_jobs(30)
        done = await db.get().jobs.find({"status": "done"}).sort("updated_at", -1).to_list(5)
        failed = await db.get().jobs.find({"status": "failed"}).sort("updated_at", -1).to_list(5)
        lines = [f"{hdr('tasks')}", ""]
        running = [j for j in active if j.get("status") == "running"]
        pending = [j for j in active if j.get("status") == "pending"]
        lines.append(f"{bsc('running')} ({len(running)})")
        cancel_rows = []
        for j in running[:8]:
            title = (j.get("manga_title") or "?")[:18]
            chn = j.get("chapter_num")
            lines.append(f"  • {title} ch{chn}")
            jk = j.get("job_key", "")
            if jk:
                cancel_rows.append([
                    btn(sc(f"cancel · {title[:12]} ch{chn}"), f"p:jcancel:{jk[-16:]}", "danger")
                ])
        lines.append(f"\n{bsc('pending')} ({len(pending)})")
        for j in pending[:10]:
            title = (j.get("manga_title") or "?")[:18]
            chn = j.get("chapter_num")
            lines.append(f"  • {title} ch{chn}")
            jk = j.get("job_key", "")
            if jk and len(cancel_rows) < 8:
                cancel_rows.append([
                    btn(sc(f"cancel · {title[:12]} ch{chn}"), f"p:jcancel:{jk[-16:]}", "danger")
                ])
        lines.append(f"\n{bsc('recent done')}")
        for j in done:
            lines.append(f"  [ok] {j.get('manga_title','?')[:22]} ch{j.get('chapter_num')}")
        lines.append(f"\n{bsc('recent failed')}")
        for j in failed:
            err = (j.get("error") or "")[:36]
            lines.append(f"  [x] {j.get('manga_title','?')[:18]} — {err}")
        text = "\n".join(lines)
        if len(text) > 1000:
            text = text[:1000] + "…"
        extra = cancel_rows[:6]
        extra.append([
            btn(sc("refresh"), "p:pending", "primary"),
            btn(sc("cancel all"), "p:cancelall", "danger"),
        ])
        await panel_edit(q, text, back_kb(*extra))
        return

    if action == "cancelall":
        res = await db.get().jobs.update_many(
            {"status": "pending"},
            {"$set": {"cancel_requested": True, "status": "cancelled", "updated_at": db.utcnow()}},
        )
        n = res.modified_count
        await q.answer(sc(f"cancelled {n} pending"), show_alert=True)
        active = await db.list_active_jobs(20)
        lines = [f"{hdr('pending')}", "", sc(f"cancelled {n} jobs"), ""]
        running = [j for j in active if j.get("status") == "running"]
        pending = [j for j in active if j.get("status") == "pending"]
        lines.append(f"{bsc('running')} ({len(running)})")
        for j in running[:6]:
            lines.append(f"  • {j.get('manga_title','?')[:22]} ch{j.get('chapter_num')}")
        lines.append(f"\n{bsc('pending')} ({len(pending)})")
        for j in pending[:8]:
            lines.append(f"  • {j.get('manga_title','?')[:22]} ch{j.get('chapter_num')}")
        await panel_edit(q, "\n".join(lines), back_kb([btn(sc("refresh"), "p:pending", "primary")]))
        return

    if action.startswith("jcancel:"):
        suffix = action.split(":", 1)[-1]
        active = await db.list_active_jobs(50)
        doc = next((j for j in active if (j.get("job_key") or "").endswith(suffix)), None)
        if not doc:
            await q.answer(sc("job not found"), show_alert=True)
            return
        ok = await db.request_cancel(doc["job_key"])
        if doc.get("status") == "pending":
            await db.update_job(doc["job_key"], status="cancelled", error="cancelled by admin")
        await q.answer(sc("cancel requested" if ok else "already done"), show_alert=True)
        await panel_edit(
            q,
            f"{hdr('pending')}\n\n{sc('cancel requested')}\n<code>{doc.get('manga_title','')}</code> ch{doc.get('chapter_num')}",
            back_kb([btn(sc("refresh"), "p:pending", "primary")]),
        )
        return

    if action == "logs":
        nav_enter(context, "logs")
        logs = await db.get_logs(20)
        lines = [f"{hdr('logs')}", ""]
        if not logs:
            lines.append(sc("no logs yet"))
        else:
            for lg in logs:
                ts = lg.get("created_at")
                tstr = ts.strftime("%m-%d %H:%M") if isinstance(ts, datetime) else "?"
                level = (lg.get("level") or "info")[:4].upper()
                msg = (lg.get("message") or "")[:70]
                lines.append(f"{mono(tstr)} [{level}] {msg}")
        lines.append(ftr())
        text = "\n".join(lines)
        if len(text) > 1000:
            text = text[:1000] + "…"
        await panel_edit(q, text, back_kb([btn(sc("refresh"), "p:logs", "primary")]))
        return

    if action == "sources":
        await show_sources_panel(q, context)
        return

    if action.startswith("srcheck:"):
        await panel_edit(
            q,
            f"{hdr('sources')}\n\n{sc('single source only')}\n{mono('https://manhwa18.net')}",
            back_kb(),
        )
        return

    if action == "pip":
        nav_enter(context, "pip")
        if not is_owner:
            await q.answer(sc("owner only"), show_alert=True)
            return
        context.user_data["await"] = "pip"
        await panel_edit(q, f"{hdr('pip')}\n\n{sc('send package name now')}\n{sc('example')}: {mono('httpx')}", back_kb())
        return

    if action == "update":
        nav_enter(context, "update")
        if not is_owner:
            await q.answer(sc("owner only"), show_alert=True)
            return
        await panel_edit(q, f"{hdr('update')}\n\n{sc('updating from upstream')}...", back_kb())
        try:
            git_dir = os.path.join(BASE_DIR, ".git")
            if os.path.isdir(git_dir):
                proc = await asyncio.create_subprocess_exec(
                    "git", "pull", "--ff-only", "origin", "main",
                    cwd=BASE_DIR, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, err = await proc.communicate()
                raw = ((out or b"") + (err or b"")).decode()[:1200]
                if proc.returncode == 0:
                    await db.add_log("info", f"update ok: {raw[:200]}", user.id)
                    await panel_edit(q, f"{hdr('update')}\n\n<b>{sc('bot update successful')}</b>\n<pre>{raw}</pre>\n{sc('restart to apply')}", back_kb())
                else:
                    await db.add_log("error", f"update fail: {raw[:300]}", user.id)
                    await panel_edit(q, f"{hdr('update error')}\n\n<pre>{raw}</pre>", back_kb())
            else:
                tmp = os.path.join(BASE_DIR, "tmp_update")
                proc = await asyncio.create_subprocess_exec(
                    "git", "clone", "--depth", "1", UPSTREAM_REPO, tmp,
                    stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
                )
                out, err = await proc.communicate()
                raw = ((out or b"") + (err or b"")).decode()[:800]
                if proc.returncode == 0:
                    import shutil
                    for root, dirs, files in os.walk(tmp):
                        for f in files:
                            if f.endswith((".py", ".txt", ".json", "Procfile", "runtime.txt", ".yaml", ".yml", ".md")):
                                src = os.path.join(root, f)
                                rel = os.path.relpath(src, tmp)
                                dst = os.path.join(BASE_DIR, rel)
                                os.makedirs(os.path.dirname(dst) or BASE_DIR, exist_ok=True)
                                shutil.copy2(src, dst)
                    shutil.rmtree(tmp, ignore_errors=True)
                    await db.add_log("info", "update via clone ok", user.id)
                    await panel_edit(q, f"{hdr('update')}\n\n<b>{sc('bot update successful')}</b>\n{sc('files synced')}\n{sc('restart to apply')}", back_kb())
                else:
                    await db.add_log("error", f"clone fail: {raw[:300]}", user.id)
                    await panel_edit(q, f"{hdr('update error')}\n\n<pre>{raw}</pre>", back_kb())
        except Exception as e:
            await db.add_log("error", str(e), user.id)
            await panel_edit(q, f"{hdr('update error')}\n\n{mono(str(e))}", back_kb())
        return

    # ── search results / manhwa select / chapter / upload ──

    if action.startswith("spage:"):
        try:
            page = int(action.split(":")[-1])
        except Exception:
            page = 1
        query = context.user_data.get("search_q") or ""
        results = context.user_data.get("search_results") or []
        source_id = context.user_data.get("search_source") or "all"
        if results:
            await _render_search_results(q, context, query, results, source_id, page=page)
            return
        if not query:
            await panel_edit(q, f"{sc('session expired')}\n{sc('search again')}", back_kb())
            return
        await _show_search(q, context, query, page)
        return

    if action.startswith("srcpick:"):
        sid = action.split(":", 1)[-1]
        query = context.user_data.get("search_q") or ""
        if not query:
            await panel_edit(q, f"{sc('session expired')}\n{sc('search again')}", back_kb())
            return
        await panel_edit(q, f"<b>{sc('searching')}...</b>\n<code>{query}</code>\n{sc('source')}: {sid}", back_kb())
        await _show_search(q, context, query, page=1, source_id=sid)
        return

    if action == "srcagain":
        query = context.user_data.get("search_q") or ""
        if not query:
            await panel_edit(q, f"{sc('session expired')}\n{sc('search again')}", back_kb())
            return
        await _show_source_picker(q, context, query)
        return

    if action.startswith("msel:"):
        # p:msel:{index} from search results
        nav_enter(context, "sel")
        idx_s = action.split(":", 1)[-1]
        results = context.user_data.get("search_results") or []
        smap = context.user_data.get("search_map") or {}
        hit = smap.get(idx_s)
        if hit is None:
            try:
                hit = results[int(idx_s)]
            except Exception:
                hit = None
        if not hit:
            await panel_edit(q, f"<b>{sc('session expired')}</b>\n{sc('search again')}", back_kb())
            return
        await panel_edit(q, f"<b>{sc('loading')}...</b>\n{hit.get('title','')}\n{sc('source')}: {hit.get('source','')}", back_kb())
        await send_action(context, q.message.chat_id)
        detail = await get_detail_any(hit.get("url") or "", hit.get("source") or hit.get("source_id") or "")
        if not detail:
            await panel_edit(q, f"<b>{sc('failed to load')}</b>\n{hit.get('title','')}\n{hit.get('source','')}", back_kb())
            return
        slug = detail.get("slug") or hit.get("slug") or ""
        await db.cache_manhwa(slug, {
            "title": detail["title"],
            "poster": detail.get("poster", ""),
            "url": detail.get("url", ""),
            "source": detail.get("source", ""),
        })
        context.user_data["sel"] = detail
        tpl = await db.get_setting("template_manhwa", "classic")
        cap = build_caption(detail, "manhwa", tpl)
        if len(cap) > 900:
            cap = cap[:900] + "…"
        src_tag = detail.get("source") or hit.get("source") or ""
        rows = [
            [btn(sc("fetch chapters"), f"p:fetch:{slug[:40]}", "success")],
            [
                btn(sc("classic"), f"p:tpl:classic:{slug[:30]}", "primary"),
                btn(sc("compact"), f"p:tpl:compact:{slug[:30]}", "primary"),
            ],
        ]
        text = f"<b>{sc('manhwa')}</b> · {src_tag}\n\n{cap}"
        await panel_poster(q, context, detail.get("poster") or "", text, back_kb(*rows))
        return

    if action.startswith("sel:"):
        nav_enter(context, data)
        slug = action.split(":", 1)[-1]
        await panel_edit(q, f"<b>{sc('loading')}...</b>", back_kb())
        await send_action(context, q.message.chat_id)
        detail = await get_detail(slug)
        if not detail:
            await panel_edit(q, f"<b>{sc('failed to load')}</b> {slug}", back_kb())
            return
        await db.cache_manhwa(slug, {
            "title": detail["title"],
            "poster": detail.get("poster", ""),
            "url": detail.get("url", ""),
        })
        context.user_data["sel"] = detail
        tpl = await db.get_setting("template_manhwa", "classic")
        cap = build_caption(detail, "manhwa", tpl)
        if len(cap) > 900:
            cap = cap[:900] + "…"
        rows = [
            [btn(sc("fetch chapters"), f"p:fetch:{slug}", "success")],
            [
                btn(sc("classic"), f"p:tpl:classic:{slug}", "primary"),
                btn(sc("compact"), f"p:tpl:compact:{slug}", "primary"),
            ],
            [
                btn(sc("story"), f"p:tpl:story:{slug}", "primary"),
                btn(sc("minimal"), f"p:tpl:minimal:{slug}", "primary"),
                btn(sc("rich"), f"p:tpl:rich:{slug}", "primary"),
            ],
        ]
        text = f"<b>{sc('manhwa')}</b>\n\n{cap}"
        await panel_poster(q, context, detail.get("poster") or "", text, back_kb(*rows))
        return

    if action.startswith("tpl:"):
        nav_enter(context, data)
        parts = action.split(":")
        if len(parts) < 3:
            return
        tpl, slug = parts[1], parts[2]
        await db.set_setting("template_manhwa", tpl)
        detail = context.user_data.get("sel")
        if not detail or detail.get("slug") != slug:
            detail = await get_detail(slug)
            if not detail:
                await panel_edit(q, f"<b>{sc('failed')}</b>", back_kb())
                return
            context.user_data["sel"] = detail
        cap = build_caption(detail, "manhwa", tpl)
        if len(cap) > 900:
            cap = cap[:900] + "…"
        rows = [
            [btn(sc("fetch chapters"), f"p:fetch:{slug}", "success")],
            [
                btn(sc("classic"), f"p:tpl:classic:{slug}", "primary"),
                btn(sc("compact"), f"p:tpl:compact:{slug}", "primary"),
            ],
            [
                btn(sc("story"), f"p:tpl:story:{slug}", "primary"),
                btn(sc("minimal"), f"p:tpl:minimal:{slug}", "primary"),
                btn(sc("rich"), f"p:tpl:rich:{slug}", "primary"),
            ],
        ]
        text = f"<b>{sc('manhwa')}</b>\n\n{cap}"
        await panel_poster(q, context, detail.get("poster") or "", text, back_kb(*rows))
        return

    if action.startswith("fetch:"):
        nav_enter(context, "chapters")
        slug = action.split(":", 1)[-1]
        detail = context.user_data.get("sel")
        if not detail:
            await panel_edit(q, f"<b>{sc('session expired')}</b>\n{sc('search again')}", back_kb())
            return
        # refresh chapters if empty
        if not detail.get("chapters") and detail.get("url"):
            d2 = await get_detail_any(detail["url"], detail.get("source") or "")
            if d2:
                detail = d2
                context.user_data["sel"] = detail
        chapters = detail.get("chapters", [])
        rows, _, _, total = chapter_rows(slug, chapters, 0, 20, latest_first=True)
        text = (
            f"<b>{sc('select chapter')}</b> · {sc('latest')}\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{sc('chapters')}:</b> {total}"
        )
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return


    if action == "channels":
        nav_enter(context, "channels")
        channels = await db.get_channels(admin_only=False, owner_id=None if is_owner else user.id)
        lines = [
            f"<blockquote><b>{sc('my channels')}</b></blockquote>",
            f"<b>{sc('total')}:</b> {len(channels)}",
            "",
        ]
        if not channels:
            lines.append(sc("no channels yet — add one"))
        for c in channels[:30]:
            title = c.get("title") or c.get("chat_id")
            lines.append(f"• {title}")
            lines.append(f"  <code>{c.get('chat_id')}</code>")
        rows = [[btn(sc("add channel"), "p:addch", "success")]]
        if is_owner:
            rows.append([btn(sc("all channels"), "p:allchannels", "primary")])
        await panel_edit(q, "\n".join(lines)[:4000], back_kb(*rows))
        return

    if action == "addch":
        nav_enter(context, "addch")
        context.user_data["await"] = "addch"
        await panel_edit(
            q,
            f"<b>{sc('add channel')}</b>\n\n"
            f"{sc('send')}: <code>/addch -100xxxxxxxxxx</code>\n"
            f"{sc('or send chat id now')}\n"
            f"{sc('bot must be admin in that channel')}",
            back_kb(),
        )
        return

    if action.startswith("chmore:"):
        nav_enter(context, "chapters")
        parts = action.split(":")
        slug, offset = parts[1], int(parts[2])
        detail = context.user_data.get("sel") or await get_detail(slug)
        if not detail:
            await panel_edit(q, f"<b>{sc('failed')}</b>", back_kb())
            return
        context.user_data["sel"] = detail
        chapters = detail.get("chapters", [])
        rows, _, _, total = chapter_rows(slug, chapters, offset, 20, latest_first=True)
        text = (
            f"<b>{sc('select chapter')}</b>\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{sc('chapters')}:</b> {total} · <b>{sc('showing')}:</b> {offset+1}-{min(offset+20, total)}"
        )
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return

    if action.startswith("chfirst:"):
        nav_enter(context, "chapters")
        detail = context.user_data.get("sel")
        if not detail:
            await panel_edit(q, sc("session expired"), back_kb())
            return
        chapters = detail.get("chapters") or []
        slug = detail.get("slug") or action.split(":")[-1]
        rows, _, _, total = chapter_rows(slug, chapters, 0, 20, latest_first=False)
        text = (
            f"<b>{sc('select chapter')}</b> · {sc('first')}\n"
            f"<b>{detail.get('title')}</b>\n"
            f"<b>{sc('chapters')}:</b> {total}"
        )
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return

    if action.startswith("chnew:"):
        nav_enter(context, "chapters")
        detail = context.user_data.get("sel")
        if not detail:
            await panel_edit(q, sc("session expired"), back_kb())
            return
        chapters = detail.get("chapters") or []
        slug = detail.get("slug") or action.split(":")[-1]
        # latest first — page 0 = highest chapter numbers
        rows, _, _, total = chapter_rows(slug, chapters, 0, 20, latest_first=True)
        text = (
            f"<b>{sc('select chapter')}</b> · {sc('new')}\n"
            f"<b>{detail.get('title')}</b>\n"
            f"<b>{sc('chapters')}:</b> {total} · {sc('latest')}"
        )
        await panel_edit(q, text, InlineKeyboardMarkup(rows))
        return

    if action.startswith("chsearch:"):
        nav_enter(context, "chapters")
        context.user_data["await"] = "chapter_jump"
        detail = context.user_data.get("sel")
        title = (detail or {}).get("title") or ""
        await panel_edit(
            q,
            f"<blockquote><b>{sc('chapter search')}</b></blockquote>\n"
            f"<b>{title}</b>\n\n"
            f"{sc('send chapter number now')}\n"
            f"{sc('example')}: <code>40</code> · <code>1</code> · <code>12.5</code>",
            back_kb(),
        )
        return

    if action.startswith("ci:") or action.startswith("ch:"):
        # ci:{short_slug}:{index}  or legacy ch:{slug}:{num}
        nav_enter(context, "channel")
        parts = action.split(":")
        detail = context.user_data.get("sel")
        ch = None
        ch_num = "?"
        slug = ""
        if action.startswith("ci:") and len(parts) >= 3:
            slug = parts[1]
            try:
                idx = int(parts[2])
            except ValueError:
                idx = -1
            if not detail:
                await panel_edit(q, sc("session expired — search again"), back_kb())
                return
            chapters = detail.get("chapters") or []
            # buttons use latest-first display indices
            display = list(reversed(chapters))
            if 0 <= idx < len(display):
                ch = display[idx]
                ch_num = str(ch.get("num", idx + 1))
            else:
                await panel_edit(q, sc("chapter not found"), back_kb())
                return
            context.user_data["sel_ch"] = ch
            context.user_data["sel_ch_idx"] = idx
        else:
            if len(parts) < 3:
                return
            slug, ch_num = parts[1], parts[2]
            if not detail:
                detail = await get_detail(slug)
            if not detail:
                await panel_edit(q, sc("failed"), back_kb())
                return
            context.user_data["sel"] = detail
            for c in detail.get("chapters", []):
                if str(c.get("num")) == str(ch_num) or str(ch_num) in str(c.get("title", "")):
                    ch = c
                    break
            if not ch:
                await panel_edit(q, sc("chapter not found"), back_kb())
                return
        context.user_data["sel_ch"] = ch
        channels = await db.get_channels(admin_only=False, owner_id=None if is_owner else user.id)
        lines = [
            f"<b>{sc('select channel')}</b>",
            f"<b>{detail['title']}</b>",
            f"<b>{sc('chapter')}:</b> {ch_num}",
            "",
            f"<b>{sc('all admins can post to any channel')}</b>",
        ]
        rows = []
        ss = _short_slug(slug or detail.get("slug") or "")
        if not channels:
            lines.append(f"\n<b>{sc('no channels')}</b>")
            lines.append(sc("add bot as admin or use add channel"))
        else:
            for c in channels:
                title = (c.get("title") or c["chat_id"])[:28]
                # short: p:up2:{chat_id}  — chapter from user_data
                rows.append([btn(sc(title), f"p:up2:{c['chat_id']}", "success")])
        rows.append([
            btn(sc("add channel"), "p:addch", "success"),
            btn(sc("auto fetch"), "p:autofetch", "primary"),
        ])
        await panel_edit(q, "\n".join(lines), back_kb(*rows))
        return

    if action.startswith("up2:"):
        # Short upload path: chapter taken from user_data (sel_ch / sel_ch_idx)
        nav_enter(context, "channel")
        chat_id = action.split(":", 1)[-1]
        detail = context.user_data.get("sel")
        ch = context.user_data.get("sel_ch")
        if not detail or not ch:
            await panel_edit(q, sc("session expired — select chapter again"), back_kb())
            return
        ch_num = str(ch.get("num", "?"))
        slug = detail.get("slug") or ""
        recent = await db.count_recent(user.id, 60)
        if recent >= UPLOAD_RATE:
            await panel_edit(q, f"{sc('rate limit')} — max {UPLOAD_RATE}/min", back_kb())
            return
        ok_q, used_q, lim_q = await db.check_daily_quota(user.id, plan_id, need=1)
        if not ok_q and not is_admin:
            await panel_edit(
                q,
                f"<b>{sc('daily limit')}</b> {used_q}/{lim_q}\n{sc('upgrade via premium')}",
                back_kb([btn(sc("premium"), "p:premium", "success")]),
            )
            return
        tag = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        import html as _html
        _ch = str(ch_num).replace("_", " ").strip()
        _title = detail["title"].replace("_", " ").strip()
        _plain = f"{_ch} ⌯ {_title}"
        if tag:
            _plain += f" [{tag}]"
        caption = f"<blockquote><b>{_html.escape(_plain)}</b></blockquote>"
        channel = await db.get_channel(chat_id)
        key = await db.create_job({
            "admin_id": user.id,
            "manga_title": detail["title"].replace("_", " ").strip(),
            "chapter_num": ch_num,
            "slug": slug,
            "poster": detail.get("poster", ""),
            "chat_id": chat_id,
            "channel_title": (channel or {}).get("title", chat_id),
            "caption": caption,
            "chapter_url": ch.get("url", ""),
            "synopsis": detail.get("synopsis", ""),
            "score": detail.get("score", ""),
            "genres": detail.get("genres") or [],
            "status_text": detail.get("status", ""),
            "post_poster": True,
            "source": detail.get("source", ""),
            "kind": detail.get("kind") or "Manhwa",
            "chapters_count": detail.get("chapters_count") or len(detail.get("chapters") or []),
        })
        await db.add_log("info", f"queued {key} — {detail['title']} ch{ch_num}", user.id)
        try:
            await react_ok(context, q.message.chat_id, q.message.message_id)
        except Exception:
            pass
        status_text = (
            f"<blockquote><b>{sc('queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{sc('chapter')}:</b> {ch_num}\n"
            f"<b>{sc('channel')}:</b> {(channel or {}).get('title', chat_id)}\n"
            f"<b>{sc('job')}:</b> {mono(key[-12:])}\n\n"
            f"{sc('worker will upload with live progress')}"
        )
        try:
            sm = await context.bot.send_message(q.message.chat_id, status_text, parse_mode="HTML")
            await db.update_job(key, status_chat_id=q.message.chat_id, status_message_id=sm.message_id)
        except Exception:
            pass
        await panel_edit(
            q,
            f"<blockquote><b>{sc('queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b> · ch {ch_num}\n"
            f"{sc('live progress in next message')}",
            back_kb([btn(sc("pending"), "p:pending", "primary")]),
        )
        return

    if action.startswith("up:"):
        nav_enter(context, data)
        parts = action.split(":")
        if len(parts) < 4:
            return
        slug, ch_num, chat_id = parts[1], parts[2], parts[3]
        detail = context.user_data.get("sel") or await get_detail(slug)
        if not detail:
            await panel_edit(q, sc("failed"), back_kb())
            return
        ch = None
        for c in detail.get("chapters", []):
            if str(c.get("num")) == str(ch_num):
                ch = c
                break
        if not ch:
            await panel_edit(q, sc("chapter not found"), back_kb())
            return
        recent = await db.count_recent(user.id, 60)
        if recent >= UPLOAD_RATE:
            await panel_edit(q, f"{sc('rate limit')} — max {UPLOAD_RATE}/min", back_kb())
            return
        ok_q, used_q, lim_q = await db.check_daily_quota(user.id, plan_id, need=1)
        if not ok_q and not is_admin:
            await panel_edit(
                q,
                f"<b>{sc('daily limit')}</b> {used_q}/{lim_q}\n{sc('upgrade via premium')}",
                back_kb([btn(sc("premium"), "p:premium", "success")]),
            )
            return
        tag = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        # PHP-style: <blockquote><b>{ch} ⌯ {title} [{tag}]</b></blockquote>
        import html as _html
        _ch = str(ch_num).replace("_", " ").strip()
        _title = detail["title"].replace("_", " ").strip()
        _plain = f"{_ch} ⌯ {_title}"
        if tag:
            _plain += f" [{tag}]"
        caption = f"<blockquote><b>{_html.escape(_plain)}</b></blockquote>"
        channel = await db.get_channel(chat_id)
        key = await db.create_job({
            "admin_id": user.id,
            "manga_title": detail["title"].replace("_", " ").strip(),
            "chapter_num": ch_num,
            "slug": slug,
            "poster": detail.get("poster", ""),
            "chat_id": chat_id,
            "channel_title": (channel or {}).get("title", chat_id),
            "caption": caption,
            "chapter_url": ch.get("url", ""),
            "synopsis": detail.get("synopsis", ""),
            "score": detail.get("score", ""),
            "genres": detail.get("genres") or [],
            "status_text": detail.get("status", ""),
            "post_poster": False,
            "source": detail.get("source", ""),
        })
        await db.add_log("info", f"queued {key} — {detail['title']} ch{ch_num}", user.id)
        try:
            await react_ok(context, q.message.chat_id, q.message.message_id)
        except Exception:
            pass
        # status message that worker will live-edit
        status_text = (
            f"<blockquote><b>{sc('queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{sc('chapter')}:</b> {ch_num}\n"
            f"<b>{sc('channel')}:</b> {(channel or {}).get('title', chat_id)}\n"
            f"<b>{sc('job')}:</b> {mono(key)}\n\n"
            f"<b>{sc('progress')}:</b> 0%\n"
            f"{sc('worker will process shortly')}"
        )
        try:
            sm = await context.bot.send_message(
                chat_id=q.message.chat_id,
                text=status_text,
                parse_mode="HTML",
            )
            await db.update_job(key, status_chat_id=q.message.chat_id, status_message_id=sm.message_id)
        except Exception:
            await panel_edit(q, status_text, back_kb())
            return
        await panel_edit(
            q,
            f"<blockquote><b>{sc('queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b> · ch {ch_num}\n"
            f"{sc('live progress in next message')}",
            back_kb(),
        )
        return



    if action == "autofetch":
        nav_enter(context, "autofetch")
        channels = await db.get_channels(admin_only=False, owner_id=None if is_owner else user.id)
        lines = [
            f"<b>{sc('auto fetch')}</b>",
            f"<b>{sc('channels')}:</b> {len(channels)}",
            "",
            sc("tap a channel to use it for current manhwa"),
            sc("or add channel if empty"),
        ]
        rows = []
        detail = context.user_data.get("sel")
        ch = context.user_data.get("sel_ch")
        for c in channels[:30]:
            mark = "[ok]" if c.get("is_bot_admin") else "[--]"
            title = (c.get("title") or c["chat_id"])[:28]
            lines.append(f"{mark} <b>{title}</b>")
            cid = str(c["chat_id"])
            if detail and ch:
                slug = detail.get("slug", "")
                ch_num = str(ch.get("num", ""))
                rows.append([btn(f"{sc(title)}", f"p:up:{slug}:{ch_num}:{cid}", "success")])
            elif detail:
                # full series ready
                slug = detail.get("slug", "")
                rows.append([btn(f"{sc(title)}", f"p:upfull:{slug}:{cid}", "success")])
            else:
                rows.append([btn(sc(title), f"p:chinfo:{cid}", "primary")])
        rows.append([btn(sc("add channel"), "p:addch", "success"), btn(sc("refresh"), "p:autofetch", "primary")])
        await panel_edit(q, "\n".join(lines), back_kb(*rows))
        return

    
    if action.startswith("full:"):
        nav_enter(context, data)
        # choose channel for full series
        slug = action.split(":", 1)[-1]
        detail = context.user_data.get("sel") or await get_detail(slug)
        if not detail:
            await panel_edit(q, f"<b>{sc('failed')}</b>", back_kb())
            return
        context.user_data["sel"] = detail
        channels = await db.get_channels(admin_only=False, owner_id=None if is_owner else user.id)
        lines = [
            f"<b>{sc('add full series')}</b>",
            f"<b>{detail['title']}</b>",
            f"<b>{sc('chapters')}:</b> {len(detail.get('chapters') or [])}",
            "",
            sc("poster will post first then all chapters in order"),
        ]
        rows = []
        for c in channels:
            title = (c.get("title") or c["chat_id"])[:28]
            rows.append([btn(sc(title), f"p:upfull:{slug}:{c['chat_id']}", "success")])
        rows.append([
            btn(sc("add channel"), "p:addch", "success"),
            btn(sc("auto fetch"), "p:autofetch", "primary"),
        ])
        await panel_edit(q, "\n".join(lines), back_kb(*rows))
        return

    if action.startswith("upfull:"):
        nav_enter(context, data)
        parts = action.split(":")
        if len(parts) < 3:
            return
        slug, chat_id = parts[1], parts[2]
        detail = context.user_data.get("sel") or await get_detail(slug)
        if not detail:
            await panel_edit(q, f"<b>{sc('failed')}</b>", back_kb())
            return
        chapters = list(detail.get("chapters") or [])
        # ALWAYS oldest → newest (ch1, ch2, ch3...) for full series
        def _ch_key(c):
            import re
            n = str(c.get("num") or c.get("title") or c.get("slug") or "0")
            m = re.search(r"(\d+(?:\.\d+)?)", n)
            return float(m.group(1)) if m else 0.0
        chapters = sorted(chapters, key=_ch_key)
        if not chapters:
            await panel_edit(q, f"<b>{sc('no chapters')}</b>", back_kb())
            return
        # Premium: bulk only for plans that allow it
        if not can_bulk(plan_id) and not is_admin:
            await panel_edit(
                q,
                f"<blockquote><b>{sc('premium required')}</b></blockquote>\n"
                f"{sc('full series bulk needs Ultra / Max / Flare')}\n"
                f"{sc('free & pro = one chapter at a time')}\n\n"
                f"{sc('tap premium to see plans')}",
                back_kb([btn(sc("premium"), "p:premium", "success")]),
            )
            return
        bmax = bulk_max(plan_id)
        if not is_admin and bmax and len(chapters) > bmax:
            chapters = chapters[:bmax]
        # daily quota
        ok, used, limit = await db.check_daily_quota(user.id, plan_id, need=len(chapters))
        if not ok and not is_admin:
            await panel_edit(
                q,
                f"<blockquote><b>{sc('daily limit')}</b></blockquote>\n"
                f"{sc('used')}: {used}/{limit}\n"
                f"{sc('upgrade plan for more')}",
                back_kb([btn(sc("premium"), "p:premium", "success")]),
            )
            return
        tag = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        try:
            tag = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        except Exception:
            pass
        import html as _html
        channel = await db.get_channel(chat_id)
        bulk_id = f"bulk_{user.id}_{int(__import__('time').time())}"
        total = len(chapters)
        keys = []
        for i, ch in enumerate(chapters):
            ch_num = str(ch.get("num", i + 1))
            _plain = f"{ch_num} ⌯ {detail['title']}"
            if tag:
                _plain += f" [{tag}]"
            caption = f"<blockquote><b>{_html.escape(_plain)}</b></blockquote>"
            key = await db.create_job({
                "admin_id": user.id,
                "manga_title": detail["title"].replace("_", " ").strip(),
                "chapter_num": ch_num,
                "slug": slug,
                "poster": detail.get("poster", ""),
                "chat_id": chat_id,
                "channel_title": (channel or {}).get("title", chat_id),
                "caption": caption,
                "chapter_url": ch.get("url", ""),
                "synopsis": detail.get("synopsis", ""),
                "score": detail.get("score", ""),
                "genres": detail.get("genres") or [],
                "status_text": detail.get("status", ""),
                "post_poster": (i == 0),
                "source": detail.get("source", ""),
                "kind": detail.get("kind") or "Manhwa",
                "chapters_count": total,
                "bulk_id": bulk_id,
                "bulk_index": i + 1,
                "bulk_total": total,
            })
            keys.append(key)
        status_text = (
            f"<blockquote><b>{sc('full series queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{sc('chapters')}:</b> {total}\n"
            f"<b>{sc('channel')}:</b> {(channel or {}).get('title', chat_id)}\n"
            f"<b>{sc('batch')}:</b> {mono(bulk_id)}\n\n"
            f"<b>{sc('progress')}:</b> 0/{total}\n"
            f"{sc('uploads one chapter at a time — ch1 then ch2...')}"
        )
        try:
            sm = await context.bot.send_message(q.message.chat_id, status_text, parse_mode="HTML")
            # attach status msg to first job
            if keys:
                await db.update_job(keys[0], status_chat_id=q.message.chat_id, status_message_id=sm.message_id)
        except Exception:
            pass
        await panel_edit(
            q,
            f"<blockquote><b>{sc('full series queued')}</b></blockquote>\n"
            f"<b>{detail['title']}</b>\n"
            f"<b>{total}</b> {sc('chapters queued')}\n"
            f"{sc('one by one — time laga sakta hai lekin sab upload hoga')}\n"
            f"{sc('live progress in next message')}",
            back_kb(),
        )
        return


