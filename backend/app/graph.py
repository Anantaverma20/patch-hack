"""FalkorDB connection and small helpers.

Every piece of Unstuck state (attendees, goals, sessions, rooms, checks, results,
help reports, fixes) lives in one graph so planner, setup skill and triage share it.
"""
import os
import threading
import time

from dotenv import load_dotenv
from falkordb import FalkorDB
from falkordb.node import Node
from falkordb.edge import Edge

load_dotenv(os.path.join(os.path.dirname(__file__), "..", "..", ".env"))

_db = FalkorDB(
    host=os.getenv("FALKOR_HOST", "localhost"),
    port=int(os.getenv("FALKOR_PORT", "6379")),
    username=os.getenv("FALKOR_USERNAME") or None,
    password=os.getenv("FALKOR_PASSWORD") or None,
    ssl=os.getenv("FALKOR_SSL", "false").lower() == "true",
)
G = _db.select_graph(os.getenv("UNSTUCK_GRAPH", "unstuck"))

_version = 0
_lock = threading.Lock()


def now_ms() -> int:
    return int(time.time() * 1000)


def bump() -> int:
    """Increment the change counter clients poll to know when to refetch."""
    global _version
    with _lock:
        _version += 1
        return _version


def version() -> int:
    return _version


def _plain(v):
    if isinstance(v, (Node, Edge)):
        return dict(v.properties)
    if isinstance(v, list):
        return [_plain(x) for x in v]
    if isinstance(v, dict):
        return {k: _plain(x) for k, x in v.items()}
    return v


def rows(query: str, params: dict | None = None) -> list[dict]:
    res = G.query(query, params or {})
    names = [h[1] for h in res.header]
    return [{n: _plain(v) for n, v in zip(names, r)} for r in res.result_set]


def run(query: str, params: dict | None = None) -> None:
    G.query(query, params or {})


def one(query: str, params: dict | None = None) -> dict | None:
    r = rows(query, params)
    return r[0] if r else None
