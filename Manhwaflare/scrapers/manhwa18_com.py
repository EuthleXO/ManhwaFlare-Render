# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""manhwa18.com — HTML list-chapters"""
from __future__ import annotations
import re
from typing import List, Optional
from urllib.parse import quote_plus

from bs4 import BeautifulSoup

from Manhwaflare.scrapers.base import (
    clean_html, extract_chapter_num, fetch, is_junk_chapter, mk, normalize_chapters,
)

HOST = "https://manhwa18.com"
NAME = "Manhwa18Com"
SID = "manhwa18_com"


async def search(session, query: str) -> List[dict]:
    urls = [
        f"{HOST}/tim-kiem?q={quote_plus(query)}",
        f"{HOST}/search?keyword={quote_plus(query)}",
        f"{HOST}/?s={quote_plus(query)}",
    ]
    out, seen = [], set()
    for url in urls:
        st, html = await fetch(session, url, HOST + "/")
        if st != 200 or not html:
            continue
        soup = BeautifulSoup(html, "lxml")
        for a in soup.select(
            "div.series-title a[href*='/manga/'], "
            ".thumb_attr a[href*='/manga/'], "
            "a[href*='/manga/']"
        ):
            href = a.get("href") or ""
            mm = re.search(r"/manga/([^/?#]+)", href)
            if not mm:
                continue
            slug = mm.group(1)
            if slug in seen or "chapter" in slug.lower() or "chap-" in slug.lower():
                continue
            # skip chapter pages
            if re.search(r"/manga/[^/]+/(chapter|chap)", href, re.I):
                continue
            title = (a.get("title") or a.get_text(" ", strip=True) or slug).strip()
            if re.match(r"^(chapter|ch)\.?\s*\d+", title, re.I):
                continue
            seen.add(slug)
            full = href if href.startswith("http") else HOST + href
            full = full.split("?")[0].rstrip("/")
            # poster near card
            poster = ""
            parent = a.find_parent(["div", "li", "article"])
            if parent:
                img = parent.select_one("img[src], img[data-src]")
                if img:
                    poster = img.get("data-src") or img.get("src") or ""
            out.append(mk(title, slug, full if "/manga/" in full else f"{HOST}/manga/{slug}", poster, NAME, "manhwa", SID))
        if out:
            break
    return out


async def detail(session, url: str) -> Optional[dict]:
    if "/manga/" not in url:
        slug = url.rstrip("/").split("/")[-1]
        url = f"{HOST}/manga/{slug}"
    st, html = await fetch(session, url, HOST + "/")
    if st != 200 or not html:
        return None
    soup = BeautifulSoup(html, "lxml")
    title_el = soup.select_one("h1, .series-name, .manga-title, .post-title h1")
    title = title_el.get_text(strip=True) if title_el else url.rstrip("/").split("/")[-1]
    poster = ""
    img = soup.select_one(".series-cover img, .summary_image img, .manga-thumb img, img.lazy")
    if img:
        poster = img.get("data-src") or img.get("src") or ""
    synopsis = ""
    syn = soup.select_one(".summary__content, .manga-summary, .dsct, #synopsis, .description")
    if syn:
        synopsis = syn.get_text(" ", strip=True)
    genres = []
    for a in soup.select("a[href*='/the-loai/'], .genres a, a[rel='tag']"):
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
    if "/manga/" in url:
        slug = url.split("/manga/")[-1].split("/")[0]

    raw = []
    # Primary: list-chapters anchors (real structure)
    for a in soup.select(".list-chapters a[href], #list-chapters a[href], .list-chapter a[href]"):
        href = a.get("href") or ""
        if not href:
            continue
        name = (
            a.get("title")
            or (a.select_one(".chapter-name").get_text(" ", strip=True) if a.select_one(".chapter-name") else "")
            or a.get_text(" ", strip=True)
            or ""
        )
        if is_junk_chapter(name, href):
            continue
        num = extract_chapter_num(name, href)
        if not num:
            continue
        full = href if href.startswith("http") else HOST + href
        cslug = full.rstrip("/").split("/")[-1]
        raw.append({"num": num, "title": name or f"Chapter {num}", "slug": cslug, "url": full})

    # Fallback: any /manga/{slug}/chapter links
    if not raw:
        for a in soup.select(f'a[href*="/manga/{slug}/"]'):
            href = a.get("href") or ""
            if not re.search(r"(chapter|chap-)", href, re.I):
                continue
            name = a.get("title") or a.get_text(" ", strip=True) or ""
            if is_junk_chapter(name, href):
                continue
            num = extract_chapter_num(name, href)
            if not num:
                continue
            full = href if href.startswith("http") else HOST + href
            raw.append({"num": num, "title": name or f"Chapter {num}", "slug": full.rstrip("/").split("/")[-1], "url": full})

    chapters = normalize_chapters(raw)
    return {
        "title": title, "slug": slug, "poster": poster, "url": f"{HOST}/manga/{slug}",
        "synopsis": synopsis[:2500], "genres": genres, "score": "—",
        "status": status, "year": "",
        "chapters_count": len(chapters), "chapters": chapters,
        "source": NAME, "source_id": SID, "kind": "Manhwa", "engine": "com",
    }


async def images(session, chapter_url: str) -> List[str]:
    st, html = await fetch(session, chapter_url, HOST + "/")
    if st != 200 or not html:
        return []
    imgs = []
    soup = BeautifulSoup(html, "lxml")
    for img in soup.select(
        ".chapter-content img, .reading-content img, #chapter-content img, "
        ".page-chapter img, .chapter_img img, img.lazy"
    ):
        src = img.get("data-src") or img.get("data-original") or img.get("src") or ""
        if not src or any(x in src.lower() for x in ("avatar", "logo", "icon", "favicon")):
            continue
        if src.startswith("//"):
            src = "https:" + src
        if src.startswith("http"):
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
    for a in soup.select("a[href*='/manga/']"):
        href = a.get("href") or ""
        mm = re.search(r"/manga/([^/?#]+)", href)
        if not mm:
            continue
        slug = mm.group(1)
        if slug in seen or "chapter" in slug.lower():
            continue
        if re.search(r"/manga/[^/]+/(chapter|chap)", href, re.I):
            continue
        seen.add(slug)
        title = (a.get("title") or a.get_text(" ", strip=True) or slug).strip()
        if len(title) < 2:
            continue
        out.append(mk(title, slug, f"{HOST}/manga/{slug}", "", NAME, "manhwa", SID))
        if len(out) >= limit:
            break
    return out
