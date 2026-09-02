# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Route search / detail / images / trending — 4 sources only."""
from __future__ import annotations
import asyncio
import logging
import re
from typing import List, Optional

import aiohttp

from Manhwaflare.scrapers import manhwa18_net, manhwa18_cc, manhwa18_com, aivideos

log = logging.getLogger("scrapers.router")

SOURCES = [
    {"id": "manhwa18_net", "name": "Manhwa18", "kind": "manhwa", "host": "https://manhwa18.net", "mod": manhwa18_net},
    {"id": "manhwa18_cc", "name": "Manhwa18CC", "kind": "manhwa", "host": "https://manhwa18.cc", "mod": manhwa18_cc},
    {"id": "manhwa18_com", "name": "Manhwa18Com", "kind": "manhwa", "host": "https://manhwa18.com", "mod": manhwa18_com},
    {"id": "aivideos", "name": "AIVideos", "kind": "video", "host": "https://manhwa18.net/videos", "mod": aivideos},
]
SOURCE_BY_ID = {s["id"]: s for s in SOURCES}


async def _search_one(session, src, query):
    try:
        items = await src["mod"].search(session, query)
        return src["name"], items or [], None
    except Exception as e:
        log.debug("search %s: %s", src["id"], e)
        return src["name"], [], str(e)[:120]


async def multi_search(query: str, source_id: Optional[str] = None) -> dict:
    sources = SOURCES
    if source_id and source_id != "all":
        src = SOURCE_BY_ID.get(source_id)
        sources = [src] if src else SOURCES
    timeout = aiohttp.ClientTimeout(total=40)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        rows = await asyncio.gather(*[_search_one(session, s, query) for s in sources])
    found, none, flat, seen = [], [], [], set()
    for name, items, err in rows:
        if items:
            found.append({"site": name, "count": len(items), "items": items})
            for it in items:
                key = it.get("url") or f"{it.get('source')}:{it.get('slug')}"
                if key in seen:
                    continue
                seen.add(key)
                flat.append(it)
        else:
            none.append(name)
    return {"query": query, "found": found, "none": none, "results": flat, "source_id": source_id or "all"}


async def multi_trending(limit: int = 12) -> List[dict]:
    timeout = aiohttp.ClientTimeout(total=35)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        tasks = [s["mod"].trending(session, limit) for s in SOURCES if s["id"] != "aivideos"]
        rows = await asyncio.gather(*tasks, return_exceptions=True)
    out, seen = [], set()
    for row in rows:
        if isinstance(row, Exception) or not row:
            continue
        for it in row:
            key = it.get("url") or it.get("slug")
            if not key or key in seen:
                continue
            seen.add(key)
            out.append(it)
    return out[: limit * 2]


async def get_detail_any(url: str, source: str = "") -> Optional[dict]:
    s = (source or "").lower()
    timeout = aiohttp.ClientTimeout(total=45)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if "aivideo" in s or "/video/" in url:
            return await aivideos.detail(session, url)
        if "manhwa18.cc" in url or "manhwa18cc" in s:
            return await manhwa18_cc.detail(session, url)
        if "manhwa18.com" in url or "manhwa18com" in s:
            return await manhwa18_com.detail(session, url)
        if "manhwa18.net" in url or "manhwa18" in s:
            return await manhwa18_net.detail(session, url)
        for mod in (manhwa18_net, manhwa18_cc, manhwa18_com):
            try:
                d = await mod.detail(session, url)
                if d and (d.get("chapters") is not None or d.get("title")):
                    return d
            except Exception:
                continue
        return None


async def get_images_any(chapter_url: str, source: str = "") -> List[str]:
    s = (source or "").lower()
    timeout = aiohttp.ClientTimeout(total=50)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        if "manhwa18.cc" in chapter_url:
            return await manhwa18_cc.images(session, chapter_url)
        if "manhwa18.com" in chapter_url:
            return await manhwa18_com.images(session, chapter_url)
        imgs = await manhwa18_net.images(session, chapter_url)
        if imgs:
            return imgs
        for mod in (manhwa18_cc, manhwa18_com, aivideos):
            try:
                imgs = await mod.images(session, chapter_url)
                if imgs:
                    return imgs
            except Exception:
                continue
        return []


def format_filename(template: str, chapter_num: str, manga_title: str, tag: str = "@ManhwaFlare") -> str:
    tpl = (template or "{chapter_num} ⌯ {manga_title} [{tag}]").strip()
    ch = re.sub(r"\s+", " ", (chapter_num or "").replace("_", " ")).strip()
    title = re.sub(r"\s+", " ", (manga_title or "").replace("_", " ")).strip()
    tag = (tag or "").strip()
    name = (
        tpl.replace("{chapter_num}", ch)
        .replace("{manga_title}", title)
        .replace("{tag}", tag)
        .replace("{chapter}", ch)
        .replace("{title}", title)
    )
    for c in '\\/:*?"<>|\0':
        name = name.replace(c, "-")
    name = re.sub(r"\s+", " ", name.replace("_", " ")).strip()
    name = re.sub(r"\.pdf$", "", name, flags=re.I)
    return (name or "chapter") + ".pdf"
