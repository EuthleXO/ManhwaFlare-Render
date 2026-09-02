# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Panel open / restore helpers."""
from __future__ import annotations
import logging

from telegram import InlineKeyboardMarkup
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.config import APP_VERSION, CAPTION_TAG, SCRAPE_HOST, FILENAME_TEMPLATE, UPSTREAM_REPO
from Manhwaflare.nav import nav_enter, nav_reset, _norm_panel_key
from Manhwaflare.helpers import chapter_rows
from Manhwaflare.scrapers import SOURCES, multi_trending
from Manhwaflare.scraper import trending as fetch_trending
from Manhwaflare.text import sc, mono, hdr
from Manhwaflare.ui.home import start_caption, main_kb
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit, panel_home

log = logging.getLogger("mf.panels")

async def restore_panel(q, context, user, is_owner: bool, key: str) -> None:
    """Navigate back to previous panel. Uses short panel ids only."""
    key = _norm_panel_key(key or "home")
    context.user_data["_nav_restore"] = True

    if key in ("home", ""):
        nav_reset(context)
        await panel_home(q, context, start_caption(user, is_owner), main_kb(is_owner))
        return

    # Search prompt (type a query)
    if key == "search":
        context.user_data["await"] = "search"
        await panel_edit(
            q,
            f"{hdr('search')}\n\n"
            f"{sc('send manhwa or manga title now')}\n"
            f"{sc('then pick a source')}",
            back_kb(),
        )
        return

    # Source picker for last query
    if key == "srcpick":
        query = context.user_data.get("search_q") or ""
        if query:
            await _show_source_picker(q, context, query)
        else:
            context.user_data["await"] = "search"
            await panel_edit(q, f"{hdr('search')}\n\n{sc('send manhwa or manga title now')}", back_kb())
        return

    # Cached search results (do NOT re-hit network)
    if key == "results":
        query = context.user_data.get("search_q") or ""
        results = context.user_data.get("search_results")
        if query and results is not None:
            await _render_search_results(q, context, query, results, context.user_data.get("search_source") or "all")
            return
        if query:
            # no cache — go source picker
            await _show_source_picker(q, context, query)
            return
        await panel_edit(q, f"{hdr('search')}\n\n{sc('send manhwa or manga title now')}", back_kb())
        return

    # Selected manhwa detail
    if key == "sel":
        detail = context.user_data.get("sel")
        if detail:
            slug = detail.get("slug", "")
            src_tag = detail.get("source") or ""
            title = detail.get("title") or slug
            rows = [
                [btn(sc("fetch chapters"), f"p:fetch:{slug[:40]}", "success")],
                [btn(sc("add full series"), f"p:full:{slug[:40]}", "success")],
            ]
            text = f"<b>{sc('manhwa')}</b> · {src_tag}\n\n<b>{title}</b>"
            await panel_edit(q, text, back_kb(*rows))
            return
        # fall through to results/home
        if context.user_data.get("search_results"):
            context.user_data["_nav_restore"] = True
            return await restore_panel(q, context, user, is_owner, "results")
        nav_reset(context)
        await panel_home(q, context, start_caption(user, is_owner), main_kb(is_owner))
        return

    # Chapter list
    if key == "chapters":
        detail = context.user_data.get("sel")
        if detail:
            slug = detail.get("slug") or ""
            chapters = detail.get("chapters") or []
            rows, _, _, total = chapter_rows(slug, chapters, 0, 20)
            text = (
                f"<b>{sc('select chapter')}</b>\n"
                f"<b>{detail.get('title')}</b>\n"
                f"<b>{sc('chapters')}:</b> {total}"
            )
            await panel_edit(q, text, InlineKeyboardMarkup(rows))
            return
        context.user_data["_nav_restore"] = True
        return await restore_panel(q, context, user, is_owner, "sel")

    # Channel pick (for last selected chapter)
    if key == "channel":
        detail = context.user_data.get("sel")
        ch = context.user_data.get("sel_ch")
        if detail and ch:
            ch_num = str(ch.get("num", "?"))
            channels = await db.get_channels(admin_only=True)
            lines = [
                f"<b>{sc('select channel')}</b>",
                f"<b>{detail.get('title')}</b>",
                f"<b>{sc('chapter')}:</b> {ch_num}",
            ]
            rows = []
            for c in channels:
                title = (c.get("title") or c["chat_id"])[:28]
                rows.append([btn(sc(title), f"p:up2:{c['chat_id']}", "success")])
            await panel_edit(q, "\n".join(lines), back_kb(*rows))
            return
        context.user_data["_nav_restore"] = True
        return await restore_panel(q, context, user, is_owner, "chapters")

    # Named static panels
    if key in ("help", "settings", "admins", "channels", "trending", "pending", "logs", "sources", "pip", "update", "addch"):
        await open_named_panel(q, context, user, is_owner, key)
        return

    if key in ("setcap", "setfile", "sethost"):
        context.user_data["_nav_restore"] = True
        return await restore_panel(q, context, user, is_owner, "settings")

    # default
    nav_reset(context)
    await panel_home(q, context, start_caption(user, is_owner), main_kb(is_owner))


async def open_named_panel(q, context, user, is_owner: bool, name: str) -> None:
    """Open a top-level panel by name (used by back stack)."""
    context.user_data["_nav_restore"] = True
    if name == "help":
        text = (
            f"{hdr('help')}\n\n"
            f"{bsc('commands')}\n"
            f"/start — {sc('main panel')}\n"
            f"/search {mono('query')} — {sc('search manhwa')}\n"
            f"/addch — {sc('add channel')}\n"
            f"/ping — {sc('bot latency')}\n"
        )
        await panel_edit(q, text, back_kb())
        return
    if name == "settings":
        tag = await db.get_user_setting(user.id, "caption_tag", CAPTION_TAG)
        fn = await db.get_user_setting(user.id, "filename_template", "{chapter_num} ⌯ {manga_title} [{tag}]")
        text = (
            f"{hdr('settings')}\n\n"
            f"<b>{sc('caption tag')}:</b> {mono(str(tag))}\n"
            f"<b>{sc('file name')}:</b>\n<code>{fn}</code>\n\n"
            f"{sc('tap below to change')}"
        )
        kb = back_kb(
            [btn(sc("edit caption"), "p:setcap", "primary"), btn(sc("file name"), "p:setfile", "primary")],
        )
        await panel_edit(q, text, kb)
        return
    if name == "search":
        context.user_data["await"] = "search"
        await panel_edit(
            q,
            f"{hdr('search')}\n\n{sc('send manhwa or manga title now')}\n{sc('then pick a source')}",
            back_kb(),
        )
        return
    if name == "admins":
        ads = await db.list_admins()
        lines = [f"{hdr('admins')}", ""]
        for a in ads[:20]:
            lines.append(f"• <code>{a.get('user_id')}</code> {a.get('username') or ''}")
        if not ads:
            lines.append(sc("no admins yet"))
        await panel_edit(q, "\n".join(lines), back_kb())
        return
    if name == "channels":
        chs = await db.get_channels(admin_only=False)
        lines = [f"{hdr('channels')}", ""]
        rows = []
        for c in chs[:15]:
            title = (c.get("title") or c.get("chat_id") or "?")[:28]
            lines.append(f"• {title}")
            rows.append([btn(sc(f"del {title[:16]}"), f"p:chdel:{c['chat_id']}", "danger")])
        await panel_edit(q, "\n".join(lines) if lines else sc("no channels"), back_kb(*rows, [btn(sc("add channel"), "p:addch", "success")]))
        return
    if name == "trending":
        await panel_edit(q, f"{hdr('trending')}\n\n{sc('open trending from menu')}", back_kb([btn(sc("trending"), "p:trending", "success")]))
        return
    if name == "pending":
        await panel_edit(q, f"{hdr('pending')}\n\n{sc('open pending from menu')}", back_kb([btn(sc("pending"), "p:pending", "primary")]))
        return
    if name == "logs":
        await panel_edit(q, f"{hdr('logs')}\n\n{sc('open logs from menu')}", back_kb([btn(sc("logs"), "p:logs", "primary")]))
        return
    if name == "sources":
        await show_sources_panel(q, context)
        return
    if name in ("pip", "update", "addch"):
        await panel_edit(q, f"{hdr(name)}\n\n{sc('open from menu')}", back_kb())
        return
    nav_reset(context)
    await panel_home(q, context, start_caption(user, is_owner), main_kb(is_owner))


async def open_dynamic_panel(q, context, user, is_owner: bool, action: str, data: str) -> None:
    """Legacy dynamic restore — route through restore_panel short keys only."""
    context.user_data["_nav_restore"] = True
    key = _norm_panel_key(action or data or "home")
    await restore_panel(q, context, user, is_owner, key)


async def show_sources_panel(q, context) -> None:
    """List the 4 active scrape domains."""
    nav_enter(context, "sources")
    lines = [
        f"{hdr('sources')}",
        f"<b>{sc('active domains')}</b>",
        "",
    ]
    for s in SOURCES:
        lines.append(f"• <b>{s['name']}</b>")
        lines.append(f"  {mono(s['host'])}")
    lines.append("")
    lines.append(sc("search shows all or one domain"))
    await panel_edit(q, "\n".join(lines), back_kb())
