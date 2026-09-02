"""AI videos — list, high-quality download with progress, screenshots."""
from __future__ import annotations

import asyncio
import logging
import os
import re
import shutil
import tempfile
import time
from pathlib import Path

from telegram import InputFile, InputMediaPhoto
from telegram.ext import ContextTypes

from Manhwaflare.nav import nav_enter
from Manhwaflare.scrapers import aivideos as aivideos_mod
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit

log = logging.getLogger("mf.aivideo")

# Standard Bot API limit is 50MB. Local Bot API can go to 2GB via TELEGRAM_LOCAL_API.
MAX_BOT_BYTES = int(os.getenv("TG_MAX_FILE_MB", "49")) * 1024 * 1024
FFMPEG = shutil.which("ffmpeg") or "ffmpeg"
FFPROBE = shutil.which("ffprobe") or "ffprobe"


def _bar(pct: float, width: int = 12) -> str:
    pct = max(0.0, min(100.0, pct))
    filled = int(round(width * pct / 100))
    return "█" * filled + "░" * (width - filled)


def _fmt_mb(n: float) -> str:
    return f"{n / (1024 * 1024):.1f} MB"


def _fmt_speed(bps: float) -> str:
    if bps <= 0:
        return "—"
    if bps > 1024 * 1024:
        return f"{bps / (1024 * 1024):.1f} MB/s"
    return f"{bps / 1024:.0f} KB/s"


async def _show_ai_videos(q, context, page: int = 1) -> None:
    import aiohttp

    nav_enter(context, "aivideos")
    page = max(1, int(page or 1))
    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=30)) as session:
            data = await aivideos_mod.list_videos(session, page)
    except Exception as e:
        await panel_edit(q, f"<b>{sc('error')}</b>\n<code>{e}</code>", back_kb())
        return
    items = data.get("items") or []
    last = int(data.get("last_page") or 1)
    total = int(data.get("total") or len(items))
    context.user_data["ai_videos"] = items
    context.user_data["ai_page"] = page
    lines = [
        f"<blockquote><b>{sc('AI videos')}</b></blockquote>",
        f"<b>{sc('page')}:</b> {page}/{last} · <b>{sc('total')}:</b> {total}",
        "",
        sc("tap a video to download"),
    ]
    rows = []
    for i, v in enumerate(items[:24]):
        title = (v.get("title") or v.get("slug") or "?")[:40]
        rows.append([btn(sc(f"{title}")[:58], f"p:aiv:{i}", "primary")])
    nav = []
    if page > 1:
        nav.append(btn(sc("« prev"), f"p:aivp:{page - 1}", "primary"))
    if page < last:
        nav.append(btn(sc("next »"), f"p:aivp:{page + 1}", "primary"))
    if nav:
        rows.append(nav)
    await panel_edit(q, "\n".join(lines), back_kb(*rows))


async def _edit_progress(q, title: str, phase: str, pct: float, size_b: float = 0, speed: float = 0, extra: str = "") -> None:
    body = (
        f"<blockquote><b>{phase}</b></blockquote>\n"
        f"<b>{title[:50]}</b>\n"
        f"<code>{_bar(pct)}</code> <b>{pct:.0f}%</b>\n"
        f"<b>{sc('size')}:</b> {_fmt_mb(size_b)}\n"
        f"<b>{sc('speed')}:</b> {_fmt_speed(speed)}\n"
    )
    if extra:
        body += f"\n{extra}"
    try:
        await panel_edit(q, body, back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]))
    except Exception:
        pass


async def _probe_duration(path_or_url: str) -> float:
    try:
        proc = await asyncio.create_subprocess_exec(
            FFPROBE, "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", path_or_url,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.DEVNULL,
        )
        out, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
        return float((out or b"0").decode().strip() or 0)
    except Exception:
        return 0.0


async def _ffmpeg_with_progress(args: list, out_path: str, duration: float, q, title: str, phase: str) -> bool:
    """Run ffmpeg, parse -progress pipe:1 for % / speed."""
    try:
        if os.path.isfile(out_path):
            os.remove(out_path)
    except Exception:
        pass

    full = [FFMPEG, "-y", "-progress", "pipe:1", "-nostats"] + args
    try:
        proc = await asyncio.create_subprocess_exec(
            *full,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
    except FileNotFoundError:
        log.error("ffmpeg not found")
        return False

    out_time_ms = 0
    speed_x = 0.0
    last_ui = 0.0
    t0 = time.time()

    try:
        assert proc.stdout is not None
        while True:
            line = await proc.stdout.readline()
            if not line:
                break
            text = line.decode(errors="ignore").strip()
            if text.startswith("out_time_ms="):
                try:
                    out_time_ms = int(text.split("=", 1)[1])
                except ValueError:
                    pass
            elif text.startswith("speed="):
                m = re.search(r"([\d.]+)", text)
                if m:
                    speed_x = float(m.group(1))
            elif text == "progress=end":
                break

            now = time.time()
            if now - last_ui >= 1.2:
                last_ui = now
                pct = 0.0
                if duration > 0 and out_time_ms > 0:
                    pct = min(99.0, (out_time_ms / 1000.0) / duration * 100)
                size_b = os.path.getsize(out_path) if os.path.isfile(out_path) else 0
                # approximate bytes/sec from file growth
                elapsed = max(0.1, now - t0)
                bps = size_b / elapsed
                await _edit_progress(q, title, phase, pct, size_b, bps, extra=f"ffmpeg ×{speed_x:.1f}" if speed_x else "")
    except Exception as e:
        log.warning("progress read: %s", e)

    try:
        await asyncio.wait_for(proc.wait(), timeout=30)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()

    ok = proc.returncode == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 50_000
    return ok


async def _download_ai_video(q, context, slug: str, item: dict) -> None:
    import aiohttp

    try:
        async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
            detail = await aivideos_mod.get_video(session, slug)
    except Exception as e:
        await panel_edit(
            q, f"<b>{sc('error')}</b>\n<code>{e}</code>",
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )
        return
    if not detail:
        await panel_edit(q, sc("video not found"), back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]))
        return

    hls = detail.get("hls_url") or ""
    title = detail.get("title") or item.get("title") or slug
    manga = detail.get("manga_title") or ""
    eps = detail.get("episodes") or []

    if eps and len(eps) > 1 and not context.user_data.get("_aiv_force"):
        lines = [
            f"<blockquote><b>{manga or title}</b></blockquote>",
            f"<b>{sc('episodes')}:</b> {len(eps)}",
            sc("select episode to download"),
        ]
        rows = []
        for ep in eps[:20]:
            if not isinstance(ep, dict):
                continue
            es = str(ep.get("slug") or "")
            et = str(ep.get("title") or es)[:40]
            rows.append([btn(sc(et), f"p:aivep:{es}", "primary")])
        if hls:
            rows.insert(0, [btn(sc(f"download · {title[:30]}"), f"p:aivep:{slug}", "success")])
        await panel_edit(q, "\n".join(lines), back_kb(*rows, [btn(sc("AI videos"), "p:aivideos", "primary")]))
        return

    if not hls:
        await panel_edit(
            q,
            f"<b>{title}</b>\n{sc('no stream url')}\n<a href='{detail.get('page_url','')}'>open on site</a>",
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )
        return

    tmpdir = tempfile.mkdtemp(prefix="aiv_")
    out_path = os.path.join(tmpdir, f"{slug[:40]}.mp4")
    duration = await _probe_duration(hls)
    if duration <= 0:
        duration = 600.0

    await _edit_progress(q, title, f"› › {sc('downloading')} HQ", 1, 0, 0)

    # High quality attempts (prefer quality, only compress if over limit)
    attempts = [
        # HQ stream copy full
        {
            "phase": f"› › {sc('downloading')} HQ",
            "args": [
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", hls,
                "-c", "copy", "-bsf:a", "aac_adtstoasc",
                "-movflags", "+faststart",
                out_path,
            ],
        },
        # HQ re-encode 720p
        {
            "phase": f"› › {sc('encoding')} 720p",
            "args": [
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", hls,
                "-vf", "scale='min(1280,iw)':-2",
                "-c:v", "libx264", "-preset", "fast", "-crf", "20",
                "-c:a", "aac", "-b:a", "160k",
                "-movflags", "+faststart",
                out_path,
            ],
        },
        # Fit Telegram 50MB — 480p
        {
            "phase": f"› › {sc('compressing')} for Telegram",
            "args": [
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", hls,
                "-vf", "scale='min(854,iw)':-2",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "26",
                "-c:a", "aac", "-b:a", "96k",
                "-movflags", "+faststart",
                out_path,
            ],
        },
    ]

    ok = False
    size = 0
    for att in attempts:
        ok = await _ffmpeg_with_progress(att["args"], out_path, duration, q, title, att["phase"])
        if not ok:
            continue
        size = os.path.getsize(out_path)
        if size <= MAX_BOT_BYTES:
            break
        ok = False  # too big → next attempt

    # store for screenshots
    context.user_data["aiv_last"] = {
        "path": out_path if ok else "",
        "tmpdir": tmpdir,
        "title": title,
        "manga": manga,
        "slug": slug,
        "hls": hls,
        "page_url": detail.get("page_url") or "",
        "size": size,
    }

    cap = (
        f"<blockquote><b>{manga}</b></blockquote>\n"
        f"<b>{title}</b>\n"
        f"<b>{sc('size')}:</b> {_fmt_mb(size)}\n"
        f"<a href='{detail.get('page_url','')}'>source</a>"
    )[:1024]

    try:
        if ok and size <= MAX_BOT_BYTES:
            await _edit_progress(q, title, f"› › {sc('uploading')}", 95, size, 0)
            with open(out_path, "rb") as f:
                try:
                    await context.bot.send_video(
                        chat_id=q.message.chat_id,
                        video=InputFile(f, filename=f"{slug[:30]}.mp4"),
                        caption=cap,
                        parse_mode="HTML",
                        supports_streaming=True,
                    )
                except Exception:
                    f.seek(0)
                    await context.bot.send_document(
                        chat_id=q.message.chat_id,
                        document=InputFile(f, filename=f"{slug[:30]}.mp4"),
                        caption=cap,
                        parse_mode="HTML",
                    )
            # Keep file for screenshots briefly — copy to longer path
            shot_path = os.path.join(tmpdir, "for_shots.mp4")
            try:
                if out_path != shot_path:
                    shutil.copy2(out_path, shot_path)
                context.user_data["aiv_last"]["path"] = shot_path
            except Exception:
                pass

            await panel_edit(
                q,
                f"<blockquote><b>{sc('sent')}</b></blockquote>\n"
                f"<b>{title}</b>\n"
                f"<code>{_bar(100)}</code> <b>100%</b>\n"
                f"<b>{sc('size')}:</b> {_fmt_mb(size)}",
                back_kb(
                    [btn(sc("screenshots · 10"), f"p:aivshots:{slug[:40]}", "success")],
                    [btn(sc("AI videos"), "p:aivideos", "primary")],
                ),
            )
        else:
            await context.bot.send_message(
                q.message.chat_id,
                f"<blockquote><b>{manga or 'AI Video'}</b></blockquote>\n"
                f"<b>{title}</b>\n\n"
                f"{sc('file exceeds telegram bot limit')} ({MAX_BOT_BYTES // 1024 // 1024}MB)\n"
                f"<a href='{hls}'>stream m3u8</a>\n"
                f"<a href='{detail.get('page_url','')}'>open on site</a>",
                parse_mode="HTML",
                disable_web_page_preview=True,
            )
            await panel_edit(
                q,
                f"<b>{title}</b>\n{sc('could not fit bot upload limit')}",
                back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
            )
            # cleanup
            try:
                shutil.rmtree(tmpdir, ignore_errors=True)
            except Exception:
                pass
            context.user_data.pop("aiv_last", None)
    except Exception as e:
        log.exception("send aiv")
        await panel_edit(
            q, f"<b>{sc('error')}</b>\n<code>{e}</code>",
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )


async def _send_screenshots(q, context, slug: str) -> None:
    """Extract 10 screenshots from last downloaded video and send album."""
    info = context.user_data.get("aiv_last") or {}
    path = info.get("path") or ""
    title = info.get("title") or slug
    if not path or not os.path.isfile(path):
        await panel_edit(
            q, sc("video file expired — download again"),
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )
        return

    await panel_edit(q, f"<b>› › {sc('capturing screenshots')}...</b>\n<code>{title[:50]}</code>", back_kb())
    tmpdir = info.get("tmpdir") or tempfile.mkdtemp(prefix="aivs_")
    duration = await _probe_duration(path)
    if duration <= 0:
        duration = 60.0

    frames = []
    for i in range(10):
        # even spread, skip first/last 5%
        t = duration * (0.05 + 0.9 * i / 9)
        out = os.path.join(tmpdir, f"shot_{i:02d}.jpg")
        try:
            proc = await asyncio.create_subprocess_exec(
                FFMPEG, "-y", "-ss", f"{t:.2f}", "-i", path,
                "-frames:v", "1", "-q:v", "3", out,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
            await asyncio.wait_for(proc.wait(), timeout=60)
            if os.path.isfile(out) and os.path.getsize(out) > 1000:
                frames.append(out)
        except Exception as e:
            log.warning("shot %s: %s", i, e)

        pct = (i + 1) / 10 * 100
        await _edit_progress(q, title, f"› › {sc('screenshots')}", pct, 0, 0, extra=f"{i+1}/10")

    if not frames:
        await panel_edit(
            q, sc("could not extract screenshots"),
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )
        return

    # send as media groups (max 10)
    media = []
    files = []
    try:
        for i, fp in enumerate(frames[:10]):
            f = open(fp, "rb")
            files.append(f)
            media.append(InputMediaPhoto(f, caption=f"{title[:40]} · {i+1}/10" if i == 0 else None))
        await context.bot.send_media_group(chat_id=q.message.chat_id, media=media)
        await panel_edit(
            q,
            f"<blockquote><b>{sc('screenshots sent')}</b></blockquote>\n"
            f"<b>{title}</b>\n{len(frames)} {sc('frames')}",
            back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]),
        )
    except Exception as e:
        log.exception("shots send")
        await panel_edit(q, f"<b>{sc('error')}</b>\n<code>{e}</code>", back_kb([btn(sc("AI videos"), "p:aivideos", "primary")]))
    finally:
        for f in files:
            try:
                f.close()
            except Exception:
                pass
