# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Shared UI helpers: captions, chapter rows, poster panel, FakeQuery."""
from __future__ import annotations
import asyncio
import logging
from io import BytesIO

from telegram import InlineKeyboardMarkup, InputFile, InputMediaPhoto
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

try:
    from telegram import ReactionTypeEmoji
except ImportError:
    ReactionTypeEmoji = None

from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, back_kb
from Manhwaflare.ui.wait import panel_edit, wait_html, _edit_raw

log = logging.getLogger("mf.helpers")

async def send_action(context: ContextTypes.DEFAULT_TYPE, chat_id: int, action: str = ChatAction.TYPING) -> None:
    try:
        await context.bot.send_chat_action(chat_id=chat_id, action=action)
    except Exception:
        pass


async def react_ok(context: ContextTypes.DEFAULT_TYPE, chat_id: int, message_id: int) -> None:
    """Best-effort thumbs-up reaction (Bot API message reactions)."""
    if ReactionTypeEmoji is None:
        return
    try:
        await context.bot.set_message_reaction(
            chat_id=chat_id,
            message_id=message_id,
            reaction=[ReactionTypeEmoji(emoji="👍")],
        )
    except Exception:
        pass



# ── caption templates (from PHP mf_build_caption) ─────────

TEMPLATES = {
    "manhwa": {
        "classic": "Classic Quote",
        "compact": "Compact Stats",
        "story": "Story Focus",
        "minimal": "Minimal",
        "rich": "Rich Info",
    },
}

def synopsis_block(synopsis: str) -> str:
    import html as H
    synopsis = (synopsis or "").strip()
    if not synopsis:
        return "<blockquote><b>‣ SYNOPSIS</b>\n➟ N/A</blockquote>"
    esc = H.escape(synopsis)
    if len(synopsis) > 280:
        return f"<blockquote expandable><b>‣ SYNOPSIS</b>\n➟ {esc}</blockquote>"
    return f"<blockquote><b>‣ SYNOPSIS</b>\n➟ {esc}</blockquote>"


def build_caption(info: dict, ctype: str = "manhwa", tpl: str | None = None) -> str:
    import html as H
    tpl = (tpl or "classic").lower()
    title = info.get("title") or "Unknown"
    score = info.get("score") or "—"
    status = info.get("status") or "—"
    genres = info.get("genres") or []
    if isinstance(genres, list):
        genres = ", ".join(genres) if genres else "—"
    synopsis = info.get("synopsis") or ""
    chapters = info.get("chapters_count") or info.get("chapters") or "—"
    if isinstance(chapters, list):
        chapters = len(chapters)
    year = info.get("year") or ""

    title_block = f"<blockquote><b>{H.escape(str(title))}</b></blockquote>"
    syn = synopsis_block(synopsis)
    score_s = f"{score}%" if isinstance(score, (int, float)) or (isinstance(score, str) and score.replace(".","").isdigit()) else str(score)

    if ctype == "compact":
        stats = f"» {score_s} · {status} · Ch {chapters}\n» {genres}"
        return f"{title_block}\n\n{stats}\n\n{syn}"
    if tpl == "minimal":
        return f"{title_block}\n» Manhwa · {score_s}\n\n{syn}"
    if tpl == "story":
        return f"{title_block}\n\n{syn}\n\n» {genres}"
    # classic / rich
    stats = (
        f"» Type: Manhwa\n"
        f"» Average Rating: {score_s}\n"
        f"» Status: {status}\n"
        f"» Chapters: {chapters}\n"
        f"» Genres: {genres}"
    )
    if tpl == "rich" and year:
        stats += f"\n» Year: {year}"
    return f"{title_block}\n\n{stats}\n\n{syn}"





class FakeQuery:
    """Minimal CallbackQuery-compatible adapter for command → panel flows."""
    def __init__(self, message, from_user, data: str = ""):
        self.message = message
        self.from_user = from_user
        self.effective_user = from_user  # alias — some code paths expect this
        self.data = data
        self.id = "0"
        self.chat_instance = "0"

    async def answer(self, *a, **k):
        return None

    async def edit_message_text(self, *a, **k):
        return await self.message.edit_text(*a, **k)

    async def edit_message_caption(self, *a, **k):
        return await self.message.edit_caption(*a, **k)

    async def edit_message_media(self, *a, **k):
        return await self.message.edit_media(*a, **k)

    async def edit_message_reply_markup(self, *a, **k):
        return await self.message.edit_reply_markup(*a, **k)


async def panel_poster(q, context, poster_url: str, text: str, kb: InlineKeyboardMarkup) -> None:
    """Show manhwa poster as photo panel; fallback to text edit."""
    import aiohttp
    from io import BytesIO
    from telegram import InputFile, InputMediaPhoto

    # wait frame first
    try:
        await _edit_raw(q, wait_html(), None)
        await asyncio.sleep(0.2)
    except Exception:
        pass

    text = (text or "")[:1024]
    data = None
    if poster_url:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    poster_url,
                    timeout=aiohttp.ClientTimeout(total=15),
                    headers={"User-Agent": "Mozilla/5.0", "Referer": "https://manhwa18.net/"},
                ) as resp:
                    if resp.status == 200:
                        data = await resp.read()
        except Exception as e:
            log.warning("poster download: %s", e)

    try:
        if data and len(data) > 1000:
            media = InputMediaPhoto(
                media=InputFile(BytesIO(data), filename="poster.jpg"),
                caption=text,
                parse_mode="HTML",
            )
            # If current message has photo, edit media; else send new
            if q.message and q.message.photo:
                await q.edit_message_media(media=media, reply_markup=kb)
            else:
                try:
                    await q.message.delete()
                except Exception:
                    pass
                await context.bot.send_photo(
                    chat_id=q.message.chat_id,
                    photo=InputFile(BytesIO(data), filename="poster.jpg"),
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=kb,
                )
            return
    except Exception as e:
        log.warning("panel_poster: %s", e)

    await panel_edit(q, text, kb)


def _short_slug(slug: str, max_len: int = 28) -> str:
    """Keep callback_data under Telegram 64-byte limit."""
    return (slug or "")[:max_len]


def chapter_rows(slug: str, chapters: list, offset: int = 0, page_size: int = 20, latest_first: bool = True) -> tuple:
    """Build chapter buttons. Default: latest chapters first. Indices map into display list."""
    total = len(chapters)
    # display order: newest → oldest when latest_first
    if latest_first:
        display = list(reversed(chapters))
    else:
        display = list(chapters)
    # store mapping on context is done by caller via sel chapters; global_idx is index into display
    offset = max(0, min(offset, max(0, total - 1))) if total else 0
    chunk = display[offset:offset + page_size]
    ss = _short_slug(slug)
    rows = []
    row = []
    for idx, ch in enumerate(chunk):
        disp_idx = offset + idx  # index in display list
        num = str(ch.get("num", "?"))[:10]
        # encode display index; handler resolves via reversed list
        row.append(btn(sc(f"ch {num}"), f"p:ci:{ss}:{disp_idx}", "primary"))
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([btn(sc("add full series"), f"p:full:{ss}", "success")])
    has_prev = offset > 0
    has_next = offset + page_size < total
    nav = []
    if has_prev:
        nav.append(btn(sc("« prev"), f"p:chmore:{ss}:{max(0, offset - page_size)}", "primary"))
    nav.append(btn(sc("« back"), "p:back", "danger"))
    nav.append(btn(sc("home"), "p:home", "primary"))
    if has_next:
        nav.append(btn(sc("next »"), f"p:chmore:{ss}:{offset + page_size}", "primary"))
    if nav:
        rows.append(nav)
    return rows, has_prev, has_next, total
