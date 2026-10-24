"""Proxy between the organizer pop-up and the TrueForge copilot agent.

TrueForge runs the agent (OpenAI model + Unstuck MCP tools + approvals); this module only
starts sessions, sends turns, waits for them to settle, and relays approval decisions.
Disabled unless TRUEFORGE_URL is set.
"""
import json
import os
import time
import urllib.error
import urllib.request

from fastapi import APIRouter, Body, HTTPException

router = APIRouter(prefix="/api/copilot")
AGENT = os.getenv("TRUEFORGE_AGENT", "unstuck-organizer-copilot")


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


def _settle(session_id: str, turn_id: str) -> dict:
    """Wait for a turn to finish or pause, then summarise it for the pop-up."""
    deadline = time.time() + 120
    while True:
        state = _call("GET", f"/sessions/{session_id}/turns/{turn_id}").get("state", {})
        if state.get("status") not in ("running", "queued", "pending") or time.time() > deadline:
            break
        time.sleep(1.5)
    approvals = []
    actions = state.get("required_actions") or []
    if actions:
        calls = {}
        for e in _call("GET", f"/sessions/{session_id}/turns/{turn_id}/events") or []:
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
                approvals.append({"tool_call_id": tc["id"], "thread_id": a.get("thread_id", "main"),
                                  "tool": args.get("tool_name", fn.get("name", "tool")), "input": args.get("input", args)})
    return {"session_id": session_id, "turn_id": turn_id, "status": state.get("status"),
            "content": (state.get("output") or {}).get("content") or state.get("message") or "",
            "approvals": approvals}


@router.get("/status")
def status():
    return {"enabled": bool(os.getenv("TRUEFORGE_URL")), "agent": AGENT}


@router.post("/message")
def message(body: dict = Body(...)):
    text = str(body.get("text", "")).strip()[:2000]
    if not text:
        raise HTTPException(400, "empty message")
    sid = body.get("session_id") or _call("POST", "/sessions", {"agent": {"name": AGENT}})["id"]
    turn = {"input": [{"type": "user.message", "content": text}], "stream": False}
    if body.get("previous_turn_id"):
        turn["previous_turn_id"] = body["previous_turn_id"]
    tid = _call("POST", f"/sessions/{sid}/turns", turn)["id"]
    return _settle(sid, tid)


@router.post("/approve")
def approve(body: dict = Body(...)):
    sid = body["session_id"]
    decision = {"status": "allow"} if body.get("allow") else {"status": "deny"}
    turn = {"input": [{"type": "user.tool_approval", "thread_id": body.get("thread_id", "main"),
                       "tool_call_id": body["tool_call_id"], "approval": decision}],
            "previous_turn_id": body["previous_turn_id"], "stream": False}
    tid = _call("POST", f"/sessions/{sid}/turns", turn)["id"]
    return _settle(sid, tid)
