"""Start / home panel — clean UI, single owner by user id."""
from telegram import InlineKeyboardMarkup
from Manhwaflare.config import APP_VERSION, OWNER_ID, SUPPORT_GROUP, SUPPORT_CHANNEL
from Manhwaflare.text import sc
from Manhwaflare.ui.keyboards import btn, url_btn


def start_caption(user, is_owner: bool, plan_name: str = "Free", daily: str = "") -> str:
    name = (user.first_name if user else "user") or "user"
    daily_line = f"\n{sc('today')}: {daily}" if daily else ""
    return (
        f"<blockquote>"
        f"<b>{sc('welcome')} {name}</b>\n"
        f"{sc('your manhwa pdf companion')}"
        f"</blockquote>\n"
        f"<blockquote>"
        f"<b>{sc('plan')}:</b> {plan_name}{daily_line}\n"
        f"<b>{sc('version')}:</b> {APP_VERSION}"
        f"</blockquote>\n"
        f"<blockquote><b>{sc('tap a button below')}</b></blockquote>"
    )


def main_kb(is_owner: bool = False, is_admin: bool = False) -> InlineKeyboardMarkup:
    ch = SUPPORT_CHANNEL.lstrip("@")
    grp = SUPPORT_GROUP
    if grp and not grp.startswith("http"):
        grp = f"https://t.me/{grp.lstrip('@')}"

    # Owner = label only, opens profile by user id (no username)
    owner_btn = url_btn(sc("owner"), f"tg://user?id={OWNER_ID}")

    rows = [
        [
            btn(sc("search"), "p:search", "success"),
            btn(sc("trending"), "p:trending", "primary"),
        ],
        [
            btn(sc("help"), "p:help", "primary"),
            btn(sc("settings"), "p:settings", "primary"),
        ],
        [btn(sc("more"), "p:more", "success")],
        [owner_btn],
        [
            url_btn(sc("support channel"), f"https://t.me/{ch}"),
            url_btn(sc("support group"), grp),
        ],
    ]
    if is_admin or is_owner:
        rows.append([btn(sc("admin"), "p:adminmenu", "danger")])
    return InlineKeyboardMarkup(rows)
