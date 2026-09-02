# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""manhwa18.cc — HTML webtoon pages"""
from __future__ import annotations
import re
from typing import List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from Manhwaflare.scrapers.base import (
    extract_chapter_num, fetch, is_junk_chapter, mk, normalize_chapters,
)

HOST = "https://manhwa18.cc"
NAME = "Manhwa18CC"
SID = "manhwa18_cc"


async def search(session, query: str) -> List[dict]:
    urls = [
        f"{HOST}/search?q={quote_plus(query)}",
        f"{HOST}/search?keyword={quote_plus(query)}",
        f"{HOST}/?s={quote_plus(query)}",
    ]
    out, seen = [], set()
    for url in urls:
        st, html = await fetch(session, url, HOST + "/")
        if st != 200 or not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select('a[href*="/webtoon/"]'):
            href = a.get("href") or ""
            mm = re.search(r"/webtoon/([^/?#]+)/?$", href.rstrip("/"))
            # only series root, not chapter
            if not mm:
                mm2 = re.search(r"/webtoon/([^/?#]+)", href)
                if not mm2:
                    continue
                # chapter paths have extra segment
                rest = href.split(f"/webtoon/{mm2.group(1)}/")[-1] if f"/webtoon/{mm2.group(1)}/" in href else ""
                if rest and rest not in ("", mm2.group(1)):
                    continue
                slug = mm2.group(1)
            else:
                slug = mm.group(1)
            if slug in seen or "chapter" in slug.lower():
                continue
            title = (a.get("title") or a.get_text(" ", strip=True) or slug).strip()
            if re.match(r"^(chapter|ch)\.?\s*\d+", title, re.I):
                continue
            if is_junk_chapter(title, href):
                continue
            seen.add(slug)
            full = href if href.startswith("http") else HOST + href
            full = re.sub(r"/webtoon/([^/]+)/.*", r"/webtoon/\1", full)
            if not full.startswith("http"):
                full = HOST + full
            out.append(mk(title, slug, f"{HOST}/webtoon/{slug}", "", NAME, "manhwa", SID))
        if out:
            break
    return out


async def detail(session, url: str) -> Optional[dict]:
    if "/webtoon/" not in url:
        slug = url.rstrip("/").split("/")[-1]
        url = f"{HOST}/webtoon/{slug}"
    # strip chapter segment
    m = re.search(r"(https?://[^/]+/webtoon/[^/]+)", url)
    if m:
        url = m.group(1)
    st, html = await fetch(session, url, HOST + "/")
    if st != 200 or not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1, .series-name, .manga-title, .post-title h1")
    title = title_el.get_text(strip=True) if title_el else url.rstrip("/").split("/")[-1]
    poster = ""
    img = soup.select_one(".series-cover img, .summary_image img, .manga-thumb img, .thumb img, img.lazy")
    if img:
        poster = img.get("data-src") or img.get("src") or ""
    synopsis = ""
    syn = soup.select_one(".summary__content, .manga-summary, .dsct, #synopsis, .description, .summary")
    if syn:
        synopsis = syn.get_text(" ", strip=True)
    genres = []
    for a in soup.select("a[href*='/genre'], .genres a, a[rel='tag']"):
        g = a.get_text(strip=True)
        if g and g not in genres:
            genres.append(g)
    status = "—"
    for row in soup.select(".post-content_item, .tsinfo .imptdt, .info-item, .status"):
        txt = row.get_text(" ", strip=True).lower()
        if "status" in txt:
            status = row.get_text(" ", strip=True).split(":")[-1].strip() or status
            break
    slug = url.rstrip("/").split("/")[-1]
    raw = []
    for a in soup.select(f'a[href*="/webtoon/{slug}/"]'):
        href = a.get("href") or ""
        path = href.split(f"/webtoon/{slug}/")[-1].strip("/")
        if not path:
            continue
        name = a.get_text(" ", strip=True) or path
        if is_junk_chapter(name, path):
            continue
        num = extract_chapter_num(name, path)
        if not num:
            continue
        full = href if href.startswith("http") else HOST + href
        raw.append({"num": num, "title": name or f"Chapter {num}", "slug": path, "url": full})
    chapters = normalize_chapters(raw)
    return {
        "title": title, "slug": slug, "poster": poster, "url": f"{HOST}/webtoon/{slug}",
        "synopsis": synopsis[:2500], "genres": genres, "score": "—",
        "status": status, "year": "",
        "chapters_count": len(chapters), "chapters": chapters,
        "source": NAME, "source_id": SID, "kind": "Manhwa", "engine": "cc",
    }


async def images(session, chapter_url: str) -> List[str]:
    st, html = await fetch(session, chapter_url, HOST + "/")
    if st != 200 or not html:
        return []
    imgs = []
    soup = BeautifulSoup(html, "lxml")
    for img in soup.select(
        ".chapter-content img, .reading-content img, #chapter-content img, "
        ".page-chapter img, .chapter_img img, .read-content img, img"
    ):
        src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        if not src or any(x in src.lower() for x in ("avatar", "logo", "icon", "favicon", "cover")):
            continue
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http") and re.search(r"\.(jpg|jpeg|png|webp)", src, re.I):
            imgs.append(src)
    if not imgs:
        for src in re.findall(
            r'(?:data-src|src)=["\'](https?://[^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']',
            html, re.I,
        ):
            if any(x in src.lower() for x in ("avatar", "logo", "icon", "favicon")):
                continue
            imgs.append(src)
    out, seen = [], set()
    for u in imgs:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


async def trending(session, limit: int = 16) -> List[dict]:
    st, html = await fetch(session, HOST + "/", HOST + "/")
    if st != 200 or not html:
        return []
    out, seen = [], set()
    soup = BeautifulSoup(html, "lxml")
    for a in soup.select('a[href*="/webtoon/"]'):
        href = a.get("href") or ""
        if "/chapter" in href:
            continue
        mm = re.search(r"/webtoon/([^/?#]+)/?$", href.rstrip("/"))
        if not mm:
            continue
        slug = mm.group(1)
        if slug in seen:
            continue
        seen.add(slug)
        title = (a.get("title") or a.get_text(" ", strip=True) or slug).strip()
        out.append(mk(title, slug, f"{HOST}/webtoon/{slug}", "", NAME, "manhwa", SID))
        if len(out) >= limit:
            break
    return out
