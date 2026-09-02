# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""ManhwaFlare Bot — entrypoint"""
from __future__ import annotations
import logging
import sys

from telegram import Update, BotCommand, MenuButtonCommands
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, InlineQueryHandler,
    MessageHandler, ChatMemberHandler, filters, ContextTypes,
)
from telegram.error import RetryAfter, TimedOut, NetworkError

from Manhwaflare.config import BOT_TOKEN, OWNER_ID, APP_VERSION
from Manhwaflare import db
from Manhwaflare.text import sc, mono
from Manhwaflare.handlers import commands as _cmds
cmd_start = _cmds.cmd_start
cmd_ping = _cmds.cmd_ping
cmd_search = _cmds.cmd_search
cmd_ai_vid = _cmds.cmd_ai_vid
cmd_addch = _cmds.cmd_addch
cmd_addadmin = _cmds.cmd_addadmin
cmd_rmadmin = _cmds.cmd_rmadmin
cmd_pip = _cmds.cmd_pip
cmd_help = _cmds.cmd_help
cmd_premium = _cmds.cmd_premium
cmd_profile = _cmds.cmd_profile
cmd_trending = _cmds.cmd_trending
cmd_myjobs = _cmds.cmd_myjobs
cmd_broadcast = _cmds.cmd_broadcast
cmd_setplan = _cmds.cmd_setplan
cmd_stats = _cmds.cmd_stats
from Manhwaflare.handlers.callbacks import on_panel
from Manhwaflare.handlers.text_input import on_text
from Manhwaflare.handlers.misc import on_inline, on_my_chat_member
from Manhwaflare.plugins import load_all, COMMANDS as PLUGIN_COMMANDS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger("mf")

for _name in (
    "httpx", "httpcore", "telegram", "telegram.ext", "telegram.bot",
    "telegram.ext.Application", "telegram.ext.ExtBot",
    "aiohttp", "aiohttp.access", "asyncio", "urllib3",
):
    logging.getLogger(_name).setLevel(logging.WARNING)


async def _run_worker_bg() -> None:
    from Manhwaflare.worker import run_worker
    await run_worker()


async def post_init(app: Application) -> None:
    await db.connect()
    try:
        from Manhwaflare.mtproto import mtproto_enabled, get_client
        if mtproto_enabled():
            await get_client()
            log.info("MTProto enabled (large uploads)")
        else:
            log.info("MTProto off — set API_ID + API_HASH for ~2GB uploads")
    except Exception as e:
        log.warning("MTProto init: %s", e)
    await db.set_setting("owner_id", OWNER_ID)
    cmds = [
        BotCommand("start", "Home panel"),
        BotCommand("search", "Search manhwa"),
        BotCommand("trending", "Trending titles"),
        BotCommand("aivid", "AI animation videos"),
        BotCommand("premium", "Plans & prices"),
        BotCommand("profile", "Your plan & quota"),
        BotCommand("myjobs", "Your upload jobs"),
        BotCommand("help", "Help & commands"),
        BotCommand("ping", "Latency check"),
        BotCommand("broadcast", "Admin: broadcast"),
        BotCommand("addch", "Admin: add channel"),
        BotCommand("setplan", "Owner: set user plan"),
        BotCommand("stats", "Owner: bot stats"),
        BotCommand("addadmin", "Owner: add admin"),
        BotCommand("rmadmin", "Owner: remove admin"),
        BotCommand("random", "Random title"),
        BotCommand("favs", "Favorites"),
        BotCommand("history", "Activity history"),
        BotCommand("top", "Leaderboard"),
        BotCommand("queue", "Queue status"),
        BotCommand("bonus", "Daily bonus"),
        BotCommand("ref", "Referral code"),
        BotCommand("report", "Report issue"),
        BotCommand("last", "Last upload"),
        BotCommand("cancel", "Cancel my jobs"),
        BotCommand("about", "About"),
        BotCommand("sources", "Sources list"),
        BotCommand("id", "Your Telegram ID"),
        BotCommand("setcap", "Caption tag"),
        BotCommand("feedback", "Send feedback"),
        BotCommand("uptime", "Bot status"),
        BotCommand("howto", "How to use"),
    ]
    await app.bot.set_my_commands(cmds)
    try:
        await app.bot.set_chat_menu_button(menu_button=MenuButtonCommands())
    except Exception:
        pass
    try:
        await app.bot.set_my_description(
            description=(
                "ManhwaFlare — search manhwa, build PDF chapters, upload to channels.\n"
                "Multi-source manhwa PDF bot."
            )[:512]
        )
        await app.bot.set_my_short_description(
            short_description="Manhwa PDF uploader · Free & Premium"[:120]
        )
    except Exception as e:
        log.warning("set description: %s", e)
    me = await app.bot.get_me()
    log.info("bot @%s v%s", me.username, APP_VERSION)
    await db.add_log("info", f"started @{me.username} v{APP_VERSION}")
    # schedule on running loop (avoid PTBUserWarning in post_init)
    import asyncio
    asyncio.create_task(_start_health_server())
    asyncio.create_task(_run_worker_bg())
    log.info("upload worker started")


async def post_shutdown(app: Application) -> None:
    try:
        from Manhwaflare.mtproto import stop_client
        await stop_client()
    except Exception:
        pass
    await db.close()


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    err_obj = context.error
    log.error("handler error", exc_info=err_obj)
    err = str(err_obj)[:280]
    try:
        await db.add_log("error", err)
    except Exception:
        pass
    if isinstance(err_obj, (TimedOut, NetworkError, RetryAfter)):
        return
    try:
        user = msg = None
        if isinstance(update, Update):
            user = update.effective_user
            msg = update.effective_message
            if not msg and update.callback_query is not None:
                msg = update.callback_query.message
        if user and msg and await db.is_admin(user.id):
            await msg.reply_text(f"<b>{sc('error')}</b>\n{mono(err)}", parse_mode="HTML")
    except Exception:
        pass


def build() -> Application:
    if not BOT_TOKEN:
        raise SystemExit("BOT_TOKEN required")
    if not OWNER_ID:
        raise SystemExit("OWNER_ID required")
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .concurrent_updates(True)
        .build()
    )
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("ping", cmd_ping))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("search", cmd_search))
    app.add_handler(CommandHandler("trending", cmd_trending))
    app.add_handler(CommandHandler("aivid", cmd_ai_vid))
    app.add_handler(CommandHandler("ai_vid", cmd_ai_vid))
    app.add_handler(CommandHandler("premium", cmd_premium))
    app.add_handler(CommandHandler("profile", cmd_profile))
    app.add_handler(CommandHandler("myjobs", cmd_myjobs))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("addch", cmd_addch))
    app.add_handler(CommandHandler("setplan", cmd_setplan))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("addadmin", cmd_addadmin))
    app.add_handler(CommandHandler("rmadmin", cmd_rmadmin))
    app.add_handler(CommandHandler("pip", cmd_pip))
    # plugins
    load_all()
    for name, handler, _desc in PLUGIN_COMMANDS:
        app.add_handler(CommandHandler(name, handler))
    app.add_handler(CallbackQueryHandler(on_panel, pattern=r"^p:"))
    app.add_handler(InlineQueryHandler(on_inline))
    app.add_handler(ChatMemberHandler(on_my_chat_member, ChatMemberHandler.MY_CHAT_MEMBER))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_text))
    app.add_error_handler(on_error)
    return app


async def _start_health_server() -> None:
    """Minimal HTTP /health for Render free web service (keeps PORT bound)."""
    import os
    port = int(os.getenv("PORT", "0") or 0)
    # Render sets PORT; Heroku worker usually has no need
    if not port and not os.getenv("RENDER"):
        return
    if not port:
        port = 10000
    try:
        from aiohttp import web
    except ImportError:
        log.warning("aiohttp missing — health server skipped")
        return

    async def health(_request):
        return web.Response(text="ok", content_type="text/plain")

    async def root(_request):
        return web.Response(text="ManhwaFlare online", content_type="text/plain")

    app_web = web.Application()
    app_web.router.add_get("/health", health)
    app_web.router.add_get("/", root)
    runner = web.AppRunner(app_web)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("health server on :%s", port)



def main() -> None:
    app = build()
    log.info("ManhwaFlare starting (polling) v%s", APP_VERSION)
    app.run_polling(drop_pending_updates=True, allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
