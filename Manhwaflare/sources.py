# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Backward-compatible re-export — real code lives in bot/scrapers/."""
from Manhwaflare.scrapers import (
    SOURCES,
    SOURCE_BY_ID,
    multi_search,
    multi_trending,
    get_detail_any,
    get_images_any,
    format_filename,
)

__all__ = [
    "SOURCES",
    "SOURCE_BY_ID",
    "multi_search",
    "multi_trending",
    "get_detail_any",
    "get_images_any",
    "format_filename",
]
