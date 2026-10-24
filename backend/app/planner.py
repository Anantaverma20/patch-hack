"""Graph queries for the attendee side: plan, readiness, and Plan Rescue."""
from .graph import now_ms, one, rows

MIN = 60_000
START_ROOM = "hall-a"  # registration desk; where people are before their first session


def sessions_with_room() -> list[dict]:
    return rows(
        "MATCH (s:Session)-[:IN]->(r:Room) "
        "OPTIONAL MATCH (s)-[c:COVERS]->(g:Goal) "
        "WITH s, r, collect({goal:g.id, name:g.name, short:g.short, depth:c.depth}) AS covers "
        "OPTIONAL MATCH (s)-[:REQUIRES]->(k:Check) "
        "RETURN s AS session, r AS room, covers, collect(k.id) AS requires ORDER BY s.start"
    )


def attendee(aid: str) -> dict | None:
    r = one(
        "MATCH (a:Attendee {id:$aid}) "
        "OPTIONAL MATCH (a)-[:WANTS]->(g:Goal) "
        "WITH a, collect(g.id) AS goals "
        "OPTIONAL MATCH (a)-[p:PLANS]->(s:Session) "
        "RETURN a, goals, collect({id:s.id, ackAt:p.at}) AS plans",
        {"aid": aid},
    )
    if not r:
        return None
    a = r["a"]
    a["goals"] = r["goals"]
    a["plans"] = [p for p in r["plans"] if p["id"]]
    return a


def results(aid: str) -> dict:
    rs = rows(
        "MATCH (a:Attendee {id:$aid})-[r:RESULT]->(c:Check) "
        "RETURN c.id AS id, r.status AS status, r.detail AS detail, r.errorCode AS errorCode, "
        "r.at AS at, r.verified AS verified",
        {"aid": aid},
    )
    return {r["id"]: r for r in rs}


def readiness(requires: list[str], res: dict) -> dict:
    passed = [c for c in requires if res.get(c, {}).get("status") == "pass" and res[c].get("verified")]
    missing = [c for c in requires if c not in passed]
    return {"total": len(requires), "passed": len(passed), "missing": missing,
            "ready": len(requires) > 0 and not missing}


_walks: dict[tuple[str, str], tuple[int, bool]] = {}


def walk_minutes(a: str, b: str) -> tuple[int, bool]:
    """Walking time between rooms. The venue's WALK edges never change during the day,
    so they are read from the graph once and cached."""
    if a == b:
        return 0, True
    if not _walks:
        for w in rows("MATCH (x:Room)-[w:WALK]->(y:Room) RETURN x.id AS a, y.id AS b, w.minutes AS m, w.stepFree AS sf"):
            _walks[(w["a"], w["b"])] = _walks[(w["b"], w["a"])] = (w["m"], w["sf"])
    return _walks.get((a, b), (10, True))


def location_before(aid: str, start: int, exclude: str | None = None) -> tuple[str, str]:
    """Room the attendee will be in just before `start`: their latest planned session that
    started earlier (other than `exclude`), else the registration desk."""
    r = one(
        "MATCH (a:Attendee {id:$aid})-[:PLANS]->(s:Session)-[:IN]->(r:Room) "
        "WHERE s.start < $start AND s.id <> $ex AND NOT s.status IN ['cancelled'] "
        "RETURN r.id AS id, r.name AS name ORDER BY s.start DESC LIMIT 1",
        {"aid": aid, "start": start, "ex": exclude or ""},
    )
    return (r["id"], r["name"]) if r else (START_ROOM, "Hall A")


def rescue(aid: str, sid: str) -> dict:
    """Find up to three feasible alternatives for a disrupted session.

    The multi-hop part runs in FalkorDB: attendee -> goals <- sessions -> rooms, plus each
    candidate's required checks joined with this attendee's verified results. Feasibility
    (arrive in time, step-free, no clash) is then applied per candidate, and every
    rejected candidate keeps its reason so the UI can show "why not".
    """
    now = now_ms()
    orig = one(
        "MATCH (s:Session {id:$sid})-[:IN]->(r:Room) RETURN s, r", {"sid": sid})
    a = attendee(aid)
    cands = rows(
        "MATCH (a:Attendee {id:$aid})-[:WANTS]->(g:Goal)<-[cov:COVERS]-(alt:Session)-[:IN]->(r:Room) "
        "WHERE alt.id <> $sid AND NOT (a)-[:PLANS]->(alt) "
        "WITH a, alt, r, collect({id:g.id, name:g.name, short:g.short, depth:cov.depth}) AS goals "
        "OPTIONAL MATCH (alt)-[:REQUIRES]->(c:Check) "
        "OPTIONAL MATCH (a)-[res:RESULT]->(c) "
        "WITH alt, r, goals, collect(c.id) AS requires, "
        "     collect(CASE WHEN res IS NULL OR res.status <> 'pass' OR NOT res.verified THEN c.id END) AS missing "
        "RETURN alt AS s, r AS room, goals, requires, missing",
        {"aid": aid, "sid": sid},
    )
    planned = rows(
        "MATCH (a:Attendee {id:$aid})-[:PLANS]->(s:Session) WHERE s.id <> $sid AND NOT s.status IN ['cancelled','full'] "
        "RETURN s.id AS id, s.title AS title, s.start AS start, s.end AS end",
        {"aid": aid, "sid": sid},
    )
    check_names = {c["id"]: c["name"] for c in rows("MATCH (c:Check) RETURN c.id AS id, c.name AS name")}

    options, rejected = [], []
    for c in cands:
        s, room = c["s"], c["room"]
        from_id, from_name = location_before(aid, s["start"], exclude=sid)
        walk, step_free = walk_minutes(from_id, room["id"])
        best = max(c["goals"], key=lambda g: g["depth"])
        why_not = None
        if s["status"] in ("full", "cancelled"):
            why_not = f"Marked {s['status']} by the organizer"
        elif s["end"] <= now:
            why_not = "Already over"
        elif s["start"] < now + walk * MIN and s["start"] > now - 10 * MIN:
            late = round((now + walk * MIN - s["start"]) / MIN)
            why_not = f"You'd arrive {late} min late ({walk}-min walk from {from_name})"
        elif s["start"] <= now - 10 * MIN:
            why_not = "Started more than 10 minutes ago"
        elif a.get("stepFree") and not step_free:
            why_not = "No step-free route in time"
        else:
            clash = next((p for p in planned if p["start"] < s["end"] and s["start"] < p["end"]), None)
            if clash:
                why_not = f"Overlaps “{clash['title']}” in your day"
        if why_not:
            rejected.append({"id": s["id"], "title": s["title"], "reason": why_not})
            continue
        level_fit = s["level"] == a.get("level") or s["level"] == "beginner" and a.get("level") == "beginner"
        score = best["depth"] * 10 - len(c["missing"]) * 3 - walk * 0.4 + (4 if level_fit else -4) \
            - max(0, (s["start"] - now) / MIN - 30) * 0.05
        seats = max(0, (s.get("capacity") or 0) - (s.get("taken") or 0))
        options.append({
            "session": s, "room": room, "goal": best, "requires": c["requires"],
            "missing": c["missing"], "missingNames": [check_names.get(m, m) for m in c["missing"]],
            "walk": walk, "stepFree": step_free, "from": from_name, "levelFit": level_fit,
            "startsIn": round((s["start"] - now) / MIN), "seats": seats, "score": score,
            "path": [
                {"kind": "goal", "label": f"Your goal: {best['name']}"},
                {"kind": "edge", "label": f"covered in depth {best['depth']}/3"},
                {"kind": "session", "label": s["title"]},
                {"kind": "edge", "label": f"{walk}-min walk from {from_name}"},
                {"kind": "room", "label": room["name"]},
                {"kind": "edge", "label": f"requires {len(c['requires'])} checks"},
                {"kind": "checkwarn" if c["missing"] else "check", "label": f"{len(c['requires']) - len(c['missing'])} of {len(c['requires'])} checks verified" if c["requires"] else "no setup needed"},
            ],
        })
    options.sort(key=lambda o: -o["score"])
    return {"now": now, "original": orig, "options": options[:3], "rejected": rejected}
