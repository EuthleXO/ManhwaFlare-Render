# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Manhwa18.net AI Animation Videos — list / detail / hls download info."""
from __future__ import annotations
import logging
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from Manhwaflare.scrapers.base import fetch, inertia_props, mk

log = logging.getLogger("aivideos")
HOST = "https://manhwa18.net"
NAME = "AIVideos"
SID = "aivideos"


async def list_videos(session, page: int = 1) -> Dict[str, Any]:
    """Return {items, page, last_page, total} from /videos."""
    url = f"{HOST}/videos" if page <= 1 else f"{HOST}/videos?page={page}"
    st, html = await fetch(session, url, HOST + "/")
    if st != 200 or not html:
        return {"items": [], "page": page, "last_page": 1, "total": 0}
    props = inertia_props(html) or {}
    videos = props.get("videos") or {}
    if isinstance(videos, dict):
        rows = videos.get("data") or []
        return {
            "items": [v for v in rows if isinstance(v, dict)],
            "page": int(videos.get("current_page") or page),
            "last_page": int(videos.get("last_page") or 1),
            "total": int(videos.get("total") or len(rows)),
        }
    if isinstance(videos, list):
        return {"items": videos, "page": 1, "last_page": 1, "total": len(videos)}
    return {"items": [], "page": page, "last_page": 1, "total": 0}


async def get_video(session, slug: str) -> Optional[dict]:
    """Fetch single episode page — returns hls_url + meta."""
    st, html = await fetch(session, f"{HOST}/video/{slug}", HOST + "/")
    if st != 200 or not html:
        return None
    props = inertia_props(html) or {}
    video = props.get("video") or {}
    if not isinstance(video, dict) or not video.get("slug"):
        return None
    manga = video.get("manga") or props.get("mangaInfo") or {}
    episodes = props.get("episodes") or []
    return {
        "id": video.get("id"),
        "title": video.get("title") or slug,
        "slug": video.get("slug") or slug,
        "hls_url": video.get("hls_url") or "",
        "thumbnail_url": video.get("thumbnail_url") or "",
        "duration": video.get("duration") or 0,
        "views": video.get("views") or 0,
        "manga_title": (manga.get("name") if isinstance(manga, dict) else "") or "",
        "manga_slug": (manga.get("slug") if isinstance(manga, dict) else "") or "",
        "episodes": episodes if isinstance(episodes, list) else [],
        "page_url": f"{HOST}/video/{slug}",
    }


async def search(session, query: str) -> List[dict]:
    data = await list_videos(session, 1)
    q = (query or "").lower().strip()
    out = []
    for v in data.get("items") or []:
        title = str(v.get("title") or "")
        if q and q not in title.lower() and q not in str(v.get("slug") or "").lower():
            continue
        slug = str(v.get("slug") or "")
        if not slug:
            continue
        out.append(mk(
            title, slug, f"{HOST}/video/{slug}",
            v.get("thumbnail_url") or "", NAME, "video", SID,
        ))
    # also search AI series on main site
    st2, html2 = await fetch(
        session, f"{HOST}/tim-kiem?q={quote_plus(query + ' AI ANIMATION')}", HOST + "/"
    )
    if st2 == 200 and html2:
        props2 = inertia_props(html2) or {}
        mangas = props2.get("mangas") or {}
        rows2 = mangas.get("data") if isinstance(mangas, dict) else []
        seen = {x["slug"] for x in out}
        for m in rows2 or []:
            if not isinstance(m, dict):
                continue
            slug = m.get("slug") or ""
            name = m.get("name") or ""
            if not slug or slug in seen:
                continue
            if "ai" not in name.lower() and "animation" not in name.lower() and "ai" not in slug:
                continue
            seen.add(slug)
            out.append(mk(
                name, slug, f"{HOST}/manga/{slug}",
                m.get("cover_url") or m.get("thumb_url") or "",
                NAME, "video", SID,
            ))
    return out


async def detail(session, url: str) -> Optional[dict]:
    if "/video/" in url:
        slug = url.rstrip("/").split("/")[-1]
        v = await get_video(session, slug)
        if not v:
            return None
        chapters = []
        for ep in v.get("episodes") or []:
            if not isinstance(ep, dict):
                continue
            es = str(ep.get("slug") or "")
            chapters.append({
                "num": ep.get("title") or es,
                "title": ep.get("title") or es,
                "slug": es,
                "url": f"{HOST}/video/{es}",
            })
        return {
            "title": v.get("manga_title") or v.get("title"),
            "slug": v.get("manga_slug") or v.get("slug"),
            "poster": v.get("thumbnail_url") or "",
            "url": url,
            "synopsis": "",
            "genres": ["AI Animation"],
            "score": "—",
            "status": "—",
            "year": "",
            "chapters_count": len(chapters),
            "chapters": chapters,
            "source": NAME,
            "source_id": SID,
            "kind": "AI Video",
            "engine": "aivideo",
            "hls_url": v.get("hls_url") or "",
        }
    if "/manga/" in url:
        st, html = await fetch(session, url, HOST + "/")
        if st != 200 or not html:
            return None
        props = inertia_props(html) or {}
        manga = props.get("manga") or {}
        chapters_raw = props.get("chapters") or []
        title = manga.get("name") or url.rstrip("/").split("/")[-1]
        poster = manga.get("cover_url") or manga.get("thumb_url") or ""
        pilot = manga.get("pilot") or ""
        if pilot:
            pilot = BeautifulSoup(pilot, "html.parser").get_text(" ", strip=True)
        slug = manga.get("slug") or url.rstrip("/").split("/")[-1]
        chapters = []
        for c in chapters_raw:
            if not isinstance(c, dict):
                continue
            num = str(c.get("name") or c.get("slug") or "")
            cslug = c.get("slug") or num
            curl = c.get("url") or f"{HOST}/manga/{slug}/{cslug}"
            if not str(curl).startswith("http"):
                curl = HOST + str(curl)
            chapters.append({"num": num, "title": num, "slug": str(cslug), "url": curl})
        return {
            "title": title, "slug": slug, "poster": poster, "url": url,
            "synopsis": (pilot or "")[:2500], "genres": ["AI Animation"], "score": "—",
            "status": "—", "year": "",
            "chapters_count": len(chapters), "chapters": chapters,
            "source": NAME, "source_id": SID, "kind": "AI Video", "engine": "aivideo",
        }
    return None


async def images(session, chapter_url: str) -> List[str]:
    return []


async def trending(session, limit: int = 16) -> List[dict]:
    data = await list_videos(session, 1)
    out = []
    for v in (data.get("items") or [])[:limit]:
        slug = str(v.get("slug") or "")
        title = str(v.get("title") or slug)
        out.append(mk(
            title, slug, f"{HOST}/video/{slug}",
            v.get("thumbnail_url") or "", NAME, "video", SID,
        ))
    return out
