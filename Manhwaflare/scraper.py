# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""
Manhwa scraper — manhwa18.net (Inertia SPA)
Parses data-page JSON for reliable results.
"""
from __future__ import annotations
import json
import logging
import re
from html import unescape
from typing import List, Dict, Optional, Tuple
from urllib.parse import quote

import aiohttp
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

BASE = "https://manhwa18.net"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Referer": BASE + "/",
}


def _parse_inertia(html: str) -> Optional[dict]:
    m = re.search(r'data-page="([^"]+)"', html)
    if not m:
        return None
    try:
        return json.loads(unescape(m.group(1)))
    except Exception as e:
        logger.warning("inertia parse fail: %s", e)
        return None


async def _fetch(session: aiohttp.ClientSession, url: str) -> str:
    async with session.get(
        url, headers=HEADERS, timeout=aiohttp.ClientTimeout(total=30)
    ) as r:
        r.raise_for_status()
        return await r.text()


def _manga_item(m: dict) -> Dict:
    return {
        "title": m.get("name") or m.get("title") or "",
        "slug": m.get("slug") or "",
        "poster": m.get("cover_url") or m.get("thumb_url") or m.get("cover_image") or "",
        "url": f"{BASE}/manga/{m.get('slug', '')}",
        "id": m.get("id"),
        "views": m.get("view") or m.get("views") or 0,
    }


async def trending(limit: int = 16) -> List[Dict]:
    """Homepage popular + latest manhwa."""
    results: List[Dict] = []
    seen = set()
    try:
        async with aiohttp.ClientSession() as s:
            html = await _fetch(s, BASE + "/")
        data = _parse_inertia(html)
        if not data:
            logger.error("trending: no inertia data")
            return []
        props = data.get("props") or {}
        pools = []
        for key in ("popularManga", "latestManhwaMain", "featuredManga"):
            val = props.get(key)
            if isinstance(val, list):
                pools.extend(val)
        tr = props.get("topRank") or {}
        if isinstance(tr, dict):
            for k in ("day", "week", "month"):
                lst = tr.get(k)
                if isinstance(lst, list):
                    pools.extend(lst)
        for m in pools:
            if not isinstance(m, dict):
                continue
            item = _manga_item(m)
            if not item["slug"] or item["slug"] in seen:
                continue
            seen.add(item["slug"])
            results.append(item)
            if len(results) >= limit:
                break
    except Exception as e:
        logger.exception("trending failed: %s", e)
    return results


async def search_manhwa(query: str, page: int = 1) -> Tuple[List[Dict], int]:
    """Search via /tim-kiem?q="""
    q = quote(query.strip())
    url = f"{BASE}/tim-kiem?q={q}"
    if page > 1:
        url += f"&page={page}"
    results: List[Dict] = []
    total_pages = 1
    try:
        async with aiohttp.ClientSession() as s:
            html = await _fetch(s, url)
        data = _parse_inertia(html)
        if not data:
            return [], 1
        props = data.get("props") or {}
        mangas = props.get("mangas") or {}
        if isinstance(mangas, dict):
            total_pages = int(mangas.get("last_page") or 1)
            rows = mangas.get("data") or []
        elif isinstance(mangas, list):
            rows = mangas
        else:
            rows = []
        for m in rows:
            if isinstance(m, dict) and m.get("slug"):
                results.append(_manga_item(m))
    except Exception as e:
        logger.exception("search failed: %s", e)
    return results, total_pages


async def get_detail(slug: str) -> Optional[Dict]:
    """Manga detail + chapter list."""
    url = f"{BASE}/manga/{slug}"
    try:
        async with aiohttp.ClientSession() as s:
            html = await _fetch(s, url)
        data = _parse_inertia(html)
        if not data:
            return None
        props = data.get("props") or {}
        manga = props.get("manga") or {}
        chapters_raw = props.get("chapters") or []
        title = manga.get("name") or slug.replace("-", " ").title()
        poster = manga.get("cover_url") or manga.get("thumb_url") or ""
        # synopsis from pilot (HTML)
        pilot = manga.get("pilot") or manga.get("note") or ""
        if pilot:
            from bs4 import BeautifulSoup as _BS
            pilot = _BS(pilot, "html.parser").get_text(" ", strip=True)
        genres = []
        for g in (manga.get("genres") or []):
            if isinstance(g, dict) and g.get("name"):
                genres.append(g["name"])
            elif isinstance(g, str):
                genres.append(g)
        score = manga.get("rating_average")
        if score is not None:
            try:
                score = round(float(score) * 20, 1) if float(score) <= 5 else float(score)
            except Exception:
                score = str(score)
        status_map = {0: "Ongoing", 1: "Completed", 2: "Hiatus", 3: "Cancelled"}
        status = status_map.get(manga.get("status_id"), "—")
        year = ""
        rd = manga.get("release_datetime") or manga.get("created_at") or ""
        if rd:
            year = str(rd)[:4]
        chapters = []
        for c in chapters_raw:
            if not isinstance(c, dict):
                continue
            name = c.get("name") or ""
            cslug = c.get("slug") or ""
            num = name
            m = re.search(r"([0-9]+(?:\.[0-9]+)?)", name)
            if m:
                num = m.group(1)
            chapters.append({
                "num": str(num),
                "title": name,
                "slug": cslug,
                "url": f"{BASE}/manga/{slug}/{cslug}" if cslug else "",
                "id": c.get("id"),
            })
        return {
            "title": title,
            "slug": slug,
            "poster": poster,
            "url": url,
            "chapters": chapters,
            "synopsis": pilot,
            "genres": genres,
            "score": score if score is not None else "—",
            "status": status,
            "chapters_count": len(chapters),
            "year": year,
            "type": "manhwa",
        }
    except Exception as e:
        logger.exception("detail failed: %s", e)
        return None


async def get_images(chapter_url: str) -> List[str]:
    """Extract image URLs from chapter page."""
    images: List[str] = []
    try:
        async with aiohttp.ClientSession() as s:
            html = await _fetch(s, chapter_url)
        data = _parse_inertia(html)
        if data:
            props = data.get("props") or {}
            ci = props.get("chapterImages")
            if isinstance(ci, list):
                for item in ci:
                    if isinstance(item, dict):
                        src = item.get("src") or item.get("url") or ""
                    else:
                        src = str(item)
                    if src.startswith("http"):
                        images.append(src)
            if not images:
                content = props.get("chapterContent") or ""
                if content:
                    soup = BeautifulSoup(content, "html.parser")
                    for img in soup.find_all("img"):
                        src = img.get("src") or img.get("data-src") or ""
                        if src.startswith("http"):
                            images.append(src)
        if not images:
            soup = BeautifulSoup(html, "html.parser")
            for img in soup.select("img"):
                src = img.get("src") or img.get("data-src") or ""
                if src.startswith("http") and ("manhwa18" in src or "storage" in src):
                    if "avatar" not in src.lower() and "logo" not in src.lower():
                        images.append(src)
        seen, out = set(), []
        for u in images:
            if u not in seen:
                seen.add(u)
                out.append(u)
        return out
    except Exception as e:
        logger.exception("images failed: %s", e)
        return []


async def download_images(urls: List[str], concurrency: int = 6) -> List[bytes]:
    import asyncio
    sem = asyncio.Semaphore(concurrency)
    out: List[Optional[bytes]] = [None] * len(urls)

    async def one(i: int, url: str):
        async with sem:
            try:
                async with aiohttp.ClientSession() as s:
                    async with s.get(
                        url,
                        headers={**HEADERS, "Referer": BASE + "/"},
                        timeout=aiohttp.ClientTimeout(total=45),
                    ) as r:
                        if r.status == 200:
                            out[i] = await r.read()
            except Exception:
                pass

    await asyncio.gather(*(one(i, u) for i, u in enumerate(urls)))
    return [b for b in out if b]
