"""MCP server so agent harnesses (TrueForge, Claude, Codex) can work the organizer side.

Read tools answer from the FalkorDB graph. Write tools change what attendees see, so the
harness should require human approval for them (TrueForge: require_approval_for_tools).
"""
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

mcp_server = FastMCP(
    "unstuck",
    instructions=(
        "Organizer tools for the Unstuck conference companion. Shared symptoms are only a "
        "possible common cause: check get_blocker_evidence before proposing a fix, and never "
        "publish a fix without the organizer's approval. Do not solve attendees' exercises."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
    # Served behind a public hostname (Render), not only localhost.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


@mcp_server.tool(annotations=READ)
def list_shared_blockers() -> list[dict]:
    """Open help reports grouped by failed check, with the environment fact all reporters share
    and how many attendees who PASSED the same check also have it (0 = strong lead)."""
    from . import main

    return [{
        "check_id": c["checkId"], "check": c["check"], "error_code": c["code"], "attendees": c["attendees"],
        "shared_fact": c["fact"], "passers_total": c["passersTotal"], "signal": c["strength"],
        "fix_already_sent": c["fixSent"], "suggested_fix": c["suggestedFix"],
    } for c in main.clusters()]


@mcp_server.tool(annotations=READ)
def get_blocker_evidence(check_id: str) -> dict:
    """Reports, error messages, steps and shared environment facts behind one blocker group."""
    from . import main

    for c in main.clusters():
        if c["checkId"] == check_id:
            return {"check": c["check"], "facts": c["facts"], "passers_total": c["passersTotal"],
                    "reports": [{"attendee": r["name"], "step": r["step"], "error": r["error"],
                                 "status": r["status"], "asked_for_helper": r["needsHelper"]} for r in c["reports"]]}
    return {"error": f"No open reports for check '{check_id}'."}


@mcp_server.tool(annotations=READ)
def get_readiness_summary() -> dict:
    """Per-session setup check pass/fail counts and the most common setup failures."""
    from . import main

    r = main.org_readiness()
    return {"sessions": r["sessions"], "top_failures": r["failures"][:5]}


@mcp_server.tool(annotations=READ)
def list_sessions() -> list[dict]:
    """Sessions with time, room, status, attendance and how many planned attendees are setup-ready."""
    from . import main

    return [{"id": s["id"], "title": s["title"], "room": s["room"]["name"], "status": s["status"],
             "start_ms": s["start"], "planned": s["planned"], "setup_ready": s["ready"],
             "seats": f"{s['taken']}/{s['capacity']}"} for s in main.org_sessions()["sessions"]]


@mcp_server.tool(annotations=WRITE)
def publish_fix(check_id: str, fix_text: str) -> dict:
    """Send an organizer-approved fix to every attendee in the open blocker group for check_id.
    Reports only close when each attendee's check passes again. Requires human approval."""
    from . import main

    c = next((c for c in main.clusters() if c["checkId"] == check_id and not c["fixSent"]), None)
    if not c:
        return {"error": f"No open blocker group for check '{check_id}'."}
    fact = c["fact"] or {}
    main.publish_fix({"ids": [r["id"] for r in c["reports"]], "text": fix_text, "checkId": check_id,
                      "key": fact.get("key", ""), "value": fact.get("value", "")})
    return {"published_to": c["attendees"], "check": c["check"]}


@mcp_server.tool(annotations=WRITE)
def assign_helper(check_id: str, helper: str) -> dict:
    """Assign a helper to every open report in the blocker group for check_id."""
    from . import main

    c = next((c for c in main.clusters() if c["checkId"] == check_id), None)
    if not c:
        return {"error": f"No open blocker group for check '{check_id}'."}
    main.assign({"ids": [r["id"] for r in c["reports"]], "helper": helper})
    return {"assigned": helper, "reports": len(c["reports"])}


@mcp_server.tool(annotations=WRITE)
def set_session_status(session_id: str, status: str, room_id: str = "") -> dict:
    """Publish a live session update: status is open, full, moved (needs room_id) or cancelled.
    Attendees with the session in their day see it immediately. Requires human approval."""
    from . import main

    if status not in ("open", "full", "moved", "cancelled"):
        return {"error": "status must be open, full, moved or cancelled"}
    main.set_status(session_id, {"status": status, "room": room_id or None})
    return {"session": session_id, "status": status}


http_app = mcp_server.streamable_http_app()
