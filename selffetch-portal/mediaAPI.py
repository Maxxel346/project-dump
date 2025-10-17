import asyncio
import os
import random
import time
from collections import deque
from threading import Lock
from typing import List, Optional


import asyncpg
import requests
from cachetools import LRUCache
from dotenv import load_dotenv
from fastapi import FastAPI, Body, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from stem import Signal
from stem.control import Controller

# Load environment variables from .env in the same folder
load_dotenv()

# ====================
# Configuration
# ====================
# Global constants
MAIN_URL = os.getenv("MAIN_URL")
MAIN_CDN = os.getenv("MAIN_CDN")

MAIN_REFERER = MAIN_URL # default referer for requests


USE_TOR = False  # whether to use Tor proxies for media fetching

# Database DSN (consider moving to env var)
DB_DSN = "postgresql://postgres:p@localhost:5432/xxxx"

# Media cache limit in bytes (1 GiB). Use plain numeric literal.
MEDIA_CACHE_MAX_BYTES = 1024 * 1024 * 1024  # 1 GiB

# Tor proxies list (socks + control ports)
TOR_PROXIES = [
    {"socks_port": 9051, "control_port": 9151},
    {"socks_port": 9052, "control_port": 9152},
    {"socks_port": 9053, "control_port": 9153},
    {"socks_port": 9054, "control_port": 9154},
    {"socks_port": 9055, "control_port": 9155},
    {"socks_port": 9056, "control_port": 9156},
    {"socks_port": 9057, "control_port": 9157},
    {"socks_port": 9058, "control_port": 9158},
    {"socks_port": 9059, "control_port": 9159},
    {"socks_port": 9060, "control_port": 9160},
    {"socks_port": 9061, "control_port": 9161},
    {"socks_port": 9062, "control_port": 9162},
    {"socks_port": 9063, "control_port": 9163},
    {"socks_port": 9064, "control_port": 9164},
    {"socks_port": 9065, "control_port": 9165},
    {"socks_port": 9066, "control_port": 9166},
]

# Bearer tokens (sensitive) - move to environment/secret store in production
AUTH_BEARERS = []
for i in range(1, 10):  # supports up to 9 tokens, expand if needed
    token = os.getenv(f"AUTH_BEARER_{i}")
    if token:
        AUTH_BEARERS.append(token)

# Allowed origins list (for development). Consider restricting in production.
ALLOWED_ORIGINS = ["*"]


# User agents list (sample)
USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 CrKey/1.54.250320",
    "Mozilla/5.0 (Linux; Android) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36 CrKey/1.54.248666",
    "Mozilla/5.0 (Linux; Android 8.0.0; SM-G955U Build/R16NW) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1",
]

# ====================
# Application setup
# ====================

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# requests Session for connection pooling (used for external HTTP calls)
session = requests.Session()

# Preflight cache for POST /preflight requests
preflight_cache = {}
preflight_queue = deque(maxlen=30)

# ====================
# Utilities: rotation / headers / DB helpers
# ====================


class RoundRobin:
    """
    Simple thread-safe round-robin selector for lists.
    """
    def __init__(self, items: list):
        self._items = items
        self._lock = Lock()
        self._idx = 0

    def next(self):
        with self._lock:
            if not self._items:
                return None
            item = self._items[self._idx]
            self._idx = (self._idx + 1) % len(self._items)
            return item


# Create global round-robins for bearers and proxies
bearer_rr = RoundRobin(AUTH_BEARERS)
proxy_rr = RoundRobin(TOR_PROXIES)


def get_next_bearer() -> str:
    """Return next bearer token in round-robin fashion."""
    return bearer_rr.next()


def get_next_proxy():
    """Return next proxy object and index (index not used outside)."""
    return proxy_rr.next()


def make_headers(referer: Optional[str] = None, include_bearer: bool = True) -> dict:
    """
    Build headers used for requests to the target site.
    include_bearer: whether to include Authorization header (some calls comment it out).
    """
    headers = {
        "Referer": referer or MAIN_REFERER,
        "User-Agent": random.choice(USER_AGENTS),
        "DNT": "1",
    }
    if include_bearer:
        headers["Authorization"] = f"Bearer {get_next_bearer()}"
    return headers


# DB helper to get a connection from pool or create a direct connection if pool not ready.
# Prefer using app.state.db (pool) via acquire() in async routes.
async def get_db_pool():
    return getattr(app.state, "db", None)


# ====================
# Media cache: LRU by bytes
# ====================


class MediaLRUCache:
    """
    LRU cache that evicts based on total bytes rather than item count.
    Each value stored as tuple: (content_bytes, content_type, size_bytes)
    """

    def __init__(self, max_bytes: int):
        self.cache = LRUCache(maxsize=10000)  # large count; we'll control eviction by bytes
        self.lock = Lock()
        self.max_bytes = max_bytes
        self.current_bytes = 0

    @staticmethod
    def _estimate_size(content: bytes) -> int:
        """Estimate the size in bytes for content."""
        return len(content)

    def get(self, url: str):
        """Return cached tuple (content, content_type, size) or None."""
        with self.lock:
            return self.cache.get(url, None)

    def set(self, url: str, content: bytes, content_type: str):
        """Insert content into cache and evict older items if needed."""
        with self.lock:
            if url in self.cache:
                return
            size = self._estimate_size(content)
            # Evict LRU items until enough space is available
            while self.current_bytes + size > self.max_bytes and len(self.cache) > 0:
                evicted_url, evicted_tuple = self.cache.popitem(last=False)
                _, _, evicted_size = evicted_tuple
                self.current_bytes -= evicted_size
            self.cache[url] = (content, content_type, size)
            self.current_bytes += size


# global media cache instance
media_cache = MediaLRUCache(MEDIA_CACHE_MAX_BYTES)

# ====================
# Tor control helper
# ====================


def newnym_tor_port(control_port: int, control_password: Optional[str] = "your-password"):
    """
    Signal Tor to create a new circuit on the control_port. The password should be configured properly.
    Note: in production, keep control password in a secret store and ensure Controller.from_port authentication works.
    """
    try:
        with Controller.from_port(port=control_port) as controller:
            controller.authenticate(password=control_password)
            controller.signal(Signal.NEWNYM)
    except Exception as exc:
        # We swallow exceptions so the calling code can retry with different proxy
        print(f"[newnym] failed for control_port={control_port}: {exc}")


# ====================
# Media fetching (images/videos) — synchronous helpers
# ====================


def _streaming_response_from_requests(resp: requests.Response) -> StreamingResponse:
    """
    Create FastAPI StreamingResponse from requests.Response stream.
    Filter specific headers useful for video playback.
    """
    filtered_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() in (
            "content-type", "content-length", "content-range", "accept-ranges", "cache-control", "last-modified"
        )
    }
    return StreamingResponse(resp.iter_content(chunk_size=8192), media_type=resp.headers.get("Content-Type", "video/mp4"), headers=filtered_headers)


def fetch_media(url: str, media_type: str = "image", max_retries: int = 6, post_id: Optional[int] = None):
    """
    Fetch media from target URLs, using proxies in round-robin and attempting NEWNYM on connection reset.
    Returns either fastapi.Response (for images) or StreamingResponse (for videos).
    Raises HTTPException on permanent failure.
    """
    # Check cache for images (we don't cache big videos)
    cached = media_cache.get(url)
    if cached and media_type == "image":
        content, content_type, _ = cached
        return Response(content=content, media_type=content_type)

    # Prepare headers
    referer = f"{MAIN_URL}post/{post_id}" if post_id else MAIN_REFERER
    headers = {
        "Referer": referer,
        "User-Agent": random.choice(USER_AGENTS),
        "Dnt": "1",
        # "Authorization": f"Bearer {get_next_bearer()}", 
    }

    last_exc = None

    for attempt in range(max_retries):
        if not USE_TOR:
            proxy_conf = None
        if proxy_conf is None:
            # No proxies configured; fallback to direct connection
            socks_port = None
            control_port = None
        else:
            socks_port = proxy_conf.get("socks_port")
            control_port = proxy_conf.get("control_port")

        # Build requests proxies dict for socks if present (requests + socks support needed)
        proxies = {}
        if socks_port:
            proxies = {
                "http": f"socks5h://127.0.0.1:{socks_port}",
                "https": f"socks5h://127.0.0.1:{socks_port}",
            }

        try:
            # Image (small) - fetch fully and cache
            if media_type == "image":
                resp = session.get(url, headers=headers, timeout=10, proxies=proxies)
                if resp.status_code == 200:
                    # pick content type heuristically
                    content_type = "image/avif" if url.endswith(".avif") else resp.headers.get("Content-Type", "image/jpeg")
                    media_cache.set(url, resp.content, content_type)
                    return Response(content=resp.content, media_type=content_type)
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Image not found")
                # treat some 500/resets as transient
                if resp.status_code == 500 and "ConnectionResetError" in resp.text:
                    raise ValueError("Tor 500/ConnectionReset")
                raise HTTPException(status_code=resp.status_code, detail=f"[{socks_port}] {resp.text}")

            # Video streaming
            elif media_type == "video":
                resp = session.get(url, headers=headers, timeout=60, stream=True, proxies=proxies)
                if resp.status_code == 200:
                    return _streaming_response_from_requests(resp)
                if resp.status_code == 404:
                    raise HTTPException(status_code=404, detail="Video not found")
                if resp.status_code == 500 and "ConnectionResetError" in resp.text:
                    raise ValueError("Tor 500/ConnectionReset")
                raise HTTPException(status_code=resp.status_code, detail=f"[{socks_port}] {resp.text}")
            else:
                raise HTTPException(status_code=400, detail="Bad media type")
        except requests.exceptions.ConnectionError as ce:
            # Windows Winsock 10054 or similar connection reset cases
            msg = str(ce)
            last_exc = ce
            if "10054" in msg or "forcibly closed" in msg or "Connection aborted" in msg:
                print(f"[fetch_media] Tor@{socks_port}: connection reset detected -> NEWNYM and retry")
                if control_port:
                    newnym_tor_port(control_port)
                    time.sleep(1.5)
                continue
        except Exception as exc:
            last_exc = exc
            # If matches reset pattern, attempt NEWNYM and continue; else the outer loop will try other proxies
            msg = str(exc)
            if "10054" in msg or "forcibly closed" in msg or "Connection aborted" in msg:
                print(f"[fetch_media] generic connection reset -> NEWNYM on control_port={control_port}")
                if control_port:
                    newnym_tor_port(control_port)
                    time.sleep(1.5)
                continue

    # If reached here, all attempts failed
    raise HTTPException(status_code=500, detail=f"Failed to fetch after retries: {last_exc}")


# ====================
# Storage path helpers
# ====================


def build_storage_path(post_id: int) -> str:
    """
    Build the storage path prefix used by the site storage host.
    Format: "<prefix>/<post_id>/<post_id>"
    Where prefix is integer division by 1000 (0 for ids < 1000).
    """
    prefix = str(post_id // 1000)
    folder = str(post_id)
    return f"{prefix}/{folder}/{post_id}"


# ====================
# Startup event: DB pool creation
# ====================


@app.on_event("startup")
async def startup():
    """
    Create a connection pool on application startup and attach it to app.state.db.
    """
    app.state.db = await asyncpg.create_pool(dsn=DB_DSN, min_size=1, max_size=10)


# ====================
# Routes: media fetch (images/videos) and helpers
# ====================


@app.get("/image/preview/{post_id}")
def preview_image_url(post_id: int, ts: Optional[float] = None):
    """
    Return a preview image (avif or jpg). Tries primary (avif) then backup (.jpg).
    Optional ts: sleep time for testing.
    """
    if ts:
        time.sleep(ts)
    primary = f"{MAIN_CDN}posts/{build_storage_path(post_id)}.pic256avif.avif"
    backup = f"{MAIN_CDN}posts/{build_storage_path(post_id)}.pic256.jpg"
    try:
        return fetch_media(primary, media_type="image", post_id=post_id)
    except HTTPException:
        try:
            return fetch_media(backup, media_type="image", post_id=post_id)
        except Exception as exc:
            print(f"[preview_image_url] failed for {post_id}: {exc}")
            raise


@app.get("/image/full/{post_id}")
def full_image_url(post_id: int):
    """
    Return the full-size image. Tries .pic.jpg then .picsmall.jpg.
    """
    primary = f"{MAIN_CDN}posts/{build_storage_path(post_id)}.pic.jpg"
    backup = f"{MAIN_CDN}posts/{build_storage_path(post_id)}.picsmall.jpg"
    try:
        return fetch_media(primary, media_type="image", post_id=post_id)
    except HTTPException:
        try:
            return fetch_media(backup, media_type="image", post_id=post_id)
        except Exception as exc:
            print(f"[full_image_url] failed for {post_id}: {exc}")
            raise


@app.get("/video/preview/{post_id}")
def video_preview_url(post_id: int):
    """
    Return a small-sized preview video (.mov256.mp4). Try a backup host if needed.
    """
    primary = f"{MAIN_CDN}posts/{build_storage_path(post_id)}.mov256.mp4"
    backup = f"{MAIN_URL}posts/{build_storage_path(post_id)}.mov256.mp4"
    try:
        return fetch_media(primary, media_type="video", post_id=post_id)
    except HTTPException:
        try:
            return fetch_media(backup, media_type="video", post_id=post_id)
        except Exception as exc:
            print(f"[video_preview_url] failed for {post_id}: {exc}")
            raise


@app.get("/video/full/{post_id}")
def video_full_url(post_id: int):
    """
    Return full video with a few alternative path attempts.
    """
    base = f"{MAIN_CDN}posts/{build_storage_path(post_id)}"
    attempts = [
        base + ".mov.mp4",
        base + ".mov480.mp4",
    ]
    last_exc = None
    for url in attempts:
        try:
            return fetch_media(url, media_type="video", post_id=post_id)
        except Exception as exc:
            last_exc = exc
            print(f"[video_full_url] attempt {url} failed: {exc}")
    # try final backup
    try:
        return fetch_media(base + ".mov480.mp4", media_type="video", post_id=post_id)
    except Exception as exc:
        print(f"[video_full_url] all attempts failed for {post_id}: {exc}")
        raise HTTPException(status_code=500, detail=f"Video fetch failed: {exc}")


# ====================
# Preflight / suggestion endpoints
# ====================


@app.post("/preflight")
async def fetch_preflight(ids: List[int] = Body(...)):
    """
    Requests states for a list of post ids from the external API and caches result locally.
    Caches keyed by sorted tuple of ids with limited queue-based eviction.
    """
    key = tuple(sorted(ids))
    # quick cache hit
    if key in preflight_cache:
        return {"cached": True}
    url = "{MAIN_URL}api/v2/post/action/states"
    headers = make_headers(referer=f"{MAIN_URL}post/{ids[0]}" if ids else MAIN_REFERER, include_bearer=True)
    payload = ids
    try:
        resp = session.post(url, json=payload, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            preflight_cache[key] = data
            preflight_queue.append(key)
            # deque has maxlen so it auto-evicts, but ensure cache cleanup
            while len(preflight_queue) > preflight_queue.maxlen:
                oldest = preflight_queue.popleft()
                preflight_cache.pop(oldest, None)
            return data
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"Preflight POST failed: {resp.text}")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Preflight POST exception: {exc}")


@app.get("/suggestion/{post_id}")
async def fetch_suggestion(post_id: int):
    """
    Return suggested related post ids by calling the suggestion API.
    The original network also posted to /post/action/state before fetching suggestions so we keep that best-effort behavior.
    """
    url_get = f"{MAIN_URL}api/v2/post/suggestion/{post_id}"
    referer = f"{MAIN_URL}post/{post_id}"
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Authorization": f"Bearer {get_next_bearer()}",
        "Content-Type": "application/json",
        "DNT": "1",
        "Referer": referer,
        "Sec-Ch-Ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
        "Sec-Ch-Ua-Mobile": "?1",
        "Sec-Ch-Ua-Platform": "Android",
        "User-Agent": "Mozilla/5.0 (Linux; Android 6.0; Nexus 5 Build/MRA58N) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Mobile Safari/537.36",
    }

    # Best-effort POST to action/state as in original code (ignore errors)
    try:
        session.post("{MAIN_URL}api/v2/post/action/state", json={"postId": post_id}, headers=headers, timeout=15)
    except Exception as exc:
        print(f"[fetch_suggestion] state POST exception (ignored): {exc}")

    try:
        resp = session.get(url_get, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            only_ids = [item["id"] for item in data]
            return only_ids
        else:
            raise HTTPException(status_code=resp.status_code, detail=f"Suggestion GET failed: {resp.text}")
    except Exception as exc:
        print(f"[fetch_suggestion] exception: {exc}")
        raise HTTPException(status_code=500, detail=f"Suggestion GET exception: {exc}")


# ====================
# Pydantic models
# ====================


class SearchMediaByTagsRequest(BaseModel):
    include_tags: Optional[List[str]] = Field(default_factory=list)
    exclude_tags: Optional[List[str]] = Field(default_factory=list)
    limit: int = 50
    offset: int = 0
    favorite_only: bool = False
    user_id: Optional[int] = None
    cached: Optional[bool] = None


class TagIn(BaseModel):
    id: int
    value: str


class SearchHistoryIn(BaseModel):
    include_tags: List[str] = Field(default_factory=list)
    exclude_tags: List[str] = Field(default_factory=list)
    favorite_only: bool = False
    user_id: Optional[int] = None


# ====================
# Database / search / favorites routes
# ====================


@app.get("/fetch_media_with_tags")
async def fetch_media_with_tags_api(id: int):
    """
    Fetch a single media row by id along with its tags and source.
    """
    # Use a direct connection (original code used asyncpg.connect here)
    conn = await asyncpg.connect(DB_DSN)
    try:
        media = await conn.fetchrow("SELECT * FROM media WHERE id=$1", id)
        if not media:
            return {"error": "Media not found"}
        rows = await conn.fetch("""
            SELECT t.id, t.value, t.type, t.popularity, t.count
            FROM tags t
            JOIN media_tags mt ON mt.tag_id = t.id
            WHERE mt.media_id=$1
        """, id)
        source_row = await conn.fetchrow("SELECT ms.source FROM media_sources ms WHERE ms.media_id=$1", id)
        return {
            "id": media["id"],
            "created": media["created"].isoformat() if media["created"] else None,
            "posted": media["posted"].isoformat() if media["posted"] else None,
            "likes": media["likes"],
            "type": media["type"],
            "status": media["status"],
            "uploaderId": media["uploader_id"],
            "width": media["width"],
            "height": media["height"],
            "tags": [dict(row) for row in rows],
            "source": source_row["source"] if source_row else None
        }
    finally:
        await conn.close()


@app.post("/fetch_media_with_tags_batch")
async def fetch_media_with_tags_batch(ids: List[int] = Body(...)):
    """
    Fetch multiple media with their tags in optimized queries.
    Returns list in the same order as ids input with per-id error if not found.
    """
    if not ids:
        return []
    conn = await asyncpg.connect(DB_DSN)
    try:
        media_rows = await conn.fetch("SELECT * FROM media WHERE id = ANY($1)", ids)
        media_dict = {row["id"]: dict(row) for row in media_rows}
        tag_rows = await conn.fetch("""
            SELECT mt.media_id, t.id, t.value, t.type, t.popularity, t.count
            FROM tags t
            JOIN media_tags mt ON mt.tag_id = t.id
            WHERE mt.media_id = ANY($1)
        """, ids)
        for tag in tag_rows:
            mid = tag["media_id"]
            if "tags" not in media_dict[mid]:
                media_dict[mid]["tags"] = []
            media_dict[mid]["tags"].append({
                "id": tag["id"],
                "value": tag["value"],
                "type": tag["type"],
                "popularity": tag["popularity"],
                "count": tag["count"]
            })
        result = []
        for mid in ids:
            m = media_dict.get(mid)
            if not m:
                result.append({"id": mid, "error": "Media not found"})
                continue
            result.append({
                "id": m["id"],
                "created": m["created"].isoformat() if m["created"] else None,
                "posted": m["posted"].isoformat() if m["posted"] else None,
                "likes": m["likes"],
                "type": m["type"],
                "status": m["status"],
                "uploaderId": m["uploader_id"],
                "width": m["width"],
                "height": m["height"],
                "tags": m.get("tags", [])
            })
        return result
    finally:
        await conn.close()


@app.post("/search_media_by_tags")
async def search_media_by_tags_api(req: SearchMediaByTagsRequest):
    """
    Complex search that supports include/exclude tags, favorites, pagination, and optional prefetching of previews.
    """
    async with app.state.db.acquire() as conn:
        conditions = ["TRUE"]
        params = []
        param_index = 1

        # Include tags: ensure media has all include_tags
        if req.include_tags:
            conditions.append(f"""
                m.id IN (
                    SELECT mt.media_id
                    FROM media_tags mt
                    JOIN tags t ON t.id = mt.tag_id
                    WHERE t.value = ANY(${param_index})
                    GROUP BY mt.media_id
                    HAVING COUNT(DISTINCT t.value) = {len(req.include_tags)}
                )
            """)
            params.append(req.include_tags)
            param_index += 1

        # Exclude tags: ensure none of exclude_tags are present
        if req.exclude_tags:
            conditions.append(f"""
                NOT EXISTS (
                    SELECT 1
                    FROM media_tags mt
                    JOIN tags t ON t.id = mt.tag_id
                    WHERE mt.media_id = m.id
                      AND t.value = ANY(${param_index})
                )
            """)
            params.append(req.exclude_tags)
            param_index += 1

        # Favorite-only filtering
        if req.favorite_only:
            if req.user_id is not None:
                conditions.append(f"m.id IN (SELECT media_id FROM favorite_media WHERE user_id = ${param_index})")
                params.append(req.user_id)
                param_index += 1
            else:
                conditions.append("m.id IN (SELECT media_id FROM favorite_media)")

        where_clause = " AND ".join(conditions)

        # Build the main query (returns paginated items and total_count)
        query = f"""
        WITH filtered AS (
            SELECT m.id
            FROM media m
            WHERE {where_clause}
        ),
        total AS (
            SELECT COUNT(*) AS total_count FROM filtered
        ),
        paged AS (
            SELECT m.*
            FROM media m
            JOIN filtered f ON f.id = m.id
            ORDER BY m.created DESC
            LIMIT ${param_index} OFFSET ${param_index + 1}
        )
        SELECT p.id,
               p.created,
               p.posted,
               p.likes,
               p.type,
               p.status,
               p.uploader_id,
               p.width,
               p.height,
               tot.total_count,
               COALESCE(json_agg(
                   json_build_object('id', t.id, 'value', t.value)
               ) FILTER (WHERE t.id IS NOT NULL), '[]') AS tags
        FROM paged p
        CROSS JOIN total tot
        LEFT JOIN media_tags mt ON mt.media_id = p.id
        LEFT JOIN tags t ON t.id = mt.tag_id
        GROUP BY p.id, p.created, p.posted, p.likes, p.type, p.status,
                 p.uploader_id, p.width, p.height, tot.total_count
        ORDER BY p.created DESC
        """

        params.extend([req.limit, req.offset])
        rows = await conn.fetch(query, *params)

        if not rows:
            return {"total": 0, "limit": req.limit, "offset": req.offset, "items": []}

        total = rows[0]["total_count"]
        items = [{
            "id": r["id"],
            "created": r["created"].isoformat() if r["created"] else None,
            "posted": r["posted"].isoformat() if r["posted"] else None,
            "likes": r["likes"],
            "type": r["type"],
            "status": r["status"],
            "uploaderId": r["uploader_id"],
            "width": r["width"],
            "height": r["height"],
            "tags": r["tags"]
        } for r in rows]

        # If cached flag requested, prefetch preview images asynchronously using event loop executors (best-effort)
        if req.cached:
            print(f"[search_media_by_tags_api] Prefetching {len(items)} preview images (best-effort)...")
            loop = asyncio.get_event_loop()
            for item in items:
                # Use run_in_executor with synchronous preview_image_url (it returns a Response)
                loop.run_in_executor(None, preview_image_url, item["id"], 2)  # 2s artificial delay
            # Original code returned {} in cached branch; keep same behavior (no payload)
            return {}

        return {
            "total": total,
            "limit": req.limit,
            "offset": req.offset,
            "items": items
        }


@app.get("/search_tags_by_prefix")
async def search_tags_by_prefix_api(keyword: str, limit: int = 20):
    """
    Search tags by prefix using ILIKE.
    """
    if len(keyword) < 2:
        return []
    async with app.state.db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT t.id, t.value, t.type, t.popularity, t.count
            FROM tags t
            WHERE t.value ILIKE $1 || '%'
            ORDER BY t.count DESC
            LIMIT $2
        """, keyword, limit)
    return [dict(r) for r in rows]


@app.get("/search_tags_fuzzy")
async def search_tags_fuzzy_api(keyword: str, limit: int = 20, similarity_threshold: float = 0.2):
    """
    Fuzzy search using pg_trgm similarity operator (%).
    Uses a direct asyncpg connection.
    """
    conn = await asyncpg.connect(DB_DSN)
    try:
        rows = await conn.fetch("""
            SELECT t.id, t.value, t.type, t.popularity,
                   COUNT(mt.media_id) AS count,
                   similarity(t.value, $1) AS sim
            FROM tags t
            LEFT JOIN media_tags mt ON t.id = mt.tag_id
            WHERE t.value % $1
            GROUP BY t.id
            HAVING similarity(t.value, $1) > $2
            ORDER BY sim DESC, count DESC
            LIMIT $3
        """, keyword, similarity_threshold, limit)
        result = [dict(r) for r in rows]
        print(result)
        return result
    finally:
        await conn.close()


# ====================
# Favorites (media & tag) and history endpoints
# ====================


@app.post("/favorite/media/{media_id}", status_code=204)
async def add_favorite_media(media_id: int, user_id: Optional[int] = None, request: Request = None):
    """
    Add a media to favorites. If user_id provided, add per-user favorite else global.
    """
    async with request.app.state.db.acquire() as conn:
        if user_id is None:
            await conn.execute("""
                INSERT INTO favorite_media (media_id)
                SELECT $1
                WHERE NOT EXISTS (SELECT 1 FROM favorite_media WHERE media_id = $1)
            """, media_id)
        else:
            await conn.execute("""
                INSERT INTO favorite_media (media_id, user_id)
                SELECT $1, $2
                WHERE NOT EXISTS (
                    SELECT 1 FROM favorite_media WHERE media_id = $1 AND user_id = $2
                )
            """, media_id, user_id)
    return


@app.delete("/favorite/media/{media_id}", status_code=204)
async def delete_favorite_media(media_id: int, request: Request):
    """Delete favorite by media_id (global or per-user depending on table design)."""
    async with request.app.state.db.acquire() as conn:
        await conn.execute("DELETE FROM favorite_media WHERE media_id=$1", media_id)
    return


@app.get("/favorite/media")
async def list_favorite_media(user_id: Optional[int] = None, request: Request = None):
    """
    List favorite media. If user_id provided, filter by user_id else global.
    This consolidates the two duplicate definitions in the original.
    """
    async with request.app.state.db.acquire() as conn:
        if user_id is None:
            rows = await conn.fetch("""
                SELECT media_id, created
                FROM favorite_media
                ORDER BY created DESC
            """)
        else:
            rows = await conn.fetch("""
                SELECT media_id, created
                FROM favorite_media
                WHERE user_id = $1
                ORDER BY created DESC
            """, user_id)
    return [dict(r) for r in rows]


# Favorite tags (tags favorites)
@app.post("/favorite/tag", status_code=204)
async def add_favorite_tag(tag: TagIn, request: Request):
    """Add favorite tag if not exists."""
    async with request.app.state.db.acquire() as conn:
        await conn.execute("""
            INSERT INTO favorite_tags (tag_id, tag_value)
            SELECT $1, $2
            WHERE NOT EXISTS (
                SELECT 1 FROM favorite_tags WHERE tag_id = $1
            )
        """, tag.id, tag.value)
    return


@app.delete("/favorite/tag/{tag_id}", status_code=204)
async def delete_favorite_tag(tag_id: int, request: Request):
    """Delete favorite tag by tag_id."""
    async with request.app.state.db.acquire() as conn:
        await conn.execute("DELETE FROM favorite_tags WHERE tag_id=$1", tag_id)
    return


@app.get("/favorite/tag")
async def list_favorite_tags(request: Request):
    """List favorite tags ordered by value."""
    async with request.app.state.db.acquire() as conn:
        rows = await conn.fetch("""
            SELECT tag_id AS id, tag_value AS value, created
            FROM favorite_tags
            ORDER BY tag_value ASC
        """)
    return [dict(r) for r in rows]


# Search history
@app.post("/search_history", status_code=201)
async def save_search_history(payload: SearchHistoryIn):
    """Save a search history record."""
    async with app.state.db.acquire() as conn:
        await conn.execute("""
            INSERT INTO search_history (user_id, include_tags, exclude_tags, favorite_only)
            VALUES ($1, $2, $3, $4)
        """, payload.user_id, payload.include_tags, payload.exclude_tags, payload.favorite_only)
    return {"status": "ok"}


@app.get("/search_history")
async def get_search_history(limit: int = 20, user_id: Optional[int] = None):
    """Get search history (global or per-user)."""
    async with app.state.db.acquire() as conn:
        if user_id is not None:
            rows = await conn.fetch("""
                SELECT id, user_id, include_tags, exclude_tags, favorite_only, created
                FROM search_history
                WHERE user_id = $1
                ORDER BY created DESC
                LIMIT $2
            """, user_id, limit)
        else:
            rows = await conn.fetch("""
                SELECT id, user_id, include_tags, exclude_tags, favorite_only, created
                FROM search_history
                ORDER BY created DESC
                LIMIT $1
            """, limit)

    result = []
    for r in rows:
        result.append({
            "id": r["id"],
            "user_id": r["user_id"],
            "include_tags": r["include_tags"],
            "exclude_tags": r["exclude_tags"],
            "favorite_only": r["favorite_only"],
            "created": r["created"].isoformat() if r["created"] else None
        })

    return result
