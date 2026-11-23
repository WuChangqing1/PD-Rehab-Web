"""Staff dictation tickets and same-origin streaming endpoint (single worker)."""
import asyncio
import json
import secrets
import time
from collections import deque
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from app.api.deps import CurrentUser, DbSession
from app.core.errors import APIError
from app.db.models import StaffUser
from app.services import asr_stream

router = APIRouter(prefix="/asr", tags=["speech"])
_tickets = {}
_issued = {}
_active = set()


@router.get("/capabilities")
def capabilities(user: CurrentUser):
    return {"available": asr_stream.available(), "provider": "aliyun-bailian",
            "model": "fun-asr-realtime", "max_duration_seconds": 60}


@router.post("/tickets")
async def ticket(user: CurrentUser):
    if not asr_stream.available():
        raise APIError(503, "ASR_UNAVAILABLE", "语音输入暂未开通，请继续使用文字输入。")
    now = time.monotonic()
    for key, (_, expiry) in list(_tickets.items()):
        if expiry < now:
            del _tickets[key]
    for uid, history in list(_issued.items()):
        while history and history[0] < now-60:
            history.popleft()
        if not history:
            del _issued[uid]
    history = _issued.setdefault(user.id, deque())
    if len(history) >= 6 or len(_tickets) >= 256:
        raise APIError(429, "ASR_RATE_LIMIT", "语音请求过于频繁，请稍后重试。")
    history.append(now)
    value = secrets.token_urlsafe(32)
    _tickets[value] = (user.id, now+60)
    return {"ticket": value, "expires_in": 60}


def same_origin(ws):
    origin = urlsplit(ws.headers.get("origin", ""))
    # Only trusted reverse proxy may supply X-Forwarded-Proto.
    scheme = ws.headers.get("x-forwarded-proto", ws.url.scheme).split(",")[0].strip()
    scheme = {"ws": "http", "wss": "https"}.get(scheme, scheme)
    return origin.scheme == scheme and origin.netloc == ws.headers.get("host") and origin.path in ("", "/")


@router.websocket("/stream")
async def stream(ws: WebSocket, db: DbSession):
    await ws.accept()
    uid = None
    admitted = False
    async def error(code):
        await ws.send_json({"type": "error", "code": code})
    try:
        if not same_origin(ws) or ws.query_params:
            await error("ORIGIN_DENIED")
            return
        raw = await asyncio.wait_for(ws.receive_text(), 5)
        if len(raw) > 1024:
            await error("AUTH_REQUIRED")
            return
        message = json.loads(raw)
        entry = _tickets.pop(message.get("ticket", ""), None)
        if message.get("type") != "auth" or not entry or entry[1] < time.monotonic():
            await error("AUTH_REQUIRED")
            return
        uid = entry[0]
        def authorized():
            # End read transaction so concurrent account deactivation is visible.
            db.rollback()
            user = db.get(StaffUser, uid, populate_existing=True)
            return bool(user and user.is_active and user.role in ("ADMIN", "DOCTOR", "NURSE"))
        if not authorized():
            await error("AUTH_REQUIRED")
            return
        if uid in _active or len(_active) >= 4:
            await error("BUSY")
            uid = None
            return
        _active.add(uid)
        admitted = True
        if not asr_stream.available():
            await error("UNAVAILABLE")
            return
        await asr_stream.relay(ws, authorized)
    except (WebSocketDisconnect, RuntimeError):
        pass
    except Exception:
        # Do not expose upstream error text, headers or submitted content.
        try:
            await error("STREAM_FAILED")
        except (RuntimeError, WebSocketDisconnect):
            pass
    finally:
        if admitted:
            _active.discard(uid)
        try:
            await ws.close()
        except (RuntimeError, WebSocketDisconnect):
            pass
