# © ManhwaFlare — @flexyy | dragonByte | @dragonByte_Network
# Do not remove credits
"""MongoDB async layer — fixed: atomic job claim, stuck recovery, cancel support"""
from __future__ import annotations
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional, List, Dict

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from pymongo import ASCENDING, DESCENDING, IndexModel, ReturnDocument

from Manhwaflare.config import MONGODB_URI, DATABASE_NAME, OWNER_ID, OWNER_IDS, LOG_CHANNEL_ID, validate_mongodb_uri

logger = logging.getLogger(__name__)
_client: Optional[AsyncIOMotorClient] = None
_db: Optional[AsyncIOMotorDatabase] = None

# Jobs stuck in "running" longer than this are auto-failed / requeued
STUCK_MINUTES = 45
MAX_RETRIES = 2


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def connect() -> AsyncIOMotorDatabase:
    global _client, _db
    if _db is not None:
        return _db
    err = validate_mongodb_uri(MONGODB_URI)
    if err:
        logger.error("invalid MONGODB_URI:\n%s", err)
        raise RuntimeError(err)
    try:
        _client = AsyncIOMotorClient(
            MONGODB_URI,
            serverSelectionTimeoutMS=12000,
            connectTimeoutMS=12000,
        )
        _db = _client[DATABASE_NAME]
        # force DNS + auth check early
        await _client.admin.command("ping")
        await _indexes()
        logger.info("mongodb connected db=%s", DATABASE_NAME)
        return _db
    except Exception as e:
        msg = str(e)
        if "DNS" in msg or "does not exist" in msg or "SRV" in msg:
            hint = (
                "MongoDB DNS/SRV failed. Your MONGODB_URI hostname is wrong.\n"
                "Atlas → Connect → copy URI with real host e.g. cluster0.ab12cd.mongodb.net\n"
                "Also allow 0.0.0.0/0 under Network Access for Render."
            )
            logger.error("%s\n%s", hint, msg)
            raise RuntimeError(hint) from e
        raise


async def close() -> None:
    global _client, _db
    if _client:
        _client.close()
    _client = _db = None


def get() -> AsyncIOMotorDatabase:
    if _db is None:
        raise RuntimeError("db not connected")
    return _db


async def _indexes() -> None:
    d = get()
    await d.admins.create_indexes([IndexModel([("user_id", ASCENDING)], unique=True)])
    await d.settings.create_indexes([IndexModel([("key", ASCENDING)], unique=True)])
    await d.channels.create_indexes([IndexModel([("chat_id", ASCENDING)], unique=True)])
    await d.jobs.create_indexes([
        IndexModel([("status", ASCENDING), ("created_at", ASCENDING)]),
        IndexModel([("job_key", ASCENDING)], unique=True),
        IndexModel([("status", ASCENDING), ("updated_at", ASCENDING)]),
        IndexModel([("bulk_id", ASCENDING)]),
    ])
    await d.logs.create_indexes([IndexModel([("created_at", DESCENDING)])])
    await d.manhwa_cache.create_indexes([
        IndexModel([("slug", ASCENDING)], unique=True),
        IndexModel([("title", "text")]),
    ])
    await d.users.create_indexes([
        IndexModel([("user_id", ASCENDING)], unique=True),
        IndexModel([("plan", ASCENDING)]),
    ])
    await d.favorites.create_indexes([
        IndexModel([("user_id", ASCENDING), ("slug", ASCENDING)], unique=True),
    ])
    await d.history.create_indexes([
        IndexModel([("user_id", ASCENDING), ("created_at", DESCENDING)]),
    ])
    await d.referrals.create_indexes([
        IndexModel([("code", ASCENDING)], unique=True),
        IndexModel([("owner_id", ASCENDING)]),
    ])


# settings
async def get_setting(key: str, default: Any = None) -> Any:
    doc = await get().settings.find_one({"key": key})
    return doc["value"] if doc else default


async def set_setting(key: str, value: Any) -> None:
    await get().settings.update_one(
        {"key": key}, {"$set": {"value": value, "updated_at": utcnow()}}, upsert=True
    )


async def get_user_setting(uid: int, key: str, default: str = "") -> str:
    """Per-admin setting stored as settings key 'u:{uid}:{key}'."""
    v = await get_setting(f"u:{uid}:{key}", None)
    if v is not None and v != "":
        return str(v)
    return str(await get_setting(key, default) or default)


async def set_user_setting(uid: int, key: str, value: str) -> None:
    await set_setting(f"u:{uid}:{key}", value)


async def all_settings() -> Dict[str, Any]:
    return {d["key"]: d["value"] async for d in get().settings.find({})}


# auth
async def is_owner(uid: int) -> bool:
    return int(uid) in OWNER_IDS or int(uid) == int(OWNER_ID)


async def is_admin(uid: int) -> bool:
    if int(uid) in OWNER_IDS or int(uid) == int(OWNER_ID):
        return True
    return await get().admins.find_one({"user_id": uid, "status": "active"}) is not None


async def add_admin(uid: int, by: int, username: str = "") -> bool:
    if int(uid) in OWNER_IDS or int(uid) == int(OWNER_ID):
        return False
    await get().admins.update_one(
        {"user_id": uid},
        {"$set": {"user_id": uid, "username": username, "status": "active", "added_by": by, "added_at": utcnow()}},
        upsert=True,
    )
    return True


async def rm_admin(uid: int) -> bool:
    return (await get().admins.delete_one({"user_id": uid})).deleted_count > 0


async def list_admins() -> List[Dict]:
    return await get().admins.find({"status": "active"}).sort("added_at", DESCENDING).to_list(100)


# channels
async def upsert_channel(chat_id: str, title: str = "", username: str = "",
                         chat_type: str = "channel", is_bot_admin: bool = False,
                         added_by: Optional[int] = None) -> None:
    u: Dict[str, Any] = {
        "title": title, "username": username, "type": chat_type,
        "is_bot_admin": is_bot_admin, "updated_at": utcnow(),
    }
    if added_by is not None:
        u["added_by"] = added_by
    await get().channels.update_one(
        {"chat_id": str(chat_id)},
        {"$set": u, "$setOnInsert": {"created_at": utcnow()}},
        upsert=True,
    )


async def get_channels(admin_only: bool = True, owner_id=None) -> List[Dict]:
    """owner_id set → only that user's channels. owner_id=None → all."""
    q: Dict[str, Any] = {}
    if admin_only:
        q["is_bot_admin"] = True
    if owner_id is not None:
        q["added_by"] = int(owner_id)
    return await get().channels.find(q).sort("title", ASCENDING).to_list(500)


async def count_channels(owner_id=None) -> int:
    q: Dict[str, Any] = {}
    if owner_id is not None:
        q["added_by"] = int(owner_id)
    return await get().channels.count_documents(q)


async def get_channel(chat_id: str) -> Optional[Dict]:
    return await get().channels.find_one({"chat_id": str(chat_id)})


async def rm_channel(chat_id: str) -> bool:
    return (await get().channels.delete_one({"chat_id": str(chat_id)})).deleted_count > 0


# jobs
async def create_job(data: Dict) -> str:
    import uuid
    key = data.get("job_key") or f"job_{utcnow().strftime('%Y%m%d_%H%M%S')}_{data.get('admin_id', 0)}_{uuid.uuid4().hex[:8]}"
    doc = {
        "job_key": key, "status": "pending", "admin_id": data["admin_id"],
        "manga_title": data.get("manga_title", ""), "chapter_num": data.get("chapter_num", ""),
        "slug": data.get("slug", ""), "poster": data.get("poster", ""),
        "chat_id": data.get("chat_id", ""), "channel_title": data.get("channel_title", ""),
        "caption": data.get("caption", ""), "chapter_url": data.get("chapter_url", ""),
        "progress": 0, "error": None, "created_at": utcnow(), "updated_at": utcnow(),
        "status_chat_id": data.get("status_chat_id"),
        "status_message_id": data.get("status_message_id"),
        "post_poster": bool(data.get("post_poster", False)),
        "detail_snapshot": data.get("detail_snapshot") or {},
        "bulk_id": data.get("bulk_id"),
        "bulk_index": data.get("bulk_index"),
        "bulk_total": data.get("bulk_total"),
        "synopsis": data.get("synopsis", ""),
        "score": data.get("score", ""),
        "genres": data.get("genres") or [],
        "status_text": data.get("status_text", ""),
        "source": data.get("source", ""),
        "kind": data.get("kind") or "Manhwa",
        "chapters_count": data.get("chapters_count") or "",
        "retries": int(data.get("retries") or 0),
        "cancel_requested": False,
    }
    await get().jobs.insert_one(doc)
    return key


async def update_job(key: str, **kw) -> None:
    kw["updated_at"] = utcnow()
    await get().jobs.update_one({"job_key": key}, {"$set": kw})


async def get_job(key: str) -> Optional[Dict]:
    return await get().jobs.find_one({"job_key": key})


async def claim_pending_jobs(limit: int = 5) -> List[Dict]:
    """Atomically claim up to `limit` pending jobs → status=running.
    Full-series (bulk_id) jobs run strictly one-by-one in bulk_index order.
    Non-bulk jobs may still run in parallel up to `limit`.
    """
    claimed: List[Dict] = []
    now = utcnow()
    # Running bulk ids — do not claim another chapter from same series
    running_bulk = set()
    async for r in get().jobs.find({"status": "running", "bulk_id": {"$exists": True, "$ne": None}}, {"bulk_id": 1}):
        if r.get("bulk_id"):
            running_bulk.add(r["bulk_id"])

    for _ in range(limit):
        # Prefer oldest pending; skip bulk if that series already has a running job
        # Prefer lower bulk_index first so full-series is ch1 → ch2 → ch3
        candidates = await get().jobs.find(
            {"status": "pending", "cancel_requested": {"$ne": True}},
        ).sort([
            ("bulk_index", ASCENDING),
            ("created_at", ASCENDING),
        ]).limit(80).to_list(80)
        # Python-side stable sort: non-bulk first by created_at, bulk by index
        def _cand_key(c):
            bi = c.get("bulk_index")
            try:
                bi_n = int(bi) if bi is not None else 10**9
            except Exception:
                bi_n = 10**9
            ts = c.get("created_at") or utcnow()
            return (bi_n, ts)
        candidates = sorted(candidates, key=_cand_key)
        picked = None
        for c in candidates:
            bid = c.get("bulk_id")
            if bid and bid in running_bulk:
                continue
            # For bulk: only claim lowest bulk_index still pending
            if bid:
                try:
                    cur_idx = int(c.get("bulk_index") or 0)
                except Exception:
                    cur_idx = 0
                lower = await get().jobs.find_one({
                    "bulk_id": bid,
                    "status": "pending",
                    "cancel_requested": {"$ne": True},
                    "bulk_index": {"$lt": cur_idx},
                })
                if lower:
                    continue
            picked = c
            break
        if not picked:
            break
        doc = await get().jobs.find_one_and_update(
            {"_id": picked["_id"], "status": "pending", "cancel_requested": {"$ne": True}},
            {"$set": {
                "status": "running",
                "progress": 1,
                "updated_at": now,
                "claimed_at": now,
            }},
            return_document=ReturnDocument.AFTER,
        )
        if not doc:
            continue
        if doc.get("bulk_id"):
            running_bulk.add(doc["bulk_id"])
        claimed.append(doc)
    return claimed


async def recover_stuck_jobs() -> int:
    """Fail or requeue jobs stuck in 'running' longer than STUCK_MINUTES."""
    cutoff = utcnow() - timedelta(minutes=STUCK_MINUTES)
    cursor = get().jobs.find({
        "status": "running",
        "updated_at": {"$lt": cutoff},
    })
    recovered = 0
    async for doc in cursor:
        retries = int(doc.get("retries") or 0)
        key = doc["job_key"]
        if retries < MAX_RETRIES and not doc.get("cancel_requested"):
            await update_job(
                key,
                status="pending",
                progress=0,
                error=f"auto-requeued after stuck ({STUCK_MINUTES}m)",
                retries=retries + 1,
            )
            logger.warning("requeued stuck job %s (retry %s)", key, retries + 1)
        else:
            await update_job(
                key,
                status="failed",
                error=f"stuck in running > {STUCK_MINUTES}m (retries exhausted)",
            )
            logger.warning("failed stuck job %s", key)
        recovered += 1
    return recovered


async def request_cancel(key: str) -> bool:
    """Mark a pending/running job for cancellation."""
    res = await get().jobs.update_one(
        {"job_key": key, "status": {"$in": ["pending", "running"]}},
        {"$set": {"cancel_requested": True, "updated_at": utcnow()}},
    )
    return res.modified_count > 0


async def cancel_bulk(bulk_id: str) -> int:
    """Cancel all pending/running jobs of a bulk series."""
    if not bulk_id:
        return 0
    res = await get().jobs.update_many(
        {"bulk_id": bulk_id, "status": {"$in": ["pending", "running"]}},
        {"$set": {"cancel_requested": True, "updated_at": utcnow()}},
    )
    return res.modified_count


async def is_cancel_requested(key: str) -> bool:
    doc = await get().jobs.find_one({"job_key": key}, {"cancel_requested": 1})
    return bool(doc and doc.get("cancel_requested"))


async def pending_jobs(limit: int = 5) -> List[Dict]:
    """Legacy helper — prefer claim_pending_jobs for workers."""
    return await get().jobs.find(
        {"status": "pending", "cancel_requested": {"$ne": True}}
    ).sort("created_at", ASCENDING).limit(limit).to_list(limit)


async def list_active_jobs(limit: int = 30) -> List[Dict]:
    return await get().jobs.find(
        {"status": {"$in": ["pending", "running"]}}
    ).sort("created_at", DESCENDING).limit(limit).to_list(limit)


async def count_recent(admin_id: int, sec: int = 60) -> int:
    since = utcnow() - timedelta(seconds=sec)
    return await get().jobs.count_documents({"admin_id": admin_id, "created_at": {"$gte": since}})


async def bulk_stats(bulk_id: str) -> Dict[str, int]:
    """Return counts for a bulk_id: pending, running, done, failed, cancelled."""
    if not bulk_id:
        return {}
    pipeline = [
        {"$match": {"bulk_id": bulk_id}},
        {"$group": {"_id": "$status", "n": {"$sum": 1}}},
    ]
    out = {"pending": 0, "running": 0, "done": 0, "failed": 0, "cancelled": 0}
    async for row in get().jobs.aggregate(pipeline):
        st = row["_id"] or "unknown"
        if st in out:
            out[st] = row["n"]
        elif st == "cancelled":
            out["cancelled"] = row["n"]
    return out


# logs
async def add_log(level: str, msg: str, uid: int = 0, extra: Any = None) -> None:
    doc = {
        "level": level, "message": str(msg)[:2000], "user_id": uid,
        "extra": extra, "created_at": utcnow(), "pushed": False,
    }
    await get().logs.insert_one(doc)
    # mark for log-channel push (worker/main flushes)
    try:
        await get().log_queue.insert_one(doc)
    except Exception:
        pass


async def pop_log_queue(limit: int = 20) -> List[Dict]:
    out = []
    for _ in range(limit):
        doc = await get().log_queue.find_one_and_delete({})
        if not doc:
            break
        out.append(doc)
    return out


async def get_logs(limit: int = 30) -> List[Dict]:
    return await get().logs.find({}).sort("created_at", DESCENDING).limit(limit).to_list(limit)


# cache
async def cache_manhwa(slug: str, data: Dict) -> None:
    data["slug"] = slug
    data["updated_at"] = utcnow()
    await get().manhwa_cache.update_one({"slug": slug}, {"$set": data}, upsert=True)


# ── users / premium ───────────────────────────────────────

async def ensure_user(uid: int, username: str = "", first_name: str = "") -> Dict:
    """Register user on first touch; default plan = free."""
    col = get().users
    doc = await col.find_one({"user_id": uid})
    if doc:
        await col.update_one(
            {"user_id": uid},
            {"$set": {
                "username": username or doc.get("username") or "",
                "first_name": first_name or doc.get("first_name") or "",
                "last_seen": utcnow(),
            }},
        )
        return await col.find_one({"user_id": uid}) or doc
    new = {
        "user_id": uid,
        "username": username or "",
        "first_name": first_name or "",
        "plan": "free",
        "plan_until": None,
        "daily_used": 0,
        "daily_date": utcnow().strftime("%Y-%m-%d"),
        "total_uploads": 0,
        "created_at": utcnow(),
        "last_seen": utcnow(),
        "banned": False,
    }
    await col.insert_one(new)
    return new


async def get_user(uid: int) -> Optional[Dict]:
    return await get().users.find_one({"user_id": uid})


async def set_user_plan(uid: int, plan: str, days: int = 30) -> None:
    until = utcnow() + timedelta(days=days) if plan != "free" else None
    await ensure_user(uid)
    await get().users.update_one(
        {"user_id": uid},
        {"$set": {"plan": plan, "plan_until": until, "updated_at": utcnow()}},
        upsert=True,
    )


async def get_user_plan_id(uid: int) -> str:
    """Return active plan id (free if expired)."""
    if uid == OWNER_ID:
        return "flare"
    if await is_admin(uid):
        # admins default to max unless set
        doc = await get_user(uid)
        if doc and doc.get("plan") and doc.get("plan") != "free":
            plan = doc["plan"]
            until = doc.get("plan_until")
            if until and getattr(until, "tzinfo", None) is None:
                until = until.replace(tzinfo=timezone.utc)
            if until and until < utcnow():
                return "free"
            return plan
        return "max"
    doc = await get_user(uid)
    if not doc:
        return "free"
    plan = (doc.get("plan") or "free").lower()
    until = doc.get("plan_until")
    if plan != "free" and until:
        if getattr(until, "tzinfo", None) is None:
            until = until.replace(tzinfo=timezone.utc)
        if until < utcnow():
            return "free"
    return plan if plan in ("free", "pro", "ultra", "max", "flare") else "free"


async def _reset_daily_if_needed(uid: int) -> Dict:
    doc = await ensure_user(uid)
    today = utcnow().strftime("%Y-%m-%d")
    if doc.get("daily_date") != today:
        await get().users.update_one(
            {"user_id": uid},
            {"$set": {"daily_used": 0, "daily_date": today}},
        )
        doc["daily_used"] = 0
        doc["daily_date"] = today
    return doc


async def check_daily_quota(uid: int, plan_id: str, need: int = 1) -> tuple:
    """Returns (ok: bool, used: int, limit: int)."""
    from Manhwaflare.plans import daily_limit
    if uid == OWNER_ID:
        return True, 0, 99999
    doc = await _reset_daily_if_needed(uid)
    limit = daily_limit(plan_id)
    used = int(doc.get("daily_used") or 0)
    return (used + need) <= limit, used, limit


async def consume_quota(uid: int, n: int = 1) -> None:
    await _reset_daily_if_needed(uid)
    await get().users.update_one(
        {"user_id": uid},
        {"$inc": {"daily_used": n, "total_uploads": n}},
    )


async def list_all_user_ids() -> List[int]:
    ids = []
    async for d in get().users.find({}, {"user_id": 1}):
        if d.get("user_id"):
            ids.append(int(d["user_id"]))
    # also admins
    async for d in get().admins.find({}, {"user_id": 1}):
        uid = int(d.get("user_id") or 0)
        if uid and uid not in ids:
            ids.append(uid)
    if OWNER_ID and OWNER_ID not in ids:
        ids.append(OWNER_ID)
    return ids


async def count_users() -> int:
    return await get().users.count_documents({})


# ── favorites / history / referral ────────────────────────

async def add_favorite(uid: int, slug: str, title: str, url: str = "", source: str = "") -> bool:
    try:
        await get().favorites.update_one(
            {"user_id": uid, "slug": slug},
            {"$set": {
                "user_id": uid, "slug": slug, "title": title,
                "url": url, "source": source, "created_at": utcnow(),
            }},
            upsert=True,
        )
        return True
    except Exception:
        return False


async def remove_favorite(uid: int, slug: str) -> bool:
    r = await get().favorites.delete_one({"user_id": uid, "slug": slug})
    return r.deleted_count > 0


async def list_favorites(uid: int, limit: int = 20) -> List[Dict]:
    return await get().favorites.find({"user_id": uid}).sort("created_at", DESCENDING).to_list(limit)


async def add_history(uid: int, kind: str, title: str, extra: Optional[Dict] = None) -> None:
    doc = {
        "user_id": uid, "kind": kind, "title": title,
        "extra": extra or {}, "created_at": utcnow(),
    }
    await get().history.insert_one(doc)
    # keep last 50
    cursor = get().history.find({"user_id": uid}).sort("created_at", DESCENDING).skip(50)
    async for old in cursor:
        await get().history.delete_one({"_id": old["_id"]})


async def list_history(uid: int, limit: int = 15) -> List[Dict]:
    return await get().history.find({"user_id": uid}).sort("created_at", DESCENDING).to_list(limit)



async def get_or_create_referral(uid: int) -> str:
    """Returns stable ref token = user id string for deep links."""
    doc = await get().referrals.find_one({"owner_id": uid})
    if doc:
        return str(doc.get("code") or uid)
    code = str(uid)
    await get().referrals.insert_one({
        "code": code,
        "owner_id": uid,
        "uses": 0,
        "created_at": utcnow(),
    })
    return code


async def get_referral_stats(uid: int) -> dict:
    doc = await get().referrals.find_one({"owner_id": uid})
    uses = int((doc or {}).get("uses") or 0)
    return {"uses": uses, "code": str(uid)}


async def apply_referral(uid: int, code: str) -> str:
    """Apply referral from deep link /ref_USERID or code=userid."""
    code = (code or "").strip().replace("ref_", "")
    if not code.isdigit():
        return "invalid"
    owner_id = int(code)
    if owner_id == uid:
        return "self"
    # ensure referrer row exists
    await get_or_create_referral(owner_id)
    user = await get_user(uid) or {}
    if user.get("referred_by"):
        return "already"
    # referrer must exist as bot user ideally
    await get().users.update_one(
        {"user_id": uid},
        {"$set": {"referred_by": owner_id}},
        upsert=True,
    )
    await get().referrals.update_one(
        {"owner_id": owner_id},
        {"$inc": {"uses": 1}, "$setOnInsert": {"code": str(owner_id), "created_at": utcnow()}},
        upsert=True,
    )
    # both get +3 daily bonus chapters
    await add_daily_bonus(uid, 3)
    await add_daily_bonus(owner_id, 3)
    return "ok"


async def add_daily_bonus(uid: int, amount: int = 1) -> None:
    day = utcnow().strftime("%Y-%m-%d")
    await get().users.update_one(
        {"user_id": uid},
        {"$inc": {f"bonus_{day}": int(amount)}},
        upsert=True,
    )


async def leaderboard_uploaders(limit: int = 10) -> List[Dict]:
    pipe = [
        {"$group": {"_id": "$admin_id", "count": {"$sum": 1}}},
        {"$sort": {"count": -1}},
        {"$limit": limit},
    ]
    out = []
    async for row in get().jobs.aggregate(pipe):
        out.append({"user_id": row["_id"], "count": row["count"]})
    return out


async def count_queue() -> Dict[str, int]:
    pending = await get().jobs.count_documents({"status": "pending"})
    running = await get().jobs.count_documents({"status": "running"})
    return {"pending": pending, "running": running}


async def cancel_user_jobs(uid: int) -> int:
    r = await get().jobs.update_many(
        {"admin_id": int(uid), "status": {"$in": ["pending", "running"]}},
        {"$set": {"cancel_requested": True, "status": "cancelled", "updated_at": utcnow()}},
    )
    return int(r.modified_count or 0)
