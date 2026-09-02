# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Search source picker + results rendering."""
from __future__ import annotations
import logging

from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from Manhwaflare.nav import nav_enter
from Manhwaflare.scrapers import multi_search, SOURCES, SOURCE_BY_ID
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit

log = logging.getLogger("mf.search")

async def _show_source_picker(q, context, query: str) -> None:
    """After user types query — pick All or one of 4 domains."""
    nav_enter(context, "srcpick")
    context.user_data["search_q"] = query
    lines = [
        f"<b>{sc('search')}</b> · <code>{query}</code>",
        "",
        f"<b>{sc('choose source')}</b>",
        sc("all = search every domain"),
        sc("or pick one domain only"),
        "",
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
    await panel_edit(q, "\n".join(lines), back_kb(*rows))


async def _render_search_results(q, context, query: str, results: list, source_id: str = "all", page: int = 1) -> None:
    """Render cached results with page navigation."""
    nav_enter(context, "results")
    per = 10
    total = len(results)
    pages = max(1, (total + per - 1) // per)
    page = max(1, min(int(page or 1), pages))
    start = (page - 1) * per
    chunk = results[start:start + per]
    context.user_data["search_page"] = page
    src_label = "ALL"
    if source_id and source_id != "all":
        src_label = (SOURCE_BY_ID.get(source_id) or {}).get("name") or source_id
    found_sites = {}
    for it in results:
        s = it.get("source") or "?"
        found_sites[s] = found_sites.get(s, 0) + 1
    lines = [
        f"<b>{sc('search')}</b> · <code>{query}</code>",
        f"<b>{sc('source')}:</b> {src_label}",
        f"<b>{sc('page')}:</b> {page}/{pages} · <b>{sc('results')}:</b> {total}",
        "",
    ]
    if found_sites:
        lines.append(
            f"<b>{sc('found')}:</b> " + ", ".join(f"{k}({v})" for k, v in found_sites.items())
        )
        lines.append("")
    rows = []
    for i, it in enumerate(chunk):
        global_i = start + i
        title = (it.get("title") or it.get("slug") or "?")[:28]
        src = it.get("source") or "?"
        label = f"{title} · {src}"
        rows.append([btn(sc(label[:58]), f"p:msel:{global_i}", "primary")])
    nav = []
    if page > 1:
        nav.append(btn(sc("« prev"), f"p:spage:{page-1}", "primary"))
    if page < pages:
        nav.append(btn(sc("next »"), f"p:spage:{page+1}", "primary"))
    if nav:
        rows.append(nav)
    rows.append([btn(sc("change source"), "p:srcagain", "primary")])
    text = "\n".join(lines)
    if len(text) > 3500:
        text = text[:3500] + "…"
    await panel_edit(q, text, back_kb(*rows))


async def _show_search(q, context, query: str, page: int = 1, source_id: str = "all") -> None:
    """Run multi or single-source search and list results with source tags."""
    try:
        await context.bot.send_chat_action(chat_id=q.message.chat_id, action=ChatAction.TYPING)
    except Exception:
        pass
    data = await multi_search(query, source_id=source_id if source_id != "all" else None)
    results = data.get("results") or []
    context.user_data["search_q"] = query
    context.user_data["search_source"] = source_id
    smap = {}
    for i, it in enumerate(results):
        smap[str(i)] = it
        key = f"{it.get('source_id') or it.get('source')}:{it.get('slug')}"
        smap[key] = it
    context.user_data["search_map"] = smap
    context.user_data["search_results"] = results
    await _render_search_results(q, context, query, results, source_id, page=1)


