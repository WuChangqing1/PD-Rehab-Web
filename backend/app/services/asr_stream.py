"""Bounded, memory-only Fun-ASR protocol. Never log audio, text or credentials."""
from __future__ import annotations

import asyncio
import json
import re
import time
import uuid
from urllib.parse import urlsplit

from websockets.asyncio.client import connect
from app.core.config import settings


def valid_endpoint(value: str) -> bool:
    try:
        u = urlsplit(value)
        host = u.hostname or ""
        return bool(u.scheme == "wss" and u.port in (None, 443) and not u.username
                    and not u.password and not u.query and not u.fragment
                    and u.path == "/api-ws/v1/inference"
                    and (host == "dashscope.aliyuncs.com" or re.fullmatch(
                        r"[a-zA-Z0-9-]+\.cn-beijing\.maas\.aliyuncs\.com", host)))
    except ValueError:
        return False


def available() -> bool:
    return bool(settings.asr_enabled and settings.asr_api_key.strip()
                and settings.asr_model == "fun-asr-realtime" and valid_endpoint(settings.asr_ws_url))


class NoRedirectConnect(connect):
    def process_redirect(self, exc):
        # Do not carry the bearer credential to a redirected host.
        return exc


def open_provider():
    if not available():
        raise ValueError("ASR unavailable")
    return NoRedirectConnect(settings.asr_ws_url,
        additional_headers={"Authorization": "Bearer " + settings.asr_api_key.strip()},
        open_timeout=10, close_timeout=2, max_size=65536, max_queue=8)


class AudioBudget:
    def __init__(self, started: float):
        self.started, self.total = started, 0

    def accept(self, data: bytes, now: float):
        total = self.total + len(data)
        if (not data or len(data) % 2 or len(data) > 16000 or total > 60 * 32000
                or now - self.started > 75 or total > (max(0, now-self.started)+2) * 32000):
            raise ValueError("Audio limit")
        self.total = total


class Transcript:
    def __init__(self):
        self.parts = {}
        self.final = set()

    def apply(self, sentence: dict) -> str:
        if sentence.get("heartbeat"):
            return self.text()
        # sentence_id remains stable even when the provider revises begin_time.
        key = ("id", sentence["sentence_id"]) if "sentence_id" in sentence else ("time", sentence["begin_time"])
        if key not in self.final:
            self.parts[key] = str(sentence.get("text", ""))[:3000]
            if sentence.get("sentence_end", sentence.get("end_time") is not None):
                self.final.add(key)
        if len(self.parts) > 200 or sum(map(len, self.parts.values())) > 3000:
            raise ValueError("Text limit")
        return self.text()

    def text(self):
        return "".join(self.parts[k] for k in sorted(self.parts))


def command(action: str, task_id: str):
    payload = {"input": {}}
    if action == "run-task":
        payload.update(task_group="audio", task="asr", function="recognition",
                       model=settings.asr_model, parameters={"format": "pcm", "sample_rate": 16000})
    return json.dumps({"header": {"action": action, "task_id": task_id, "streaming": "duplex"}, "payload": payload})


async def relay(ws, authorized):
    async with open_provider() as provider:
        task_id = str(uuid.uuid4())
        await provider.send(command("run-task", task_id))
        start = json.loads(await asyncio.wait_for(provider.recv(), 10))
        if start.get("header", {}).get("event") != "task-started":
            raise ValueError("Provider startup failed")
        await ws.send_json({"type": "ready"})
        budget, transcript = AudioBudget(time.monotonic()), Transcript()
        stopping = False

        async def upstream():
            nonlocal stopping
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    return
                if not authorized():
                    await ws.send_json({"type": "error", "code": "AUTH_REQUIRED"})
                    return
                if message.get("bytes") is not None:
                    if stopping:
                        raise ValueError("Audio after stop")
                    data = message["bytes"]
                    budget.accept(data, time.monotonic())
                    await provider.send(data)
                else:
                    raw = message.get("text", "")
                    if len(raw) > 1024:
                        raise ValueError("Control limit")
                    control = json.loads(raw).get("type")
                    if control == "cancel":
                        return
                    if control != "stop" or stopping:
                        raise ValueError("Invalid control")
                    stopping = True
                    await provider.send(command("finish-task", task_id))
                    # Keep listening for disconnect/cancel; provider drain is bounded.

        async def downstream():
            while True:
                event = json.loads(await provider.recv())
                kind = event.get("header", {}).get("event")
                if not authorized():
                    await ws.send_json({"type": "error", "code": "AUTH_REQUIRED"})
                    return
                if kind == "result-generated":
                    text = transcript.apply(event["payload"]["output"]["sentence"])
                    await ws.send_json({"type": "transcript", "text": text})
                elif kind == "task-finished":
                    if not stopping:
                        raise ValueError("Unexpected finish")
                    await ws.send_json({"type": "done"})
                    return
                elif kind == "task-failed":
                    raise ValueError("Provider failed")

        async def watchdog():
            started = time.monotonic()
            stop_seen = None
            while True:
                await asyncio.sleep(.25)
                now = time.monotonic()
                if not authorized():
                    await ws.send_json({"type": "error", "code": "AUTH_REQUIRED"})
                    return
                if stopping and stop_seen is None:
                    stop_seen = now
                if now-started > 75 or stop_seen is not None and now-stop_seen > 10:
                    raise ValueError("ASR timeout")

        tasks = [asyncio.create_task(fn()) for fn in (upstream, downstream, watchdog)]
        try:
            done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
