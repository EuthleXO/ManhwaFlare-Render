# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""Scraper package — multi source search / detail / images."""
from Manhwaflare.scrapers.router import (
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
