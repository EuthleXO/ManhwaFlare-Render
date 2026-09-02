# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Landscape info poster for channel (cover + rating + synopsis)."""
from __future__ import annotations
import logging
from io import BytesIO
from typing import Optional, List

import aiohttp
from PIL import Image, ImageDraw, ImageFont

log = logging.getLogger("poster")


def _font(size: int):
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def _wrap(draw, text: str, font, max_w: int) -> List[str]:
    words = (text or "").split()
    if not words:
        return []
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if draw.textlength(trial, font=font) <= max_w:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


async def fetch_image(url: str) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=aiohttp.ClientTimeout(total=20),
                             headers={"User-Agent": "Mozilla/5.0", "Referer": "https://manhwa18.net/"}) as r:
                if r.status != 200:
                    return None
                data = await r.read()
        im = Image.open(BytesIO(data)).convert("RGB")
        return im
    except Exception as e:
        log.warning("poster fetch: %s", e)
        return None


async def build_landscape_poster(
    poster_url: str,
    title: str,
    score: str = "",
    status: str = "",
    genres: Optional[List[str]] = None,
    synopsis: str = "",
    chapters: str = "",
) -> Optional[bytes]:
    """1280x720 poster: cover left, info right."""
    W, H = 1280, 720
    canvas = Image.new("RGB", (W, H), (18, 22, 30))
    draw = ImageDraw.Draw(canvas)

    cover = await fetch_image(poster_url)
    left_w = 480
    if cover:
        # cover fit left panel
        cw, ch = cover.size
        scale = max(left_w / cw, H / ch)
        nw, nh = int(cw * scale), int(ch * scale)
        cover = cover.resize((nw, nh), Image.LANCZOS)
        x0 = (left_w - nw) // 2
        y0 = (H - nh) // 2
        canvas.paste(cover, (x0, y0))
    else:
        draw.rectangle([0, 0, left_w, H], fill=(32, 40, 52))

    # gradient strip
    for i in range(40):
        a = int(18 + i * 0.3)
        draw.line([(left_w + i, 0), (left_w + i, H)], fill=(a, a + 4, a + 10))

    font_title = _font(42)
    font_meta = _font(28)
    font_body = _font(22)
    font_small = _font(18)

    x = left_w + 48
    y = 48
    max_text = W - x - 40

    # title
    for line in _wrap(draw, title or "Manhwa", font_title, max_text)[:3]:
        draw.text((x, y), line, font=font_title, fill=(240, 244, 250))
        y += 52

    y += 12
    meta_bits = []
    if score not in ("", None, "—"):
        meta_bits.append(f"Rating {score}" + ("%" if str(score).replace(".", "").isdigit() else ""))
    if status:
        meta_bits.append(str(status))
    if chapters:
        meta_bits.append(f"Ch {chapters}")
    if meta_bits:
        draw.text((x, y), "  ·  ".join(meta_bits), font=font_meta, fill=(125, 211, 252))
        y += 44

    g = ", ".join(genres or [])[:80]
    if g:
        draw.text((x, y), g, font=font_small, fill=(156, 163, 175))
        y += 36

    y += 8
    draw.line([(x, y), (W - 40, y)], fill=(55, 65, 80), width=2)
    y += 20

    syn = (synopsis or "").strip()
    if syn:
        draw.text((x, y), "SYNOPSIS", font=font_small, fill=(148, 163, 184))
        y += 28
        for line in _wrap(draw, syn, font_body, max_text)[:8]:
            draw.text((x, y), line, font=font_body, fill=(226, 232, 240))
            y += 30

    # footer
    draw.text((x, H - 48), "ManhwaFlare", font=font_small, fill=(100, 116, 139))

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=90)
    return buf.getvalue()
