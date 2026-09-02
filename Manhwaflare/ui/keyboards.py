# ManhwaFlare UI keyboards
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from Manhwaflare.text import sc


def btn(text: str, data: str, style: str | None = None) -> InlineKeyboardButton:
    kwargs = {"text": text, "callback_data": data}
    if style:
        kwargs["style"] = style
    try:
        return InlineKeyboardButton(**kwargs)
    except TypeError:
        kwargs.pop("style", None)
        return InlineKeyboardButton(**kwargs)


def url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text=text, url=url)


def back_kb(*extra_rows) -> InlineKeyboardMarkup:
    rows = list(extra_rows) if extra_rows else []
    rows.append([
        btn(sc("« back"), "p:back", "danger"),
        btn(sc("home"), "p:home", "primary"),
    ])
    return InlineKeyboardMarkup(rows)
