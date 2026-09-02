# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Navigation stack helpers."""
from __future__ import annotations

def nav_stack(context) -> list:
    st = context.user_data.get("nav_stack")
    if not isinstance(st, list) or not st:
        st = ["home"]
        context.user_data["nav_stack"] = st
    return st


def _norm_panel_key(key: str) -> str:
    """Collapse callback payloads into stable short panel ids for the stack."""
    k = (key or "home").strip()
    if k.startswith("p:"):
        k = k[2:]
    # dynamic → short names
    if k.startswith("msel:") or k.startswith("sel:"):
        return "sel"
    if k.startswith("fetch:") or k.startswith("chmore:") or k.startswith("ci:") or k.startswith("ch:"):
        return "chapters"
    if k.startswith("up2:") or k.startswith("up:") or k.startswith("fullch:"):
        return "channel"
    if k.startswith("full:"):
        return "sel"
    if k.startswith("srcpick:"):
        return "results"  # after pick we go to results; picker itself uses srcpick
    if k.startswith("tpl:"):
        return "sel"
    if k in ("srcagain",):
        return "srcpick"
    # keep simple names as-is
    simple = {
        "home", "help", "settings", "search", "srcpick", "results",
        "sel", "chapters", "channel", "admins", "channels", "trending",
        "pending", "logs", "sources", "pip", "update", "addch",
        "setcap", "setfile", "sethost", "autofetch",
    }
    if k in simple:
        return k
    # unknown long keys → don't pollute stack
    if ":" in k:
        return k.split(":", 1)[0]
    return k[:32] if k else "home"


def nav_enter(context, key: str) -> None:
    """Push short panel key. On restore (back), do NOT push anything."""
    if context.user_data.pop("_nav_restore", False):
        return  # critical: never mutate stack while restoring
    key = _norm_panel_key(key)
    st = nav_stack(context)
    if not st:
        st.append("home")
    if st[-1] != key:
        st.append(key)
    if len(st) > 16:
        context.user_data["nav_stack"] = st[-16:]
    else:
        context.user_data["nav_stack"] = st


def nav_reset(context) -> None:
    context.user_data["nav_stack"] = ["home"]
