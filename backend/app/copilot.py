"""Proxy between the organizer pop-up and the TrueForge copilot agent.

TrueForge runs the agent (OpenAI model + Unstuck MCP tools + approvals); this module only
starts sessions, sends turns, waits for them to settle, and relays approval decisions.
Disabled unless TRUEFORGE_URL is set.
"""
import asyncio
import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api/copilot")
AGENT = os.getenv("TRUEFORGE_AGENT", "unstuck-organizer-copilot")
# Approvals this server handed to the pop-up: (session_id, turn_id, tool_call_id). Only these can be decided.
_issued: set[tuple[str, str, str]] = set()


def _base() -> str:
    url = os.getenv("TRUEFORGE_URL", "").rstrip("/")
    if not url:
        raise HTTPException(503, "Copilot is not configured (TRUEFORGE_URL).")
    return url + "/api/v1"


def _call(method: str, path: str, body: dict | None = None) -> dict:
    req = urllib.request.Request(_base() + path, method=method, headers={"Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get("data", {})
    except urllib.error.HTTPError as e:
        raise HTTPException(502, f"TrueForge returned {e.code}: {e.read()[:200].decode(errors='replace')}")
    except (urllib.error.URLError, TimeoutError) as e:
        raise HTTPException(502, f"TrueForge unreachable: {e}")


async def _acall(method: str, path: str, body: dict | None = None):
    return await asyncio.to_thread(_call, method, path, body)


async def _settle(session_id: str, turn_id: str) -> dict:
    """Wait (without holding a worker thread) for a turn to finish or pause, then summarise it."""
    deadline = time.time() + 120
    while True:
        state = (await _acall("GET", f"/sessions/{session_id}/turns/{turn_id}")).get("state", {})
        if state.get("status") not in ("running", "queued", "pending"):
            break
        if time.time() > deadline:
            return {"session_id": session_id, "turn_id": turn_id, "status": "timeout", "approvals": [],
                    "content": "The copilot is still working on this. Ask again in a moment."}
        await asyncio.sleep(1.5)
    approvals = []
    actions = state.get("required_actions") or []
    if actions:
        calls = {}
        for e in await _acall("GET", f"/sessions/{session_id}/turns/{turn_id}/events") or []:
            for tc in e.get("tool_calls") or []:
                if tc.get("function"):  # the approval event repeats the id without the call details
                    calls[tc["id"]] = tc
        for a in actions:
            for tc in a.get("tool_calls", []):
                fn = calls.get(tc["id"], {}).get("function", {})
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except ValueError:
                    args = {}
                _issued.add((session_id, turn_id, tc["id"]))
                approvals.append({"tool_call_id": tc["id"], "thread_id": a.get("thread_id", "main"),
                                  "tool": args.get("tool_name", fn.get("name", "tool")), "input": args.get("input", args)})
    return {"session_id": session_id, "turn_id": turn_id, "status": state.get("status"),
            "content": (state.get("output") or {}).get("content") or state.get("message") or "",
            "approvals": approvals}


@router.get("/status")
def status():
    return {"enabled": bool(os.getenv("TRUEFORGE_URL")), "agent": AGENT}


@router.post("/message")
async def message(body: dict = Body(...)):
    text = str(body.get("text", "")).strip()[:2000]
    if not text:
        raise HTTPException(400, "empty message")
    sid = body.get("session_id") or (await _acall("POST", "/sessions", {"agent": {"name": AGENT}}))["id"]
    turn = {"input": [{"type": "user.message", "content": text}], "stream": False}
    if body.get("previous_turn_id"):
        turn["previous_turn_id"] = body["previous_turn_id"]
    tid = (await _acall("POST", f"/sessions/{sid}/turns", turn))["id"]
    return await _settle(sid, tid)


@router.post("/approve")
async def approve(body: dict = Body(...)):
    sid = body["session_id"]
    key = (sid, body.get("previous_turn_id"), body.get("tool_call_id"))
    if key not in _issued:
        raise HTTPException(403, "Unknown or already decided approval.")
    allow = body.get("allow") is True  # only a JSON true approves
    decision = {"status": "allow"} if allow else {"status": "deny"}
    turn = {"input": [{"type": "user.tool_approval", "thread_id": body.get("thread_id", "main"),
                       "tool_call_id": body["tool_call_id"], "approval": decision}],
            "previous_turn_id": body["previous_turn_id"], "stream": False}
    tid = (await _acall("POST", f"/sessions/{sid}/turns", turn))["id"]
    _issued.discard(key)
    return await _settle(sid, tid)
