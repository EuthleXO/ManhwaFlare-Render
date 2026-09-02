# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Shared scraper helpers."""
from __future__ import annotations
import json
import logging
import re
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
from bs4 import BeautifulSoup

log = logging.getLogger("scrapers")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

_JUNK_CH = re.compile(
    r"(read\s*(first|last)|^(first|last)$|ch\s*read\s*(first|last))",
    re.I,
)


async def fetch(session: aiohttp.ClientSession, url: str, referer: str = "") -> Tuple[int, str]:
    h = dict(HEADERS)
    if referer:
        h["Referer"] = referer
    try:
        async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=25)) as r:
            text = await r.text(errors="ignore")
            if "Just a moment" in text[:800] or "cf-browser-verification" in text[:800]:
                return r.status, ""
            return r.status, text
    except Exception as e:
        log.debug("fetch %s: %s", url, e)
        return 0, ""


async def fetch_json(session: aiohttp.ClientSession, url: str, referer: str = "") -> Tuple[int, Any]:
    h = dict(HEADERS)
    h["Accept"] = "application/json"
    if referer:
        h["Referer"] = referer
    try:
        async with session.get(url, headers=h, timeout=aiohttp.ClientTimeout(total=25)) as r:
            try:
                data = await r.json(content_type=None)
            except Exception:
                data = None
            return r.status, data
    except Exception as e:
        log.debug("fetch_json %s: %s", url, e)
        return 0, None


def inertia_props(html: str) -> Optional[dict]:
    m = re.search(r'data-page="([^"]+)"', html)
    if not m:
        return None
    try:
        raw = unescape(m.group(1))
        data = json.loads(raw)
        if not isinstance(data, dict):
            return None
        props = data.get("props")
        return props if isinstance(props, dict) else data
    except Exception:
        return None


def mk(title, slug, url, poster, source, kind, source_id="") -> dict:
    return {
        "title": (title or slug or "").strip(),
        "slug": (slug or "").strip(),
        "url": url,
        "poster": poster or "",
        "source": source,
        "source_id": source_id or "",
        "kind": kind,
    }


def clean_html(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(" ", strip=True)


def chapter_sort_key(num: str) -> float:
    """Numeric sort key for chapter numbers (supports 12.5)."""
    m = re.search(r"(\d+(?:\.\d+)?)", str(num or ""))
    if not m:
        return 0.0
    try:
        return float(m.group(1))
    except Exception:
        return 0.0


def extract_chapter_num(text: str, fallback: str = "") -> str:
    """Pull chapter number from title/slug text."""
    t = (text or "").strip()
    m = re.search(
        r"(?:chapter|ch\.?|chap\.?|ep\.?|episode)\s*([0-9]+(?:\.[0-9]+)?)",
        t,
        re.I,
    )
    if m:
        return m.group(1)
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", t)
    if m:
        return m.group(1)
    m = re.search(r"([0-9]+(?:\.[0-9]+)?)", fallback or "")
    if m:
        return m.group(1)
    return ""


def is_junk_chapter(name: str, path: str = "") -> bool:
    blob = f"{name} {path}".strip()
    if not blob:
        return True
    if _JUNK_CH.search(blob):
        return True
    if re.search(r"read[-_\s]*(first|last)", path or "", re.I):
        return True
    return False


def normalize_chapters(chapters: List[dict]) -> List[dict]:
    """Dedupe + sort oldest→newest so First = ch1, New = latest."""
    out: List[dict] = []
    seen_url = set()
    seen_num = set()
    for c in chapters or []:
        if not isinstance(c, dict):
            continue
        name = str(c.get("title") or c.get("num") or "")
        path = str(c.get("slug") or c.get("url") or "")
        if is_junk_chapter(name, path):
            continue
        num = str(c.get("num") or extract_chapter_num(name, path) or "").strip()
        if not num:
            continue
        url = (c.get("url") or "").strip()
        if url and url in seen_url:
            continue
        # allow same num only once (prefer first seen after sort we re-sort anyway)
        key = num
        if key in seen_num:
            continue
        if url:
            seen_url.add(url)
        seen_num.add(key)
        out.append({
            "num": num,
            "title": name or f"Chapter {num}",
            "slug": str(c.get("slug") or num),
            "url": url,
        })
    out.sort(key=lambda c: chapter_sort_key(c.get("num")))
    return out
