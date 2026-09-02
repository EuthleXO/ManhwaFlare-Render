# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Premium plans — Free / Pro / Ultra / Max / Flare."""
from __future__ import annotations
from typing import Dict, Any

# plan_id -> limits & display
PLANS: Dict[str, Dict[str, Any]] = {
    "free": {
        "id": "free",
        "name": "Free",
        "price": "$0",
        "price_num": 0,
        "daily_limit": 5,
        "bulk": False,
        "bulk_max": 0,
        "ai_video": False,
        "priority": 0,
        "perks": [
            "5 chapters / day",
            "Single chapter upload only",
            "No full-series bulk",
            "No AI videos",
            "Standard queue",
        ],
    },
    "pro": {
        "id": "pro",
        "name": "Pro",
        "price": "$2.99 / mo",
        "price_num": 2.99,
        "daily_limit": 40,
        "bulk": False,
        "bulk_max": 0,
        "ai_video": True,
        "priority": 1,
        "perks": [
            "40 chapters / day",
            "Single chapter upload",
            "AI videos unlocked",
            "Faster support",
        ],
    },
    "ultra": {
        "id": "ultra",
        "name": "Ultra",
        "price": "$5.99 / mo",
        "price_num": 5.99,
        "daily_limit": 150,
        "bulk": True,
        "bulk_max": 50,
        "ai_video": True,
        "priority": 2,
        "perks": [
            "150 chapters / day",
            "Bulk full-series (max 50 ch)",
            "AI videos",
            "Priority queue",
        ],
    },
    "max": {
        "id": "max",
        "name": "Max",
        "price": "$9.99 / mo",
        "price_num": 9.99,
        "daily_limit": 500,
        "bulk": True,
        "bulk_max": 9999,
        "ai_video": True,
        "priority": 3,
        "perks": [
            "500 chapters / day",
            "Unlimited bulk series",
            "AI videos",
            "High priority queue",
        ],
    },
    "flare": {
        "id": "flare",
        "name": "Flare",
        "price": "$14.99 / mo",
        "price_num": 14.99,
        "daily_limit": 99999,
        "bulk": True,
        "bulk_max": 99999,
        "ai_video": True,
        "priority": 4,
        "perks": [
            "Unlimited chapters",
            "Unlimited bulk",
            "AI videos",
            "Top priority + early features",
        ],
    },
}

PLAN_ORDER = ["free", "pro", "ultra", "max", "flare"]


def get_plan(plan_id: str | None) -> Dict[str, Any]:
    pid = (plan_id or "free").lower().strip()
    return PLANS.get(pid) or PLANS["free"]


def can_bulk(plan_id: str | None) -> bool:
    return bool(get_plan(plan_id).get("bulk"))


def bulk_max(plan_id: str | None) -> int:
    return int(get_plan(plan_id).get("bulk_max") or 0)


def daily_limit(plan_id: str | None) -> int:
    return int(get_plan(plan_id).get("daily_limit") or 5)


def can_ai(plan_id: str | None) -> bool:
    return bool(get_plan(plan_id).get("ai_video"))
