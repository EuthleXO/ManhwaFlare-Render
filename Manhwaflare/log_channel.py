# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Push bot logs to Telegram log channel."""
from __future__ import annotations
import logging
from Manhwaflare import db
from Manhwaflare.config import LOG_CHANNEL_ID

log = logging.getLogger("mf.logch")


async def flush_logs_to_channel(bot) -> int:
    if not LOG_CHANNEL_ID or not bot:
        return 0
    items = await db.pop_log_queue(15)
    sent = 0
    for it in items:
        try:
            level = (it.get("level") or "info").upper()
            uid = it.get("user_id") or 0
            msg = it.get("message") or ""
            text = (
                f"<b>[{level}]</b>\n"
                f"<code>{msg[:1500]}</code>\n"
                f"uid: <code>{uid}</code>"
            )
            await bot.send_message(
                LOG_CHANNEL_ID, text, parse_mode="HTML",
                disable_web_page_preview=True,
            )
            sent += 1
        except Exception as e:
            log.debug("log channel: %s", e)
    return sent
