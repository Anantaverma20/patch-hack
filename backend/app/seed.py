"""Seeds the fictional "Future / Forward" conference.

Times are relative to the moment of reset so the demo always starts "live":
the keynote is ending, the evals workshop starts in ~15 minutes.
"""
import random

from .graph import G, bump, now_ms, run

MIN = 60_000

ROOMS = [
    {"id": "hall-a", "name": "Hall A", "floor": 1},
    {"id": "room-b", "name": "Room B", "floor": 1},
    {"id": "room-c", "name": "Room C", "floor": 1},
    {"id": "atrium", "name": "Atrium", "floor": 1},
    {"id": "lab-1", "name": "Lab 1", "floor": 2},
    {"id": "lab-2", "name": "Lab 2", "floor": 2},
]

# Walking minutes between rooms (symmetric). stepFree=False means the fastest route uses stairs.
WALKS = [
    ("hall-a", "room-b", 3, True), ("hall-a", "room-c", 4, True), ("hall-a", "atrium", 8, True),
    ("hall-a", "lab-1", 6, False), ("hall-a", "lab-2", 9, False),
    ("room-b", "room-c", 2, True), ("room-b", "atrium", 6, True), ("room-b", "lab-1", 5, False),
    ("room-b", "lab-2", 7, False), ("room-c", "atrium", 5, True), ("room-c", "lab-1", 6, False),
    ("room-c", "lab-2", 8, False), ("atrium", "lab-1", 7, True), ("atrium", "lab-2", 9, True),
    ("lab-1", "lab-2", 3, True),
]

GOALS = [
    {"id": "evals", "name": "Evaluate AI agents", "short": "agent evaluation"},
    {"id": "rag", "name": "Build RAG pipelines", "short": "retrieval"},
    {"id": "prod", "name": "Ship agents to production", "short": "shipping agents"},
    {"id": "prompting", "name": "Prompt engineering", "short": "prompting"},
]

CHECKS = [
    {"id": "runtime", "name": "Required runtime", "kind": "runtime", "packages": [],
     "detail": "Python 3.10 or newer",
     "approvedSteps": ["Run `python --version` and confirm 3.10+", "Use the workshop venv: `python -m venv .venv-unstuck`"]},
    {"id": "deps-core", "name": "Workshop dependencies", "kind": "deps", "packages": ["pyyaml", "tabulate"],
     "detail": "pyyaml, tabulate",
     "approvedSteps": ["Activate `.venv-unstuck`", "Run `pip install pyyaml tabulate`", "Re-run the check"]},
    {"id": "service", "name": "Service access", "kind": "service", "packages": [],
     "detail": "Workshop API key + endpoint",
     "approvedSteps": ["Open `workshop.env` and confirm WORKSHOP_ENDPOINT", "Confirm WORKSHOP_KEY is set (re-run `check.py --setup`)", "Re-run the check"]},
    {"id": "exercise", "name": "Sample exercise", "kind": "exercise", "packages": [],
     "detail": "Runs the starter eval and compares output",
     "approvedSteps": ["Make sure Workshop dependencies pass first", "Re-run the check and paste the full output"]},
    {"id": "deps-evals", "name": "Trace grader package", "kind": "deps", "packages": ["jsonschema"],
     "detail": "jsonschema",
     "approvedSteps": ["Activate `.venv-unstuck`", "Run `pip install jsonschema`", "Re-run the check"]},
]

STEPS = {
    "s2": ["Clone the starter repo", "Load the eval dataset", "Call the workshop API", "Write your first grader", "Compare two agent runs"],
    "s3": ["Install the trace grader", "Capture an agent trace", "Call the workshop API", "Grade tool-call accuracy", "Report a regression"],
    "s4": ["Pick a target app", "Write five attack prompts", "Score the responses"],
    "s6": ["Chunk the sample docs", "Embed and index", "Answer three questions"],
    "s7": ["Package the agent", "Add tracing", "Call the workshop API", "Deploy behind a feature flag"],
}


def _sessions(t0: int):
    def s(id, title, speaker, room, start, dur, fmt, level, covers, requires, outcomes, summary, capacity=60, taken=20):
        return {
            "id": id, "title": title, "speaker": speaker, "room": room,
            "start": t0 + start * MIN, "end": t0 + (start + dur) * MIN,
            "format": fmt, "level": level, "covers": covers, "requires": requires,
            "outcomes": outcomes, "summary": summary, "capacity": capacity, "taken": taken,
            "materials": [f"Slides — {title}", "Starter repo (github.com/future-forward/" + id + ")"] if fmt == "workshop" else [f"Slides — {title}"],
        }

    return [
        s("s1", "Opening keynote: Agents in the Wild", "Dana Okafor", "hall-a", -40, 45, "talk", "beginner",
          {"evals": 1, "prod": 1}, [], ["Where agents fail in production today", "What changed this year"],
          "The state of agent deployments, failure stories, and what the day covers.", 800, 640),
        s("s2", "Agent Evals, Hands-on", "Priya Natarajan", "lab-1", 15, 60, "workshop", "intermediate",
          {"evals": 3}, ["runtime", "deps-core", "service", "exercise"],
          ["Build an eval set from real traces", "Write an LLM-as-judge grader", "Compare two agent versions"],
          "Build an evaluation harness for a tool-using agent, from dataset to regression report.", 40, 38),
        s("s3", "Grading Agent Traces", "Marco Lindqvist", "room-b", 20, 60, "workshop", "intermediate",
          {"evals": 3, "prod": 1}, ["runtime", "deps-core", "service", "deps-evals"],
          ["Capture structured traces", "Grade tool-call accuracy", "Catch regressions before release"],
          "Evaluate agents step by step by grading their traces instead of only final answers.", 50, 31),
        s("s4", "Red-teaming LLM Apps", "Ines Duarte", "lab-2", 20, 60, "workshop", "advanced",
          {"evals": 2}, ["runtime", "deps-core"],
          ["Design adversarial test cases", "Score jailbreak resistance"],
          "Attack your own app before someone else does. Assumes prior eval experience.", 30, 19),
        s("s5", "Benchmarks Aren't Evals", "Kofi Mensah", "atrium", 5, 30, "talk", "beginner",
          {"evals": 2}, [], ["Why leaderboard scores mislead", "Choosing task-specific metrics"],
          "A short talk on why public benchmarks rarely predict how your agent behaves.", 120, 64),
        s("s6", "RAG From Scratch", "Lena Fischer", "room-c", 15, 60, "workshop", "beginner",
          {"rag": 3}, ["runtime", "deps-core"], ["Chunk and embed documents", "Evaluate retrieval quality"],
          "Build a retrieval pipeline end to end with no framework.", 40, 27),
        s("s8", "Prompt Patterns That Last", "Sam Whitfield", "hall-a", 90, 30, "talk", "beginner",
          {"prompting": 3}, [], ["Reusable prompt structures", "When to stop prompting and start evaluating"],
          "Patterns that survive model upgrades.", 800, 300),
        s("s10", "Vector Search Deep Dive", "Aiko Tanaka", "room-c", 90, 45, "talk", "advanced",
          {"rag": 2}, [], ["Index trade-offs", "Hybrid search"], "How vector indexes actually behave at scale.", 60, 22),
        s("s7", "Shipping Agents to Production", "Rafael Ortiz", "lab-2", 130, 60, "workshop", "intermediate",
          {"prod": 3, "evals": 1}, ["runtime", "deps-core", "service", "exercise"],
          ["Package and trace an agent", "Roll out behind a flag", "Monitor regressions"],
          "Take a working agent and make it safe to ship.", 40, 22),
        s("s9", "Agent Eval Office Hours", "Priya Natarajan", "atrium", 200, 60, "office hours", "intermediate",
          {"evals": 2}, [], ["Bring your eval questions", "Review your grader with an expert"],
          "Drop-in help on evaluation design with the Agent Evals instructors.", 30, 6),
    ]


FIRST = ["Ava", "Ben", "Chen", "Diego", "Elif", "Farah", "Gus", "Hana", "Ivan", "Jade", "Kai", "Luis",
         "Mina", "Noor", "Omar", "Pia", "Quinn", "Ravi", "Sofia", "Tariq", "Uma", "Vik", "Wen", "Yara"]


def reset() -> int:
    t0 = (now_ms() // MIN) * MIN
    rnd = random.Random(7)
    try:
        G.delete()
    except Exception:
        pass

    run("CREATE (:Conference {id:'ff', name:'Future / Forward', city:'San Francisco', dates:'Oct 24, 2026', "
        "venue:'Moscone West', endpoint:'/mock/us-old/v1', t0:$t0})", {"t0": t0})
    run("UNWIND $rows AS r CREATE (x:Room) SET x = r", {"rows": ROOMS})
    run("UNWIND $rows AS r MATCH (a:Room {id:r[0]}), (b:Room {id:r[1]}) "
        "CREATE (a)-[:WALK {minutes:r[2], stepFree:r[3]}]->(b)", {"rows": [list(w) for w in WALKS]})
    run("UNWIND $rows AS r CREATE (x:Goal) SET x = r", {"rows": GOALS})
    run("UNWIND $rows AS r CREATE (x:Check) SET x = r", {"rows": CHECKS})
    run("CREATE (:SkillPackage {id:'pkg-evals', name:'agent-evals-setup', version:'1.2.0', status:'published', "
        "reviewedAt:$t, sandbox:'passed'}), "
        "(:SkillPackage {id:'pkg-traces', name:'trace-grader-addon', version:'0.3.0', status:'published', "
        "reviewedAt:$t, sandbox:'passed'}), "
        "(:SkillPackage {id:'pkg-prod', name:'ship-agents-setup', version:'0.9.0', status:'in review', sandbox:'not run'})",
        {"t": t0 - 90 * MIN})
    run("MATCH (c:Check), (p:SkillPackage {id:'pkg-evals'}) WHERE c.id <> 'deps-evals' CREATE (c)-[:PROVIDED_BY]->(p)")
    run("MATCH (c:Check {id:'deps-evals'}), (p:SkillPackage {id:'pkg-traces'}) CREATE (c)-[:PROVIDED_BY]->(p)")

    sessions = _sessions(t0)
    for s in sessions:
        props = {k: v for k, v in s.items() if k not in ("covers", "requires", "room")}
        props.update(status="open", statusAt=t0 - 30 * MIN, statusSource="organizer")
        run("MATCH (r:Room {id:$room}) CREATE (s:Session)-[:IN]->(r) SET s = $p",
            {"room": s["room"], "p": props})
        run("UNWIND $cov AS c MATCH (s:Session {id:$sid}), (g:Goal {id:c[0]}) CREATE (s)-[:COVERS {depth:c[1]}]->(g)",
            {"sid": s["id"], "cov": [[g, d] for g, d in s["covers"].items()]})
        run("UNWIND $req AS c MATCH (s:Session {id:$sid}), (k:Check {id:c}) CREATE (s)-[:REQUIRES]->(k)",
            {"sid": s["id"], "req": s["requires"]})
        steps = [{"id": f"{s['id']}-st{i + 1}", "n": i + 1, "title": t} for i, t in enumerate(STEPS.get(s["id"], []))]
        run("UNWIND $steps AS st MATCH (s:Session {id:$sid}) CREATE (s)-[:HAS_STEP]->(x:Step) SET x = st",
            {"sid": s["id"], "steps": steps})

    # The sample attendee: starts un-onboarded so the demo shows the join flow.
    run("CREATE (:Attendee {id:'a-demo', name:'Jordan Lee', level:'intermediate', token:'demo-7Q4K', sample:true, "
        "onboarded:false, stepFree:false, timeNote:''})")

    _seed_crowd(rnd, t0)
    bump()
    return t0


def _seed_crowd(rnd: random.Random, t0: int) -> None:
    """24 simulated attendees with check results. Five are stuck on service access and
    all of them still use the retired us-old endpoint from the original handout."""
    old_ep, new_ep = "/mock/us-old/v1", "/mock/us-west/v1"
    stuck_service = set(range(5))
    stuck_deps_win = {5, 6, 7}
    attendees, results, uses, plans, reports = [], [], [], [], []
    for i, first in enumerate(FIRST):
        aid = f"a{i:02d}"
        os_name = "windows" if i in stuck_deps_win or i % 3 == 0 else ("macos" if i % 3 == 1 else "linux")
        py = "3.9" if i == 9 else rnd.choice(["3.11", "3.12", "3.12", "3.13"])
        ep = old_ep if i in stuck_service else new_ep
        attendees.append({"id": aid, "name": f"{first} {chr(65 + (i * 7) % 26)}.", "level": rnd.choice(["beginner", "intermediate", "intermediate", "advanced"]),
                          "token": f"tok-{aid}", "sample": False, "onboarded": True, "stepFree": i == 11})
        uses += [[aid, "os", os_name], [aid, "python", py], [aid, "endpoint", ep]]
        for sid in ["s1", "s2"] + rnd.sample(["s3", "s4", "s6", "s7", "s9"], 2):
            plans.append([aid, sid])
        for chk in ["runtime", "deps-core", "service", "exercise"]:
            status, code, detail = "pass", "", ""
            if chk == "runtime" and py == "3.9":
                status, code, detail = "fail", "python_too_old", "Python 3.9.6 found; 3.10+ required"
            if chk == "service" and i in stuck_service:
                status, code, detail = "fail", "endpoint_retired", f"410 Gone from {old_ep}/ping"
            if chk == "deps-core" and i in stuck_deps_win and i != 7:
                status, code, detail = "fail", "build_tools_missing", "pyyaml wheel build failed: Microsoft Visual C++ 14.0 required"
            if chk == "exercise" and (i in stuck_service or i in stuck_deps_win or py == "3.9"):
                status, code, detail = "fail", "blocked_by_previous", "Skipped: earlier check failed"
            results.append([aid, chk, status, code, detail, t0 - rnd.randint(20, 300) * MIN])
        if i in stuck_service:
            reports.append({"id": f"r-{aid}", "aid": aid, "session": "s2", "step": "s2-st3", "check": "service",
                            "error": f"HTTPError: 410 Gone for url: https://api.workshop.dev{old_ep}/ping — endpoint retired",
                            "errorCode": "endpoint_retired", "at": t0 - rnd.randint(2, 25) * MIN})
        if i in (5, 6):
            reports.append({"id": f"r-{aid}", "aid": aid, "session": "s2", "step": "s2-st1", "check": "deps-core",
                            "error": "error: Microsoft Visual C++ 14.0 or greater is required (building wheel for pyyaml)",
                            "errorCode": "build_tools_missing", "at": t0 - rnd.randint(5, 40) * MIN})

    run("UNWIND $rows AS r CREATE (a:Attendee) SET a = r", {"rows": attendees})
    run("UNWIND $rows AS r MERGE (e:EnvFact {id: r[1] + ':' + r[2]}) ON CREATE SET e.key = r[1], e.value = r[2] "
        "WITH e, r MATCH (a:Attendee {id:r[0]}) CREATE (a)-[:USES]->(e)", {"rows": uses})
    run("UNWIND $rows AS r MATCH (a:Attendee {id:r[0]}), (s:Session {id:r[1]}) CREATE (a)-[:PLANS {at:0}]->(s)", {"rows": plans})
    run("UNWIND $rows AS r MATCH (a:Attendee {id:r[0]}), (c:Check {id:r[1]}) "
        "CREATE (a)-[:RESULT {status:r[2], errorCode:r[3], detail:r[4], at:r[5], verified:r[2]='pass', source:'skill'}]->(c)",
        {"rows": results})
    run("UNWIND $rows AS r MATCH (a:Attendee {id:r.aid}), (s:Session {id:r.session}), (st:Step {id:r.step}), (c:Check {id:r.check}) "
        "CREATE (h:HelpReport {id:r.id, at:r.at, error:r.error, errorCode:r.errorCode, status:'open', helper:'', "
        "simulated:true, needsHelper:false})-[:FROM]->(a), (h)-[:IN_SESSION]->(s), (h)-[:AT_STEP]->(st), (h)-[:FAILED]->(c)",
        {"rows": reports})
