# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Plain text message handler (await modes)."""
from __future__ import annotations
import asyncio
import sys
import logging

from telegram import InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from Manhwaflare import db
from Manhwaflare.config import CAPTION_TAG
from Manhwaflare.helpers import chapter_rows
from Manhwaflare.scrapers import SOURCES
from Manhwaflare.text import sc, mono
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit

log = logging.getLogger("mf.text")

from Manhwaflare.handlers.search import _show_source_picker

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    key = context.user_data.get("await")
    if not key:
        return
    text = update.message.text.strip()
    user = update.effective_user
    context.user_data.pop("await", None)
    if user:
        await db.ensure_user(user.id, user.username or "", user.first_name or "")

    if key == "setcap":
        tag = text[:64]
        await db.set_user_setting(user.id, "caption_tag", tag)
        await update.message.reply_text(f"<b>{sc('saved')}</b>\n<code>{tag}</code>", parse_mode="HTML")
        return

    if key == "feedback":
        from Manhwaflare.config import OWNER_IDS, OWNER_ID
        await db.add_log("feedback", text[:800], user.id if user else 0)
        body = f"<b>feedback</b>\nfrom <code>{user.id}</code>\n\n{text[:1500]}"
        for oid in set(OWNER_IDS) | ({OWNER_ID} if OWNER_ID else set()):
            try:
                await context.bot.send_message(oid, body, parse_mode="HTML")
            except Exception:
                pass
        await update.message.reply_text(sc("thanks for feedback"))
        return

    if key == "report":

        from Manhwaflare.config import OWNER_ID
        await db.add_log("report", text[:500], user.id if user else 0)
        try:
            if OWNER_ID:
                await context.bot.send_message(
                    OWNER_ID,
                    f"<b>report</b> from <code>{user.id}</code>\n{text[:1000]}",
                    parse_mode="HTML",
                )
        except Exception:
            pass
        await update.message.reply_text(sc("report sent — thanks"))
        return

    if key == "broadcast":

        if not await db.is_admin(user.id):
            await update.message.reply_text(sc("access denied"))
            return
        ids = await db.list_all_user_ids()
        ok = fail = 0
        status = await update.message.reply_text(f"{sc('broadcasting')} 0/{len(ids)}...")
        for i, uid in enumerate(ids):
            try:
                await context.bot.send_message(uid, text, parse_mode="HTML", disable_web_page_preview=True)
                ok += 1
            except Exception:
                fail += 1
            if i % 20 == 0:
                try:
                    await status.edit_text(f"{sc('broadcasting')} {i}/{len(ids)}...")
                except Exception:
                    pass
        await status.edit_text(f"<b>{sc('broadcast done')}</b>\nOK {ok} · fail {fail}", parse_mode="HTML")
        return

    if key == "setplan":
        if not await db.is_owner(user.id):
            await update.message.reply_text(sc("owner only"))
            return
        parts = text.split()
        if len(parts) < 2:
            await update.message.reply_text(f"{sc('usage')}: <code>123456 pro</code>", parse_mode="HTML")
            return
        try:
            target = int(parts[0])
        except ValueError:
            await update.message.reply_text(sc("invalid user id"))
            return
        plan = parts[1].lower()
        if plan not in ("free", "pro", "ultra", "max", "flare"):
            await update.message.reply_text(sc("invalid plan"))
            return
        await db.set_user_plan(target, plan, days=30)
        await update.message.reply_text(
            f"<b>{sc('plan set')}</b>\n<code>{target}</code> → <b>{plan}</b>",
            parse_mode="HTML",
        )
        return

    if key == "chapter_jump":
        detail = context.user_data.get("sel")
        if not detail:
            await update.message.reply_text(sc("session expired — open chapters again"))
            return
        chapters = detail.get("chapters") or []
        target = text.strip().replace("chapter", "").replace("ch", "").strip()
        # find best match
        hit_idx = None
        for i, ch in enumerate(chapters):
            num = str(ch.get("num") or "").strip()
            if num == target or num == text.strip():
                hit_idx = i
                break
        if hit_idx is None:
            for i, ch in enumerate(chapters):
                num = str(ch.get("num") or "")
                if num.startswith(target) or target in num:
                    hit_idx = i
                    break
        if hit_idx is None:
            await update.message.reply_text(
                f"{sc('chapter not found')}: <code>{text}</code>\n{sc('try again')}",
                parse_mode="HTML",
            )
            context.user_data["await"] = "chapter_jump"
            return
        # show page containing that chapter
        page_size = 20
        offset = (hit_idx // page_size) * page_size
        slug = detail.get("slug") or ""
        rows, _, _, total = chapter_rows(slug, chapters, offset, page_size)
        ch = chapters[hit_idx]
        msg = await update.message.reply_text(
            f"<b>{sc('select chapter')}</b>\n"
            f"<b>{detail.get('title')}</b>\n"
            f"<b>{sc('found')}:</b> ch {ch.get('num')}\n"
            f"<b>{sc('chapters')}:</b> {total}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(rows),
        )
        return

    if key == "addch":
        # treat plain id as /addch
        context.args = [text.split()[0]]
        await cmd_addch(update, context)
        return

    if key == "filename":
        await db.set_user_setting(user.id, "filename_template", text)
        await update.message.reply_text(
            f"<b>{sc('file name saved')}</b>\n<code>{text}</code>",
            parse_mode="HTML",
        )
        return

    if key == "caption":
        await db.set_user_setting(user.id, "caption_tag", text)
        await update.message.reply_text(f"{sc('caption updated')}: {mono(text)}", parse_mode="HTML")
    elif key == "host":
        await db.set_setting("scrape_host", text.rstrip("/"))
        await update.message.reply_text(f"{sc('host updated')}: {mono(text)}", parse_mode="HTML")
    elif key == "search":
        context.user_data["search_q"] = text
        # Source picker: All + 4 domains
        lines = [
            f"<b>{sc('search')}</b> · <code>{text}</code>",
            "",
            f"<b>{sc('choose source')}</b>",
            sc("all = every domain"),
            sc("or pick one domain"),
        ]
        rows = [[btn(sc("all sources"), "p:srcpick:all", "success")]]
        row = []
        for s in SOURCES:
            row.append(btn(sc(s["name"]), f"p:srcpick:{s['id']}", "primary"))
            if len(row) == 2:
                rows.append(row)
                row = []
        if row:
            rows.append(row)
        await update.message.reply_text(
            "\n".join(lines), parse_mode="HTML",
            reply_markup=back_kb(*rows),
        )
    elif key == "pip":
        if not await db.is_owner(user.id):
            await update.message.reply_text(sc("owner only"))
            return
        m = await update.message.reply_text(f"{sc('installing')} {mono(text)}...", parse_mode="HTML")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable, "-m", "pip", "install", "--upgrade", text,
                stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            )
            out, err = await proc.communicate()
            raw = ((out or b"").decode()[-1200:] + (err or b"").decode()[-400:])
            if proc.returncode == 0:
                await db.add_log("info", f"pip {text} ok", user.id)
                await m.edit_text(f"<b>{sc('installed')}</b>\n<pre>{raw[-1500:]}</pre>", parse_mode="HTML")
            else:
                await db.add_log("error", f"pip {text} fail", user.id)
                await m.edit_text(f"<b>{sc('failed')}</b>\n<pre>{raw[-1500:]}</pre>", parse_mode="HTML")
        except Exception as e:
            await m.edit_text(f"{sc('error')}: {mono(str(e))}", parse_mode="HTML")
