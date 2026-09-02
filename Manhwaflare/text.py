# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Small-caps — exact font map provided by user"""

# ᴀ ʙ ᴄ ᴅ ᴇ ꜰ ɢ ʜ ɪ ᴊ ᴋ ʟ ᴍ
# ɴ ᴏ ᴘ q ʀ ꜱ ᴛ ᴜ ᴠ ᴡ x ʏ ᴢ
_SC = {
    "a": "ᴀ", "b": "ʙ", "c": "ᴄ", "d": "ᴅ", "e": "ᴇ", "f": "ꜰ",
    "g": "ɢ", "h": "ʜ", "i": "ɪ", "j": "ᴊ", "k": "ᴋ", "l": "ʟ",
    "m": "ᴍ", "n": "ɴ", "o": "ᴏ", "p": "ᴘ", "q": "q", "r": "ʀ",
    "s": "ꜱ", "t": "ᴛ", "u": "ᴜ", "v": "ᴠ", "w": "ᴡ", "x": "x",
    "y": "ʏ", "z": "ᴢ",
}


def sc(t: str) -> str:
    if not t:
        return t
    return "".join(_SC.get(c.lower(), c) for c in t)


def bsc(t: str) -> str:
    return f"<b>{sc(t)}</b>"


def mono(t: str) -> str:
    return f"<code>{t}</code>"


def hdr(t: str) -> str:
    """Title only — no box borders."""
    return f"<b>{sc(t)}</b>"


def ftr() -> str:
    """No footer box."""
    return ""


def bar(pct: int, w: int = 10) -> str:
    pct = max(0, min(100, pct))
    f = int(w * pct / 100)
    return f"[{'█' * f}{'░' * (w - f)}] {pct}%"
