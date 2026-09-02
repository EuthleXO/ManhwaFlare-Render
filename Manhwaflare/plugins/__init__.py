"""Plugins package — each feature in its own file."""
from __future__ import annotations
from typing import List, Callable

COMMANDS: List[tuple] = []
PANEL_ACTIONS: dict = {}


def register_command(name: str, handler: Callable, description: str = "") -> None:
    COMMANDS.append((name, handler, description))


def register_panel(action: str, handler: Callable) -> None:
    PANEL_ACTIONS[action] = handler


def load_all() -> None:
    from Manhwaflare.plugins import (
        random_title, favorites, history, leaderboard, report,
        queue_info, daily_bonus, referral, mirror_last, cancel_mine,
        about, sources_info, whoami, setcap, feedback, uptime, howto,
        notify_on, cleardata, mychannels, bookmarks, donate, speed,
        sources_status, quota, newchap, invites, canceljobs,
    )
    _ = (
        random_title, favorites, history, leaderboard, report,
        queue_info, daily_bonus, referral, mirror_last, cancel_mine,
        about, sources_info, whoami, setcap, feedback, uptime, howto,
        notify_on, cleardata, mychannels, bookmarks, donate, speed,
        sources_status, quota, newchap, invites, canceljobs,
    )
