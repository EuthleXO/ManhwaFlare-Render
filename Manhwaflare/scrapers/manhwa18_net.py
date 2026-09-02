# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""manhwa18.net — Inertia SPA"""
from __future__ import annotations
import re
from typing import List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from Manhwaflare.scrapers.base import (
    clean_html, extract_chapter_num, fetch, inertia_props, mk, normalize_chapters,
)

HOST = "https://manhwa18.net"
NAME = "Manhwa18"
SID = "manhwa18_net"


async def search(session, query: str) -> List[dict]:
    url = f"{HOST}/tim-kiem?q={quote_plus(query)}&page=1"
    st, html = await fetch(session, url, HOST + "/")
    if st != 200 or not html:
        return []
    out, seen = [], set()
    props = inertia_props(html) or {}
    mangas = props.get("mangas") or {}
    rows = mangas.get("data") if isinstance(mangas, dict) else (mangas if isinstance(mangas, list) else [])
    for m in rows or []:
        if not isinstance(m, dict):
            continue
        slug = (m.get("slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(mk(
            m.get("name") or m.get("title") or slug, slug,
            f"{HOST}/manga/{slug}",
            m.get("cover_url") or m.get("thumb_url") or "",
            NAME, "manhwa", SID,
        ))
    if not out:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select("a[href*='/manga/']"):
            href = a.get("href") or ""
            mm = re.search(r"/manga/([^/?#]+)", href)
            if not mm:
                continue
            slug = mm.group(1)
            if slug in seen or "chapter" in slug.lower():
                continue
            seen.add(slug)
            title = (a.get("title") or a.get_text(" ", strip=True) or slug).strip()
            full = href if href.startswith("http") else HOST + href
            out.append(mk(title, slug, full.split("?")[0], "", NAME, "manhwa", SID))
    return out


async def detail(session, url: str) -> Optional[dict]:
    # normalize to /manga/{slug}
    if "/manga/" not in url:
        slug = url.rstrip("/").split("/")[-1]
        url = f"{HOST}/manga/{slug}"
    st, html = await fetch(session, url, HOST + "/")
    if st != 200 or not html:
        return None
    props = inertia_props(html) or {}
    manga = props.get("manga") or {}
    chapters_raw = props.get("chapters") or []
    if not manga and not chapters_raw:
        return None
    title = manga.get("name") or url.rstrip("/").split("/")[-1]
    poster = manga.get("cover_url") or manga.get("thumb_url") or manga.get("cover_image") or ""
    synopsis = clean_html(manga.get("pilot") or manga.get("note") or "")
    genres = []
    for g in (manga.get("genres") or []):
        if isinstance(g, dict) and g.get("name"):
            genres.append(g["name"])
        elif isinstance(g, str):
            genres.append(g)
    status_id = manga.get("status_id")
    status_map = {0: "Ongoing", 1: "Completed", 2: "Hiatus", 3: "Cancelled"}
    status = manga.get("status") or status_map.get(status_id, "—")
    score = manga.get("rating_average")
    try:
        if score is not None:
            score = round(float(score) * 20, 1) if float(score) <= 5 else float(score)
        else:
            score = "—"
    except Exception:
        score = "—"
    slug = manga.get("slug") or url.rstrip("/").split("/")[-1]
    raw = []
    for c in chapters_raw:
        if not isinstance(c, dict):
            continue
        name = str(c.get("name") or c.get("title") or "")
        cslug = str(c.get("slug") or "")
        order = c.get("order")
        num = extract_chapter_num(name, cslug)
        if not num and order is not None:
            num = str(order)
        if not num:
            continue
        curl = c.get("url") or f"{HOST}/manga/{slug}/{cslug or ('chapter-' + num)}"
        if not str(curl).startswith("http"):
            curl = HOST + str(curl)
        raw.append({"num": num, "title": name or f"Chapter {num}", "slug": cslug or num, "url": curl})
    chapters = normalize_chapters(raw)
    return {
        "title": title, "slug": slug, "poster": poster, "url": f"{HOST}/manga/{slug}",
        "synopsis": synopsis[:2500], "genres": genres, "score": str(score),
        "status": str(status), "year": "",
        "chapters_count": len(chapters), "chapters": chapters,
        "source": NAME, "source_id": SID, "kind": "Manhwa", "engine": "inertia",
    }


async def images(session, chapter_url: str) -> List[str]:
    st, html = await fetch(session, chapter_url, HOST + "/")
    if st != 200 or not html:
        return []
    props = inertia_props(html) or {}
    images: List[str] = []
    ci = props.get("chapterImages")
    if isinstance(ci, list):
        for item in ci:
            src = (item.get("src") or item.get("url") or "") if isinstance(item, dict) else str(item)
            if src.startswith("//"):
                src = "https:" + src
            if src.startswith("http"):
                images.append(src)
    if not images:
        content = props.get("chapterContent") or ""
        for src in re.findall(r'(?:src|data-src)=["\'](https?://[^"\']+)["\']', str(content), re.I):
            images.append(src)
    if not images:
        for src in re.findall(
            r'(?:data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            html, re.I,
        ):
            if any(x in src.lower() for x in ("avatar", "logo", "icon", "favicon", "cover")):
                continue
            images.append(src)
    out, seen = [], set()
    for u in images:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def trending(session, limit: int = 16) -> List[dict]:
    st, html = await fetch(session, HOST + "/", HOST + "/")
    if st != 200 or not html:
        return []
    props = inertia_props(html) or {}
    out, seen = [], set()
    rows = list(props.get("latestManhwaMain") or []) + list(props.get("popularManga") or [])
    for m in rows:
        if not isinstance(m, dict):
            continue
        slug = (m.get("slug") or "").strip()
        if not slug or slug in seen:
            continue
        seen.add(slug)
        out.append(mk(
            m.get("name") or slug, slug, f"{HOST}/manga/{slug}",
            m.get("cover_url") or "", NAME, "manhwa", SID,
        ))
        if len(out) >= limit:
            break
    return out
