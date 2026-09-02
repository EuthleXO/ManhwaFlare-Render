# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Background worker — live progress, atomic claim, cancel support, stuck recovery."""
from __future__ import annotations
import asyncio
import logging
import re
import time
from io import BytesIO
from typing import Optional, List

import aiohttp
from telegram import Bot, InputFile
from telegram.constants import ParseMode
import img2pdf
from PIL import Image

from Manhwaflare import db
from Manhwaflare.config import BOT_TOKEN, MAX_CONCURRENT, CAPTION_TAG, FILENAME_TEMPLATE
from Manhwaflare.text import sc
from Manhwaflare.scrapers import format_filename, get_images_any
from Manhwaflare.log_channel import flush_logs_to_channel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
log = logging.getLogger("worker")
for _name in ("httpx", "httpcore", "telegram", "telegram.ext", "aiohttp", "urllib3"):
    logging.getLogger(_name).setLevel(logging.WARNING)

SUCCESS_STICKER = "CAACAgUAAxkBAAERsHRqetAntl7ECaCWzEPTdzdeHZY-0gACxg8AAiK-yFYv6Jcy_r3roD0E"
TELEGRAM_MAX_MB = 48
MAX_PAGES_SOFT = 120  # warn / skip extreme chapters


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").replace("_", " ")).strip()


def progress_bar(pct: int) -> str:
    pct = max(0, min(100, int(pct)))
    f = round(pct / 10)
    return "『" + ("●" * f) + ("○" * (10 - f)) + "』"


def fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n/1024:.1f} KB"
    return f"{n/(1024*1024):.1f} MB"


def fmt_speed(bps: float) -> str:
    return "—" if bps <= 0 else f"{fmt_size(int(bps))}/s"


def fmt_eta(seconds: float) -> str:
    if seconds <= 0 or seconds > 86400:
        return "—"
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m {s}s" if m < 60 else f"{m//60}h {m%60}m"


def status_html(chapter, title, phase, pct, **extra) -> str:
    import html as H
    pct = max(0, min(100, int(pct)))
    line1 = f"⌯ {sc('chapter')} {_clean(str(chapter))} ~"
    line2 = f"{sc(phase)}… {progress_bar(pct)} <b>{pct}%</b>"
    body = f"<b>{H.escape(line1)}</b>\n{line2}"
    bits = []
    if extra.get("total"):
        bits.append(f"<b>{sc('pages')}:</b> {extra.get('done', 0)}/{extra['total']}")
    if extra.get("speed"):
        bits.append(f"<b>{sc('speed')}:</b> {extra['speed']}")
    if extra.get("eta") and pct < 100:
        bits.append(f"<b>{sc('eta')}:</b> {extra['eta']}")
    if extra.get("size"):
        bits.append(f"<b>{sc('size')}:</b> {extra['size']}")
    if extra.get("bulk"):
        bits.append(f"<b>{sc('batch')}:</b> {extra['bulk']}")
    if bits:
        body += "\n" + " · ".join(bits)
    if title:
        body += f"\n<code>{H.escape(_clean(str(title))[:60])}</code>"
    return f"<blockquote>{body}</blockquote>"


def format_caption_html(chapter, title, tag="") -> str:
    import html as H
    plain = f"{_clean(chapter)} ⌯ {_clean(title)}"
    if tag:
        plain += f" [{_clean(tag)}]"
    return f"<blockquote><b>{H.escape(plain)}</b></blockquote>"


def images_to_pdf(raws, quality=75, max_w=1200) -> bytes:
    pages = []
    for raw in raws:
        try:
            im = Image.open(BytesIO(raw))
            if im.mode != "RGB":
                im = im.convert("RGB")
            w, h = im.size
            if w > max_w:
                im = im.resize((max_w, int(h * max_w / w)), Image.LANCZOS)
            buf = BytesIO()
            im.save(buf, format="JPEG", quality=quality, optimize=True)
            pages.append(buf.getvalue())
        except Exception:
            continue
    if not pages:
        raise ValueError("no valid images")
    return img2pdf.convert(pages)


def build_pdf_under_limit(raws) -> bytes:
    for q, w in ((80, 1400), (70, 1200), (55, 1000), (40, 800), (30, 700)):
        pdf = images_to_pdf(raws, q, w)
        if len(pdf) / (1024 * 1024) <= TELEGRAM_MAX_MB:
            return pdf
    slim = raws[::2] if len(raws) > 10 else raws
    pdf = images_to_pdf(slim, 35, 700)
    if len(pdf) / (1024 * 1024) > TELEGRAM_MAX_MB:
        raise ValueError(f"PDF too large ({len(pdf)/(1024*1024):.1f} MB)")
    return pdf


async def edit_msg(bot, chat_id, msg_id, text):
    if not chat_id or not msg_id:
        return
    try:
        await bot.edit_message_text(
            chat_id=chat_id, message_id=msg_id, text=text[:4096], parse_mode=ParseMode.HTML
        )
    except Exception:
        try:
            await bot.edit_message_caption(
                chat_id=chat_id, message_id=msg_id, caption=text[:1024], parse_mode=ParseMode.HTML
            )
        except Exception:
            pass


async def broadcast_status(bot, job, text):
    """Update channel status msg + admin status msg."""
    await edit_msg(bot, job.get("chat_id"), job.get("tg_message_id"), text)
    await edit_msg(bot, job.get("status_chat_id"), job.get("status_message_id"), text)


async def robust_download(urls: list, referer: str = "") -> list:
    """Download page images with proper Referer and retries."""
    from urllib.parse import urlparse
    if not urls:
        return []
    ref = referer or (f"{urlparse(urls[0]).scheme}://{urlparse(urls[0]).netloc}/")
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Referer": ref,
        "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
    }
    out = []
    timeout = aiohttp.ClientTimeout(total=45)
    # Prefer SSL verification; fall back only on rare SSL errors
    connector = aiohttp.TCPConnector(ssl=True)
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        for u in urls:
            data = b""
            for attempt in range(3):
                try:
                    async with session.get(u, headers=headers) as r:
                        if r.status == 200:
                            data = await r.read()
                            if len(data) > 500:
                                break
                except Exception:
                    await asyncio.sleep(0.4 * (attempt + 1))
            if data and len(data) > 500:
                out.append(data)
    return out


async def process(bot: Bot, job: dict) -> None:
    key = job["job_key"]
    chat_id = job["chat_id"]
    title = _clean(job.get("manga_title") or "manhwa")
    ch = _clean(str(job.get("chapter_num") or "0"))
    bulk = ""
    if job.get("bulk_total"):
        bulk = f"{job.get('bulk_index', 1)}/{job['bulk_total']}"

    # Early cancel check
    if job.get("cancel_requested") or await db.is_cancel_requested(key):
        await db.update_job(key, status="cancelled", error="cancelled by admin", progress=0)
        log.info("cancelled (early) %s", key)
        return

    log.info("job %s", key)
    msg_id = 0
    try:
        st = status_html(ch, title, "queued", 0, bulk=bulk)
        try:
            m = await bot.send_message(chat_id, st, parse_mode=ParseMode.HTML)
            msg_id = m.message_id
            await db.update_job(key, tg_message_id=msg_id)
            job["tg_message_id"] = msg_id
        except Exception as e:
            log.warning("channel status: %s", e)

        await broadcast_status(bot, job, status_html(ch, title, "starting", 3, bulk=bulk))

        # Cancel check
        if await db.is_cancel_requested(key):
            await db.update_job(key, status="cancelled", error="cancelled by admin")
            await broadcast_status(bot, job, status_html(ch, title, "cancelled", 0, bulk=bulk))
            if msg_id:
                try:
                    await bot.delete_message(chat_id, msg_id)
                except Exception:
                    pass
            return

        # Optional landscape poster (first of bulk or single)
        # channel info-poster disabled by request

        url = job.get("chapter_url") or ""
        if not url:
            raise ValueError("no chapter_url")

        if await db.is_cancel_requested(key):
            await db.update_job(key, status="cancelled", error="cancelled by admin")
            await broadcast_status(bot, job, status_html(ch, title, "cancelled", 0, bulk=bulk))
            return

        await broadcast_status(bot, job, status_html(ch, title, "fetching", 8, bulk=bulk))
        urls = await get_images_any(url, job.get('source') or '')
        if not urls:
            urls = []
        if not urls:
            raise ValueError("no images found")
        total = len(urls)
        if total > MAX_PAGES_SOFT:
            log.warning("chapter has %s pages (soft limit %s)", total, MAX_PAGES_SOFT)

        raws: List[bytes] = []
        batch = 6
        t_dl = time.monotonic()
        bytes_done = 0
        for i in range(0, total, batch):
            if await db.is_cancel_requested(key):
                await db.update_job(key, status="cancelled", error="cancelled by admin")
                await broadcast_status(bot, job, status_html(ch, title, "cancelled", 0, bulk=bulk))
                if msg_id:
                    try:
                        await bot.delete_message(chat_id, msg_id)
                    except Exception:
                        pass
                return

            part = await robust_download(urls[i:i + batch], referer=url)
            raws.extend(part)
            bytes_done += sum(len(x) for x in part)
            done = len(raws)
            elapsed = max(0.1, time.monotonic() - t_dl)
            speed = bytes_done / elapsed
            pct = 10 + int(70 * done / max(1, total))
            eta = ((total - done) / max(1, done / elapsed)) if done else 0
            await db.update_job(key, progress=pct)
            await broadcast_status(
                bot, job,
                status_html(
                    ch, title, "downloading", pct, bulk=bulk,
                    done=done, total=total, speed=fmt_speed(speed),
                    eta=fmt_eta(eta), size=fmt_size(bytes_done),
                ),
            )
        if not raws:
            raise ValueError(f"download failed (0/{total} pages — check source/referer)")

        if await db.is_cancel_requested(key):
            await db.update_job(key, status="cancelled", error="cancelled by admin")
            await broadcast_status(bot, job, status_html(ch, title, "cancelled", 0, bulk=bulk))
            return

        await broadcast_status(
            bot, job,
            status_html(ch, title, "building pdf", 82, bulk=bulk, done=len(raws), total=total),
        )
        pdf = build_pdf_under_limit(raws)
        # free memory ASAP
        del raws
        pdf_size = len(pdf)

        await broadcast_status(
            bot, job,
            status_html(ch, title, "uploading", 92, bulk=bulk, done=total, total=total, size=fmt_size(pdf_size)),
        )

        admin_id = int(job.get("admin_id") or 0)
        try:
            tag = _clean(await db.get_user_setting(admin_id, "caption_tag", CAPTION_TAG) or "")
        except Exception:
            tag = _clean(await db.get_setting("caption_tag", CAPTION_TAG) or "")
        caption_html = job.get("caption") or format_caption_html(ch, title, tag)
        if "<blockquote>" not in str(caption_html):
            caption_html = format_caption_html(ch, title, tag)
        try:
            tpl = await db.get_user_setting(admin_id, "filename_template", FILENAME_TEMPLATE)
        except Exception:
            tpl = await db.get_setting("filename_template", FILENAME_TEMPLATE)
        display_name = format_filename(tpl, ch, title, tag)

        thumb_file = None
        if job.get("poster"):
            try:
                timeout = aiohttp.ClientTimeout(total=20)
                async with aiohttp.ClientSession(timeout=timeout) as s:
                    async with s.get(
                        job["poster"],
                        headers={"User-Agent": "Mozilla/5.0"},
                    ) as r:
                        if r.status == 200:
                            raw = await r.read()
                            im = Image.open(BytesIO(raw)).convert("RGB")
                            im.thumbnail((320, 320), Image.LANCZOS)
                            buf = BytesIO()
                            im.save(buf, format="JPEG", quality=85)
                            thumb_file = InputFile(BytesIO(buf.getvalue()), filename="thumb.jpg")
            except Exception:
                pass

        kwargs = dict(
            chat_id=chat_id,
            document=InputFile(BytesIO(pdf), filename=display_name),
            caption=str(caption_html)[:1024],
            parse_mode=ParseMode.HTML,
            read_timeout=180, write_timeout=180, connect_timeout=60,
        )
        if thumb_file:
            kwargs["thumbnail"] = thumb_file
        await bot.send_document(**kwargs)

        done_txt = status_html(
            ch, title, "complete", 100, bulk=bulk,
            done=total, total=total, size=fmt_size(pdf_size),
        )
        await broadcast_status(bot, job, done_txt)
        try:
            await bot.send_sticker(chat_id, SUCCESS_STICKER)
        except Exception:
            pass
        await asyncio.sleep(0.5)
        if msg_id:
            try:
                await bot.delete_message(chat_id, msg_id)
            except Exception:
                pass

        await db.update_job(key, status="done", progress=100, error=None)
        try:
            await db.consume_quota(int(job.get("admin_id") or 0), 1)
        except Exception:
            pass
        await db.add_log("info", f"uploaded {key} {display_name}", job.get("admin_id", 0))
        log.info("done %s", key)

        # Update bulk status message if present
        if job.get("bulk_id") and job.get("status_chat_id") and job.get("status_message_id"):
            try:
                stats = await db.bulk_stats(job["bulk_id"])
                done_n = stats.get("done", 0)
                total_n = job.get("bulk_total") or (done_n + stats.get("pending", 0) + stats.get("running", 0) + stats.get("failed", 0))
                text = (
                    f"<blockquote><b>{sc('bulk progress')}</b></blockquote>\n"
                    f"<b>{title}</b>\n"
                    f"<b>{sc('done')}:</b> {done_n}/{total_n}\n"
                    f"<b>{sc('failed')}:</b> {stats.get('failed', 0)} · "
                    f"<b>{sc('pending')}:</b> {stats.get('pending', 0) + stats.get('running', 0)}"
                )
                await edit_msg(bot, job["status_chat_id"], job["status_message_id"], text)
            except Exception:
                pass

    except Exception as e:
        log.exception("job %s fail", key)
        err = str(e)[:500]
        # If cancel was requested during failure path, mark cancelled
        if await db.is_cancel_requested(key):
            await db.update_job(key, status="cancelled", error="cancelled by admin")
            await broadcast_status(bot, job, status_html(ch, title, "cancelled", 0, bulk=bulk))
        else:
            await db.update_job(key, status="failed", error=err)
            await db.add_log("error", f"job {key}: {e}", job.get("admin_id", 0))
            await broadcast_status(bot, job, status_html(ch, title, "failed", 0, bulk=bulk))
            try:
                if job.get("admin_id"):
                    await bot.send_message(
                        job["admin_id"],
                        f"<b>{sc('upload failed')}</b>\n<code>{title}</code> ch {ch}\n<code>{err}</code>",
                        parse_mode=ParseMode.HTML,
                    )
            except Exception:
                pass


async def loop() -> None:
    await db.connect()
    bot = Bot(token=BOT_TOKEN)
    log.info("worker up")
    sem = asyncio.Semaphore(MAX_CONCURRENT)

    # Recover stuck jobs on startup
    try:
        n = await db.recover_stuck_jobs()
        if n:
            log.info("recovered %s stuck jobs", n)
    except Exception as e:
        log.warning("stuck recovery: %s", e)

    async def one(j):
        async with sem:
            await process(bot, j)

    while True:
        try:
            # Periodic stuck recovery
            try:
                await db.recover_stuck_jobs()
            except Exception:
                pass

            try:
                await flush_logs_to_channel(bot)
            except Exception:
                pass
            jobs = await db.claim_pending_jobs(MAX_CONCURRENT)
            if jobs:
                await asyncio.gather(*(one(j) for j in jobs))
            else:
                await asyncio.sleep(3)
        except Exception as e:
            log.exception("loop: %s", e)
            await asyncio.sleep(5)


async def run_worker() -> None:
    """Called from main.py background task."""
    await loop()


if __name__ == "__main__":
    asyncio.run(loop())
