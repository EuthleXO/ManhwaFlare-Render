"""ManhwaFlare Bot — config"""
import os
import re
import sys
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()

# MTProto (Pyrogram) — large file upload up to ~2GB
API_ID = int(os.getenv("API_ID", "0") or 0)
API_HASH = os.getenv("API_HASH", "").strip()
USE_MTPROTO = bool(API_ID and API_HASH and BOT_TOKEN)

# Single owner only
_env_owner = int(os.getenv("OWNER_ID", "0") or 0)
OWNER_ID = _env_owner or 8681820826
OWNER_IDS = {OWNER_ID}

OWNER_USERNAME = os.getenv("OWNER_USERNAME", "").lstrip("@")
OWNER_DISPLAY = []
if OWNER_USERNAME:
    OWNER_DISPLAY = [{"id": OWNER_ID, "username": OWNER_USERNAME, "label": "Owner"}]
else:
    OWNER_DISPLAY = [{"id": OWNER_ID, "username": "", "label": "Owner"}]

SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", "https://t.me/+CZCfHr3AHKUwNTJk").strip()
SUPPORT_CHANNEL = os.getenv("SUPPORT_CHANNEL", "DragonByte_network").lstrip("@")
LOG_CHANNEL_ID = int(os.getenv("LOG_CHANNEL_ID", "-1003915347751") or -1003915347751)

MONGODB_URI = os.getenv("MONGODB_URI", "").strip()
DATABASE_NAME = os.getenv("DATABASE_NAME", "manhwaflare").strip()
SCRAPE_HOST = os.getenv("SCRAPE_HOST", "https://manhwa18.net").rstrip("/")
SCRAPE_HOST_NET = os.getenv("SCRAPE_HOST_NET", "https://manhwa18.net").rstrip("/")
SCRAPE_SOURCE = os.getenv("SCRAPE_SOURCE", "net")
CAPTION_TAG = os.getenv("CAPTION_TAG", "").strip()
FILENAME_TEMPLATE = os.getenv("FILENAME_TEMPLATE", "{chapter_num} ⌯ {manga_title} [{tag}]")
PORT = int(os.getenv("PORT", "10000") or 10000)
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
UPSTREAM_REPO = "https://github.com/EuthleXO/ManhwaFlare-Render.git"
REPO_URL = "https://github.com/EuthleXO/ManhwaFlare-Render"
APP_VERSION = "v1.0"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TMP_DIR = os.path.join(BASE_DIR, "tmp")
os.makedirs(TMP_DIR, exist_ok=True)
MAX_CONCURRENT = 2
UPLOAD_RATE = 15
PAGE_SIZE = 8

START_IMAGES = [
    "https://i.postimg.cc/PrNm8t2G/03ee94efd955d189e970a5de76a9000f.jpg",
    "https://i.postimg.cc/c46Q8sXG/0bc8ecc0951cf0c579b769f9c71fef03.jpg",
    "https://i.postimg.cc/NfL1rgbd/21ce8df86f292cb7fc56c6b7cab6242c.jpg",
]

COPYRIGHT = ""


def validate_mongodb_uri(uri: str) -> str:
    """Return error message or empty string if OK."""
    if not uri:
        return (
            "MONGODB_URI is empty. Set it in Render Environment.\n"
            "Atlas → Connect → Drivers → copy full URI.\n"
            "Example: mongodb+srv://USER:PASS@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority"
        )
    # placeholder / incomplete hosts
    bad = (
        "cluster.mongodb.net",
        "cluster0.mongodb.net",
        "<cluster>",
        "xxxxx.mongodb.net",
        "yourcluster",
    )
    low = uri.lower()
    for b in bad:
        if b in low and "cluster0." not in low.replace(b, ""):
            # allow real cluster0.abc12.mongodb.net — only flag bare cluster.mongodb.net
            pass
    if re.search(r"@cluster\.mongodb\.net\b", low) or re.search(r"@cluster0\.mongodb\.net\b", low):
        return (
            "MONGODB_URI host is invalid (placeholder cluster.mongodb.net).\n"
            "Open MongoDB Atlas → Connect → Drivers → copy the real hostname "
            "like cluster0.ab1cd.mongodb.net (NOT just cluster.mongodb.net)."
        )
    if "mongodb" not in low:
        return "MONGODB_URI must start with mongodb:// or mongodb+srv://"
    return ""


_mongo_err = validate_mongodb_uri(MONGODB_URI)
if _mongo_err and not os.getenv("SKIP_MONGO_CHECK"):
    # print clear message early (Render logs)
    print("=" * 60, file=sys.stderr)
    print("MONGODB_URI ERROR:", file=sys.stderr)
    print(_mongo_err, file=sys.stderr)
    print("=" * 60, file=sys.stderr)
