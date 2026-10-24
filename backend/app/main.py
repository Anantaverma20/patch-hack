"""Unstuck Live API. Serves the static web app from ../web as well."""
import hmac
import os
import random
import threading
from contextlib import asynccontextmanager

from fastapi import Body, FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import planner, seed
from .graph import bump, now_ms, one, rows, run, version
from .mcp_tools import http_app as mcp_http_app, mcp_server
from .triage import triage

MIN = 60_000
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
HELPERS = ["Leo (workshop TA)", "Mei (volunteer)", "Arjun (volunteer)"]
FIX_TEXT = {
    "endpoint_retired": "The handout listed the retired us-old endpoint. Re-run `python check.py --setup` "
                        "to pull the corrected endpoint (/mock/us-west/v1), then run the check again.",
    "build_tools_missing": "Install the prebuilt wheel instead of building: "
                           "`pip install --only-binary=:all: pyyaml`, then run the check again.",
    "python_too_old": "Create the workshop venv with Python 3.11+: `py -3.11 -m venv .venv-unstuck`.",
}

@asynccontextmanager
async def lifespan(_app):
    _ensure_seeded()
    async with mcp_server.session_manager.run():
        yield


app = FastAPI(title="Unstuck Live", lifespan=lifespan)
_pings: dict[str, int] = {}          # token -> last successful ping to the mock workshop API
_sim = {"pending_until": 0}
_tick_lock = threading.Lock()


def _ensure_seeded() -> None:
    if not one("MATCH (c:Conference) RETURN c.id AS id"):
        seed.reset()


def conference() -> dict:
    return one("MATCH (c:Conference) RETURN c")["c"]


def approved_steps() -> dict[str, list[str]]:
    return {r["id"]: r["steps"] for r in rows("MATCH (c:Check) RETURN c.id AS id, c.approvedSteps AS steps")}


def _tick() -> None:
    """Simulated attendees re-run their checks a few seconds after a fix is published."""
    if not _sim["pending_until"] or not _tick_lock.acquire(blocking=False):
        return
    try:
        now = now_ms()
        due = rows(
            "MATCH (h:HelpReport {status:'fix_sent', simulated:true})-[:FROM]->(a:Attendee), (h)-[:FAILED]->(c:Check) "
            "WHERE h.simResolveAt <= $now RETURN h.id AS id, a.id AS aid, c.id AS cid, h.errorCode AS code",
            {"now": now})
        for d in due:
            run("MATCH (h:HelpReport {id:$id}) SET h.status = 'resolved_verified', h.resolvedAt = $now", {"id": d["id"], "now": now})
            run("MATCH (a:Attendee {id:$aid})-[r:RESULT]->(c:Check) WHERE c.id = $cid OR r.errorCode = 'blocked_by_previous' "
                "SET r.status = 'pass', r.errorCode = '', r.detail = '', r.at = $now, r.verified = true",
                {"aid": d["aid"], "cid": d["cid"], "now": now})
            if d["code"] == "endpoint_retired":
                _set_env(d["aid"], "endpoint", "/mock/us-west/v1")
        if due:
            bump()
        if now > _sim["pending_until"]:
            _sim["pending_until"] = 0
    finally:
        _tick_lock.release()


def _set_env(aid: str, key: str, value: str) -> None:
    run("MATCH (a:Attendee {id:$aid})-[u:USES]->(e:EnvFact {key:$key}) DELETE u", {"aid": aid, "key": key})
    run("MERGE (e:EnvFact {id:$id}) ON CREATE SET e.key = $key, e.value = $value "
        "WITH e MATCH (a:Attendee {id:$aid}) CREATE (a)-[:USES]->(e)",
        {"id": f"{key}:{value}", "key": key, "value": value, "aid": aid})


# ---------------------------------------------------------------- shared

@app.get("/api/health")
def health():
    """For the host's health check: fails when FalkorDB is unreachable, unlike /api/version."""
    try:
        one("RETURN 1 AS ok")
    except Exception as exc:
        return JSONResponse({"ok": False, "falkordb": "unreachable", "error": type(exc).__name__}, 503)
    return {"ok": True, "falkordb": "ok"}


@app.get("/api/version")
def get_version():
    _tick()
    return {"v": version(), "now": now_ms()}


@app.post("/api/reset")
def reset():
    _pings.clear()
    _sim["pending_until"] = 0
    seed.reset()
    return {"ok": True}


@app.get("/api/conference")
def get_conference():
    return {"conference": conference(), "goals": rows("MATCH (g:Goal) RETURN g.id AS id, g.name AS name ORDER BY g.name"),
            "rooms": rows("MATCH (r:Room) RETURN r.id AS id, r.name AS name ORDER BY r.name"),
            "checks": rows("MATCH (c:Check) RETURN c.id AS id, c.name AS name, c.detail AS detail ORDER BY c.id"),
            "helpers": HELPERS, "now": now_ms()}


# ---------------------------------------------------------------- attendee

def _session_view(x: dict, res: dict, now: int) -> dict:
    s = x["session"]
    return {**s, "room": x["room"], "covers": x["covers"], "requires": x["requires"],
            "readiness": planner.readiness(x["requires"], res),
            "seats": max(0, (s.get("capacity") or 0) - (s.get("taken") or 0)),
            "live": s["start"] <= now < s["end"]}


@app.get("/api/me")
def me(aid: str = "a-demo"):
    now = now_ms()
    a = planner.attendee(aid)
    if not a:
        raise HTTPException(404, "attendee not found")
    res = planner.results(aid)
    plan_ids = {p["id"]: p["ackAt"] for p in a["plans"]}
    all_s = planner.sessions_with_room()
    plan = [_session_view(x, res, now) for x in all_s if x["session"]["id"] in plan_ids]
    plan.sort(key=lambda s: s["start"])

    prev_room, prev_end = ("hall-a", None)
    for s in plan:
        s["ackAt"] = plan_ids[s["id"]]
        walk, _ = planner.walk_minutes(prev_room, s["room"]["id"])
        s["travel"] = {"walk": walk, "gap": round((s["start"] - prev_end) / MIN) if prev_end else None}
        if s["status"] not in ("cancelled", "full"):
            prev_room, prev_end = s["room"]["id"], s["end"]

    upcoming = [s for s in plan if s["end"] > now and s["status"] != "cancelled"]
    next_up = next((s for s in upcoming if not s["live"]), None) or (upcoming[0] if upcoming else None)
    current = next((s for s in plan if s["live"] and s["status"] not in ("full", "cancelled")), None)

    attention = []
    for s in upcoming:
        if s["status"] in ("full", "cancelled"):
            attention.append({"id": f"{s['status']}-{s['id']}-{s['statusAt']}", "kind": s["status"], "sessionId": s["id"],
                              "urgent": True, "at": s["statusAt"],
                              "text": f"“{s['title']}” is {'full' if s['status'] == 'full' else 'cancelled'}. View alternatives."})
        elif s["status"] == "moved" and (s["ackAt"] or 0) < s["statusAt"]:
            attention.append({"id": f"moved-{s['id']}-{s['statusAt']}", "kind": "moved", "sessionId": s["id"], "urgent": True,
                              "at": s["statusAt"], "text": f"“{s['title']}” moved to {s['room']['name']}."})
    for s in upcoming:
        if s["requires"] and not s["readiness"]["ready"] and s["status"] not in ("full", "cancelled"):
            attention.append({"id": f"setup-{s['id']}", "kind": "setup", "sessionId": s["id"], "urgent": False,
                              "text": f"Finish setup for “{s['title']}” — {s['readiness']['passed']} of {s['readiness']['total']} checks verified."})

    reports = rows(
        "MATCH (h:HelpReport)-[:FROM]->(a:Attendee {id:$aid}), (h)-[:FAILED]->(c:Check) "
        "OPTIONAL MATCH (h)-[:AT_STEP]->(st:Step) OPTIONAL MATCH (f:Fix)-[:RESOLVES]->(:Cause)-[:EXPLAINS]->(h) "
        "RETURN h AS report, c.id AS checkId, c.name AS checkName, st.title AS step, f AS fix ORDER BY h.at DESC",
        {"aid": aid})
    for r in reports:
        if r["report"]["status"] == "fix_sent":
            attention.insert(0, {"id": f"fix-{r['report']['id']}", "kind": "fix", "urgent": True, "checkId": r["checkId"],
                                 "text": f"The organizer published a fix for your {r['checkName']} blocker. Run the check again."})

    checks = rows("MATCH (c:Check) RETURN c.id AS id, c.name AS name, c.detail AS detail, c.packages AS packages")
    needed = sorted({c for s in upcoming for c in s["requires"]})
    return {"now": now, "attendee": a, "plan": plan, "nextUp": next_up, "current": current, "attention": attention,
            "results": res, "checks": checks, "needed": needed, "reports": reports,
            "endpoint": conference()["endpoint"]}


@app.get("/api/sessions")
def sessions(aid: str = "a-demo"):
    now = now_ms()
    a = planner.attendee(aid)
    res = planner.results(aid)
    plan_ids = {p["id"] for p in a["plans"]}
    out = []
    for x in planner.sessions_with_room():
        s = _session_view(x, res, now)
        s["inPlan"] = s["id"] in plan_ids
        s["fit"] = [c for c in s["covers"] if c["goal"] in a["goals"]]
        out.append(s)
    return {"now": now, "sessions": out, "attendee": a}


@app.get("/api/session/{sid}")
def session_detail(sid: str):
    s = one("MATCH (s:Session {id:$sid})-[:IN]->(r:Room) RETURN s, r", {"sid": sid})
    if not s:
        raise HTTPException(404)
    steps = [r["st"] for r in rows("MATCH (:Session {id:$sid})-[:HAS_STEP]->(st:Step) RETURN st ORDER BY st.n", {"sid": sid})]
    req = rows("MATCH (:Session {id:$sid})-[:REQUIRES]->(c:Check) RETURN c", {"sid": sid})
    return {**s["s"], "room": s["r"], "steps": steps, "checks": [r["c"] for r in req]}


@app.post("/api/onboard")
def onboard(body: dict = Body(...)):
    aid = body.get("aid", "a-demo")
    goals, interests = body.get("goals", []), body.get("interests", [])
    now = now_ms()
    run("MATCH (a:Attendee {id:$aid}) SET a.level = $level, a.stepFree = $sf, a.timeNote = $tn, a.onboarded = true",
        {"aid": aid, "level": body.get("level", "intermediate"), "sf": bool(body.get("stepFree")), "tn": body.get("timeNote", "")})
    run("MATCH (a:Attendee {id:$aid})-[w:WANTS]->() DELETE w", {"aid": aid})
    run("MATCH (a:Attendee {id:$aid})-[p:PLANS]->() DELETE p", {"aid": aid})
    run("UNWIND $g AS gid MATCH (a:Attendee {id:$aid}), (g:Goal {id:gid}) CREATE (a)-[:WANTS]->(g)", {"aid": aid, "g": goals})

    ranked = rows(
        "MATCH (s:Session) WHERE s.end > $now AND s.status <> 'cancelled' "
        "OPTIONAL MATCH (s)-[c:COVERS]->(g:Goal) WHERE g.id IN $goals "
        "RETURN s.id AS id, s.start AS start, s.end AS end, coalesce(max(c.depth), 0) AS depth ORDER BY depth DESC, start",
        {"now": now, "goals": goals})
    chosen: list[dict] = []
    order = [r for r in ranked if r["id"] == "s1"] + [r for r in ranked if r["id"] in interests] + \
            [r for r in ranked if r["depth"] >= 3 and r["id"] not in interests and r["id"] != "s1"]
    for r in order:
        if len(chosen) >= 4:
            break
        if any(c["start"] < r["end"] and r["start"] < c["end"] for c in chosen):
            continue
        chosen.append(r)
    run("UNWIND $ids AS sid MATCH (a:Attendee {id:$aid}), (s:Session {id:sid}) CREATE (a)-[:PLANS {at:$now}]->(s)",
        {"aid": aid, "ids": [c["id"] for c in chosen], "now": now})
    bump()
    return {"plan": [c["id"] for c in chosen]}


@app.post("/api/plan")
def plan(body: dict = Body(...)):
    aid, sid = body.get("aid", "a-demo"), body["sid"]
    if body.get("action") == "remove":
        run("MATCH (a:Attendee {id:$aid})-[p:PLANS]->(s:Session {id:$sid}) DELETE p", {"aid": aid, "sid": sid})
    else:
        run("MATCH (a:Attendee {id:$aid}), (s:Session {id:$sid}) WHERE NOT (a)-[:PLANS]->(s) "
            "CREATE (a)-[:PLANS {at:$now}]->(s)", {"aid": aid, "sid": sid, "now": now_ms()})
    bump()
    return {"ok": True}


@app.post("/api/ack")
def ack(body: dict = Body(...)):
    run("MATCH (a:Attendee {id:$aid})-[p:PLANS]->(s:Session {id:$sid}) SET p.at = $now",
        {"aid": body.get("aid", "a-demo"), "sid": body["sid"], "now": now_ms()})
    bump()
    return {"ok": True}


@app.get("/api/rescue")
def rescue(sid: str, aid: str = "a-demo"):
    return planner.rescue(aid, sid)


@app.post("/api/switch")
def switch(body: dict = Body(...)):
    aid = body.get("aid", "a-demo")
    run("MATCH (a:Attendee {id:$aid})-[p:PLANS]->(s:Session {id:$sid}) DELETE p", {"aid": aid, "sid": body["from"]})
    run("MATCH (a:Attendee {id:$aid}), (s:Session {id:$sid}) CREATE (a)-[:PLANS {at:$now}]->(s)",
        {"aid": aid, "sid": body["to"], "now": now_ms()})
    run("MATCH (s:Session {id:$sid}) SET s.taken = coalesce(s.taken, 0) + 1", {"sid": body["to"]})
    bump()
    return {"ok": True}


# ---------------------------------------------------------------- setup skill + readiness

@app.get("/api/skill/manifest")
def manifest(token: str):
    a = one("MATCH (a:Attendee {token:$t}) RETURN a.id AS id, a.name AS name", {"t": token})
    if not a:
        raise HTTPException(401, "unknown token")
    now = now_ms()
    req = rows(
        "MATCH (a:Attendee {id:$aid})-[:PLANS]->(s:Session)-[:REQUIRES]->(c:Check) "
        "WHERE s.end > $now AND NOT s.status IN ['cancelled', 'full'] "
        "RETURN DISTINCT c.id AS id, c.name AS name, c.kind AS kind, c.packages AS packages",
        {"aid": a["id"], "now": now})
    if not any(c["id"] == "runtime" for c in req):
        req.insert(0, {"id": "runtime", "name": "Required runtime", "kind": "runtime", "packages": []})
    order = ["runtime", "deps-core", "deps-evals", "service", "exercise"]
    req.sort(key=lambda c: order.index(c["id"]) if c["id"] in order else 99)
    return {"attendee": a["name"], "checks": req, "endpoint": conference()["endpoint"], "key": token, "minPython": "3.10"}


@app.get("/mock/{region}/v1/ping")
def mock_ping(region: str, x_workshop_key: str | None = Header(default=None)):
    """Stand-in for the workshop's hosted API. us-old was retired mid-morning."""
    if region == "us-old":
        return JSONResponse({"error": "endpoint_retired", "message": "Region us-old was retired at 9:00. Use us-west."}, 410)
    if region != "us-west":
        return JSONResponse({"error": "not_found"}, 404)
    if not x_workshop_key or not one("MATCH (a:Attendee {token:$t}) RETURN a.id AS id", {"t": x_workshop_key}):
        return JSONResponse({"error": "auth_rejected", "message": "Missing or unknown workshop key."}, 401)
    _pings[x_workshop_key] = now_ms()
    return {"ok": True, "region": region, "model": "workshop-eval-1"}


@app.post("/api/readiness")
def readiness(body: dict = Body(...)):
    """Accepts the structured report from check.py. Readiness comes only from these results;
    service access is additionally cross-checked against the server's own ping log."""
    if not body.get("consent"):
        raise HTTPException(400, "consent required")
    token = body.get("token", "")
    a = one("MATCH (a:Attendee {token:$t}) RETURN a.id AS id", {"t": token})
    if not a:
        raise HTTPException(401, "unknown token")
    now, aid = now_ms(), a["id"]
    simulated = bool(body.get("simulated"))
    accepted = []
    for r in body.get("results", [])[:10]:
        cid, status = str(r.get("checkId", "")), r.get("status")
        if status not in ("pass", "fail"):
            continue
        verified = status == "pass"
        if cid == "service" and status == "pass" and not simulated:
            verified = now - _pings.get(token, 0) < 10 * MIN
        run("MATCH (a:Attendee {id:$aid}), (c:Check {id:$cid}) "
            "MERGE (a)-[r:RESULT]->(c) SET r.status = $st, r.detail = $d, r.errorCode = $code, r.at = $now, "
            "r.verified = $v, r.source = $src",
            {"aid": aid, "cid": cid, "st": status, "d": str(r.get("detail", ""))[:300], "code": str(r.get("errorCode", ""))[:60],
             "now": now, "v": verified, "src": "simulated" if simulated else "skill"})
        if status == "pass" and verified:
            run("MATCH (h:HelpReport)-[:FROM]->(:Attendee {id:$aid}), (h)-[:FAILED]->(:Check {id:$cid}) "
                "WHERE h.status IN ['open', 'fix_sent'] SET h.status = 'resolved_verified', h.resolvedAt = $now",
                {"aid": aid, "cid": cid, "now": now})
        accepted.append({"checkId": cid, "status": status, "verified": verified})
    env = body.get("env") or {}
    for key in ("os", "python", "endpoint"):
        if env.get(key):
            val = str(env[key])
            if key == "endpoint" and "/mock/" in val:
                val = val[val.index("/mock/"):].rstrip("/")
            _set_env(aid, key, val[:80])
    bump()
    return {"accepted": accepted}


@app.post("/api/simulate-report")
def simulate_report(body: dict = Body(...)):
    """Backup for the stage: the same report a local run would send, clearly labelled simulated."""
    aid = body.get("aid", "a-demo")
    a = one("MATCH (a:Attendee {id:$aid}) RETURN a.token AS t", {"aid": aid})
    m = manifest(a["t"])
    retired = m["endpoint"].endswith("us-old/v1")
    results = []
    for c in m["checks"]:
        if c["id"] == "service" and retired:
            results.append({"checkId": "service", "status": "fail", "errorCode": "endpoint_retired",
                            "detail": f"410 Gone from {m['endpoint']}/ping — endpoint retired"})
        elif c["id"] == "exercise" and retired:
            results.append({"checkId": "exercise", "status": "fail", "errorCode": "blocked_by_previous",
                            "detail": "Skipped: Service access failed"})
        else:
            results.append({"checkId": c["id"], "status": "pass", "detail": "ok"})
    return readiness({"token": a["t"], "consent": True, "simulated": True, "results": results,
                      "env": {"os": "macos", "python": "3.12", "endpoint": m["endpoint"]}})


# ---------------------------------------------------------------- help

@app.post("/api/help")
def help_report(body: dict = Body(...)):
    aid = body.get("aid", "a-demo")
    t = triage(body.get("error", ""), body.get("checkId") or None, approved_steps())
    rid = f"r-{aid}-{now_ms()}"
    run("MATCH (a:Attendee {id:$aid}), (c:Check {id:$cid}) "
        "CREATE (h:HelpReport {id:$rid, at:$now, error:$err, errorCode:$code, summary:$sum, status:'open', helper:'', "
        "simulated:false, needsHelper:false, agent:$agent})-[:FROM]->(a), (h)-[:FAILED]->(c)",
        {"aid": aid, "cid": t["checkId"], "rid": rid, "now": now_ms(), "err": body.get("error", "")[:2000],
         "code": t["errorCode"], "sum": t["summary"], "agent": t["agent"]})
    if body.get("sessionId"):
        run("MATCH (h:HelpReport {id:$rid}), (s:Session {id:$sid}) CREATE (h)-[:IN_SESSION]->(s)", {"rid": rid, "sid": body["sessionId"]})
    if body.get("stepId"):
        run("MATCH (h:HelpReport {id:$rid}), (s:Step {id:$st}) CREATE (h)-[:AT_STEP]->(s)", {"rid": rid, "st": body["stepId"]})
    if t.get("endpoint"):
        _set_env(aid, "endpoint", t["endpoint"])
    if t["checkId"]:
        run("MATCH (a:Attendee {id:$aid}), (c:Check {id:$cid}) MERGE (a)-[r:RESULT]->(c) "
            "ON CREATE SET r.status = 'fail', r.detail = $d, r.errorCode = $code, r.at = $now, r.verified = false, r.source = 'report'",
            {"aid": aid, "cid": t["checkId"], "d": t["summary"], "code": t["errorCode"], "now": now_ms()})
    bump()
    return {"id": rid, **t}


@app.post("/api/help/{rid}/escalate")
def escalate(rid: str):
    run("MATCH (h:HelpReport {id:$rid}) SET h.needsHelper = true", {"rid": rid})
    bump()
    return {"ok": True}


@app.post("/api/help/{rid}/confirm")
def confirm(rid: str):
    run("MATCH (h:HelpReport {id:$rid}) WHERE h.status IN ['open', 'fix_sent'] SET h.status = 'resolved_self', h.resolvedAt = $now",
        {"rid": rid, "now": now_ms()})
    bump()
    return {"ok": True}


# ---------------------------------------------------------------- organizer

@app.get("/api/org/sessions")
def org_sessions():
    now = now_ms()
    out = []
    counts = {r["id"]: r for r in rows(
        "MATCH (s:Session) OPTIONAL MATCH (a:Attendee)-[:PLANS]->(s) RETURN s.id AS id, count(a) AS planned")}
    ready = {r["id"]: r["ready"] for r in rows(
        "MATCH (a:Attendee)-[:PLANS]->(s:Session)-[:REQUIRES]->(c:Check) "
        "OPTIONAL MATCH (a)-[r:RESULT {status:'pass'}]->(c) WHERE r.verified "
        "WITH s, a, count(c) AS need, count(r) AS ok WITH s, sum(CASE WHEN need = ok THEN 1 ELSE 0 END) AS ready "
        "RETURN s.id AS id, ready")}
    for x in planner.sessions_with_room():
        s = x["session"]
        out.append({**s, "room": x["room"], "requires": x["requires"], "covers": x["covers"],
                    "planned": counts.get(s["id"], {}).get("planned", 0), "ready": ready.get(s["id"]),
                    "live": s["start"] <= now < s["end"]})
    return {"now": now, "sessions": out}


@app.post("/api/org/sessions/{sid}/status")
def set_status(sid: str, body: dict = Body(...)):
    status, room = body["status"], body.get("room")
    if status not in ("open", "full", "moved", "cancelled"):
        raise HTTPException(400, "status must be open, full, moved or cancelled")
    if not one("MATCH (s:Session {id:$sid}) RETURN s.id AS id", {"sid": sid}):
        raise HTTPException(404, f"unknown session {sid}")
    if status == "moved" and not (room and one("MATCH (r:Room {id:$room}) RETURN r.id AS id", {"room": room})):
        raise HTTPException(400, "moved needs an existing room")
    run("MATCH (s:Session {id:$sid}) SET s.status = $st, s.statusAt = $now, s.statusSource = 'organizer'",
        {"sid": sid, "st": status, "now": now_ms()})
    if status == "full":
        run("MATCH (s:Session {id:$sid}) SET s.taken = s.capacity", {"sid": sid})
    if status == "moved":
        # Single query: if the room didn't match, nothing is deleted.
        run("MATCH (s:Session {id:$sid}), (r:Room {id:$room}) OPTIONAL MATCH (s)-[i:IN]->() DELETE i "
            "WITH DISTINCT s, r CREATE (s)-[:IN]->(r)", {"sid": sid, "room": room})
    bump()
    return {"ok": True}


@app.post("/api/org/sessions")
def add_session(body: dict = Body(...)):
    now = now_ms()
    sid = f"s-{now}"
    start = now + int(body.get("startIn", 30)) * MIN
    props = {"id": sid, "title": body["title"], "speaker": body.get("speaker", ""), "format": body.get("format", "talk"),
             "level": body.get("level", "intermediate"), "start": start, "end": start + int(body.get("duration", 45)) * MIN,
             "outcomes": [o for o in body.get("outcomes", []) if o], "summary": body.get("summary", ""), "capacity": int(body.get("capacity", 40)),
             "taken": 0, "materials": [], "status": "open", "statusAt": now, "statusSource": "organizer"}
    run("MATCH (r:Room {id:$room}) CREATE (s:Session)-[:IN]->(r) SET s = $p", {"room": body.get("room", "hall-a"), "p": props})
    if body.get("goal"):
        run("MATCH (s:Session {id:$sid}), (g:Goal {id:$g}) CREATE (s)-[:COVERS {depth:$d}]->(g)",
            {"sid": sid, "g": body["goal"], "d": int(body.get("depth", 2))})
    run("UNWIND $req AS c MATCH (s:Session {id:$sid}), (k:Check {id:c}) CREATE (s)-[:REQUIRES]->(k)",
        {"sid": sid, "req": body.get("requires", [])})
    bump()
    return {"id": sid}


@app.get("/api/org/readiness")
def org_readiness():
    per = rows(
        "MATCH (s:Session)-[:REQUIRES]->(c:Check) "
        "OPTIONAL MATCH (a:Attendee)-[:PLANS]->(s) "
        "OPTIONAL MATCH (a)-[r:RESULT]->(c) "
        "RETURN s.id AS sid, s.title AS title, s.start AS start, c.id AS cid, c.name AS check, count(DISTINCT a) AS planned, "
        "sum(CASE WHEN r.status = 'pass' AND r.verified THEN 1 ELSE 0 END) AS pass, "
        "sum(CASE WHEN r.status = 'fail' THEN 1 ELSE 0 END) AS fail ORDER BY start, cid")
    sessions: dict[str, dict] = {}
    for r in per:
        s = sessions.setdefault(r["sid"], {"id": r["sid"], "title": r["title"], "start": r["start"], "checks": []})
        s["checks"].append({"id": r["cid"], "name": r["check"], "planned": r["planned"], "pass": r["pass"], "fail": r["fail"]})
    failures = rows(
        "MATCH (a:Attendee)-[r:RESULT {status:'fail'}]->(c:Check) WHERE r.errorCode <> 'blocked_by_previous' "
        "RETURN c.name AS check, r.errorCode AS code, count(a) AS n, collect(r.detail)[0] AS example ORDER BY n DESC")
    packages = [r["p"] for r in rows("MATCH (p:SkillPackage) RETURN p ORDER BY p.name")]
    return {"sessions": list(sessions.values()), "failures": failures, "packages": packages}


@app.post("/api/org/packages/{pid}/{action}")
def package_action(pid: str, action: str):
    if action == "sandbox":
        run("MATCH (p:SkillPackage {id:$pid}) SET p.sandbox = 'passed', p.sandboxAt = $now", {"pid": pid, "now": now_ms()})
    elif action == "publish":
        run("MATCH (p:SkillPackage {id:$pid}) WHERE p.sandbox = 'passed' SET p.status = 'published', p.reviewedAt = $now",
            {"pid": pid, "now": now_ms()})
    bump()
    return {"ok": True}


def clusters() -> list[dict]:
    """Group open reports by shared symptom, then look for an environment fact every reporter
    shares, and count how many attendees who *passed* the same check also have it."""
    groups = rows(
        "MATCH (h:HelpReport)-[:FAILED]->(c:Check), (h)-[:FROM]->(a:Attendee) "
        "WHERE h.status IN ['open', 'fix_sent'] "
        "OPTIONAL MATCH (h)-[:AT_STEP]->(st:Step) "
        "RETURN c.id AS checkId, c.name AS check, h.errorCode AS code, "
        "collect({id:h.id, aid:a.id, name:a.name, error:h.error, at:h.at, status:h.status, helper:h.helper, "
        "needsHelper:h.needsHelper, step:st.title, summary:h.summary}) AS reports")
    out = []
    for g in groups:
        aids = sorted({r["aid"] for r in g["reports"]})
        facts = rows(
            "MATCH (a:Attendee)-[:USES]->(e:EnvFact) WHERE a.id IN $aids "
            "WITH e, count(DISTINCT a) AS n WHERE n = $total "
            "OPTIONAL MATCH (p:Attendee)-[:RESULT {status:'pass'}]->(:Check {id:$cid}) WHERE (p)-[:USES]->(e) "
            "RETURN e.key AS key, e.value AS value, n, count(DISTINCT p) AS passing",
            {"aids": aids, "total": len(aids), "cid": g["checkId"]})
        passers = one("MATCH (p:Attendee)-[:RESULT {status:'pass'}]->(:Check {id:$cid}) RETURN count(p) AS n",
                      {"cid": g["checkId"]})["n"]
        facts.sort(key=lambda f: f["passing"])
        best = facts[0] if facts else None
        strength = "strong" if best and best["passing"] == 0 and len(aids) >= 3 else ("weak" if best else "none")
        out.append({**g, "attendees": len(aids), "fact": best, "facts": facts, "passersTotal": passers, "strength": strength,
                    "fixSent": all(r["status"] == "fix_sent" for r in g["reports"]),
                    "suggestedFix": FIX_TEXT.get(g["code"], "")})
    out.sort(key=lambda c: -c["attendees"])
    return out


@app.get("/api/org/help")
def org_help():
    resolved = rows(
        "MATCH (h:HelpReport)-[:FROM]->(a:Attendee), (h)-[:FAILED]->(c:Check) "
        "WHERE h.status IN ['resolved_verified', 'resolved_self'] "
        "RETURN h.id AS id, a.name AS name, c.name AS check, h.status AS status, h.resolvedAt AS at ORDER BY at DESC")
    fixes = [r["f"] for r in rows("MATCH (f:Fix) RETURN f ORDER BY f.at DESC")]
    return {"now": now_ms(), "clusters": clusters(), "resolved": resolved, "fixes": fixes, "helpers": HELPERS}


@app.post("/api/org/help/assign")
def assign(body: dict = Body(...)):
    run("MATCH (h:HelpReport) WHERE h.id IN $ids SET h.helper = $helper", {"ids": body["ids"], "helper": body["helper"]})
    bump()
    return {"ok": True}


@app.post("/api/org/fix")
def publish_fix(body: dict = Body(...)):
    """Organizer-approved fix for a shared cause. Reports move to fix_sent; they only count as
    resolved once the attendee's check passes again (or they explicitly confirm)."""
    now = now_ms()
    fid = f"fix-{now}"
    ids = [r["id"] for r in rows("MATCH (h:HelpReport) WHERE h.id IN $ids AND h.status = 'open' RETURN h.id AS id",
                                 {"ids": body["ids"]})]
    if not ids:
        raise HTTPException(409, "no open reports to send a fix to")
    run("CREATE (f:Fix {id:$fid, text:$text, at:$now, approvedBy:'Organizer', checkId:$cid, factKey:$k, factValue:$v})"
        "-[:RESOLVES]->(:Cause {id:$cause, check:$cid, factKey:$k, factValue:$v, confirmed:false})",
        {"fid": fid, "text": body["text"], "now": now, "cid": body.get("checkId", ""), "k": body.get("key", ""),
         "v": body.get("value", ""), "cause": f"cause-{now}"})
    run("MATCH (c:Cause {id:$cause}), (h:HelpReport) WHERE h.id IN $ids CREATE (c)-[:EXPLAINS]->(h) SET h.status = 'fix_sent'",
        {"cause": f"cause-{now}", "ids": ids})
    if body.get("key") == "endpoint":
        run("MATCH (c:Conference) SET c.endpoint = '/mock/us-west/v1'")
    for rid in ids:
        run("MATCH (h:HelpReport {id:$id, simulated:true}) SET h.simResolveAt = $t",
            {"id": rid, "t": now + random.randint(3, 9) * 1000})
    _sim["pending_until"] = now + 12_000
    bump()
    return {"id": fid}


# ---------------------------------------------------------------- MCP (agent harnesses)

@app.middleware("http")
async def mcp_auth(request: Request, call_next):
    """/mcp requires `Authorization: Bearer <MCP_TOKEN>`; without MCP_TOKEN configured it stays off."""
    if not request.url.path.startswith("/mcp"):
        return await call_next(request)
    token = os.getenv("MCP_TOKEN")
    if not token:
        return JSONResponse({"error": "MCP is disabled until MCP_TOKEN is configured"}, 503)
    given = request.headers.get("authorization", "").removeprefix("Bearer ").strip()
    if not hmac.compare_digest(given, token):
        return JSONResponse({"error": "unauthorized"}, 401)
    return await call_next(request)


app.router.routes.extend(mcp_http_app.routes)


# ---------------------------------------------------------------- static

@app.get("/skill/{name}")
def skill_file(name: str):
    if name not in ("SKILL.md", "check.py"):
        raise HTTPException(404)
    return FileResponse(os.path.join(ROOT, "skill", "unstuck-setup", name), media_type="text/plain")


app.mount("/", StaticFiles(directory=os.path.join(ROOT, "web"), html=True), name="web")
