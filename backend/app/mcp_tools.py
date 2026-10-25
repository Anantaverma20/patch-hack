"""MCP server so agent harnesses (TrueForge, Claude, Codex) can work the organizer side.

Read tools answer from the FalkorDB graph. Write tools change what attendees see, so the
harness should require human approval for them (TrueForge: require_approval_for_tools).
"""
from fastapi import HTTPException
from mcp.server.fastmcp import FastMCP
from mcp.server.fastmcp.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from mcp.types import ToolAnnotations

mcp_server = FastMCP(
    "unstuck",
    instructions=(
        "Organizer tools for the Unstuck conference companion. Shared symptoms are only a "
        "possible common cause: check get_blocker_evidence before proposing a fix, and never "
        "publish a fix without the organizer's approval. Do not solve attendees' exercises. "
        "A blocker group is identified by (check_id, error_code) from list_shared_blockers."
    ),
    stateless_http=True,
    json_response=True,
    streamable_http_path="/mcp",
    # Served behind a public hostname (Render), not only localhost.
    transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
)

READ = ToolAnnotations(readOnlyHint=True, destructiveHint=False)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)


def _group(check_id: str, error_code: str) -> dict:
    """Refusals raise ToolError so MCP clients get an error result (isError), not a success."""
    from . import main

    c = next((c for c in main.clusters() if c["checkId"] == check_id and c["code"] == error_code), None)
    if not c:
        raise ToolError(f"No open blocker group for check_id='{check_id}', error_code='{error_code}'. "
                        "Call list_shared_blockers for the current groups.")
    return c


@mcp_server.tool(annotations=READ)
def list_shared_blockers() -> list[dict]:
    """Open help reports grouped by (check_id, error_code), with the environment fact all reporters
    share and how many attendees who PASSED the same check also have it (0 = strong lead)."""
    from . import main

    return [{
        "check_id": c["checkId"], "error_code": c["code"], "check": c["check"], "attendees": c["attendees"],
        "open_reports": sum(r["status"] == "open" for r in c["reports"]),
        "shared_fact": c["fact"], "passers_total": c["passersTotal"], "signal": c["strength"],
        "fix_already_sent": c["fixSent"], "suggested_fix": c["suggestedFix"],
    } for c in main.clusters()]


@mcp_server.tool(annotations=READ)
def get_blocker_evidence(check_id: str, error_code: str) -> dict:
    """Reports, error messages, steps and shared environment facts behind one blocker group."""
    c = _group(check_id, error_code)
    return {"check": c["check"], "error_code": c["code"], "facts": c["facts"], "passers_total": c["passersTotal"],
            "reports": [{"attendee": r["name"], "step": r["step"], "error": r["error"], "status": r["status"],
                         "asked_for_helper": r["needsHelper"]} for r in c["reports"]]}


@mcp_server.tool(annotations=READ)
def get_readiness_summary() -> dict:
    """Per-session setup check pass/fail counts and the most common setup failures."""
    from . import main

    r = main.org_readiness()
    return {"sessions": r["sessions"], "top_failures": r["failures"][:5]}


@mcp_server.tool(annotations=READ)
def list_sessions() -> list[dict]:
    """Sessions across the conference week with day, venue time (San Francisco), room, status,
    attendance and how many planned attendees are setup-ready."""
    from . import main, seed

    days = main.conference().get("days") or []
    return [{"id": s["id"], "title": s["title"], "day": days[s.get("day", 0)] if s.get("day", 0) < len(days) else "",
             "starts": seed.fmt_local(s["start"]), "start_ms": s["start"], "format": s["format"],
             "room": s["room"]["name"], "status": s["status"], "planned": s["planned"], "setup_ready": s["ready"],
             "seats": f"{s['taken']}/{s['capacity']}"} for s in main.org_sessions()["sessions"]]


@mcp_server.tool(annotations=WRITE)
def publish_fix(check_id: str, error_code: str, fix_text: str) -> dict:
    """Send an organizer-approved fix to the attendees in one blocker group whose reports are still
    open; anyone who already received a fix is skipped. Reports only close when each attendee's
    check passes again. Requires human approval."""
    from . import main

    c = _group(check_id, error_code)
    open_ids = [r["id"] for r in c["reports"] if r["status"] == "open"]
    if not open_ids:
        raise ToolError("Every report in this group already received a fix; waiting for re-checks.")
    fact = c["fact"] or {}
    main.publish_fix({"ids": open_ids, "text": fix_text, "checkId": check_id,
                      "key": fact.get("key", ""), "value": fact.get("value", "")})
    return {"published_to_reports": len(open_ids), "check": c["check"], "error_code": error_code}


@mcp_server.tool(annotations=WRITE)
def assign_helper(check_id: str, error_code: str, helper: str) -> dict:
    """Assign a helper to every report in one blocker group."""
    from . import main

    c = _group(check_id, error_code)
    main.assign({"ids": [r["id"] for r in c["reports"]], "helper": helper})
    return {"assigned": helper, "reports": len(c["reports"])}


@mcp_server.tool(annotations=WRITE)
def set_session_status(session_id: str, status: str, room_id: str = "") -> dict:
    """Publish a live session update: status is open, full, moved (needs an existing room_id) or
    cancelled. Attendees with the session in their day see it immediately. Requires human approval."""
    from . import main

    try:
        main.set_status(session_id, {"status": status, "room": room_id or None})
    except HTTPException as e:
        raise ToolError(f"Session update rejected: {e.detail}") from e
    return {"session": session_id, "status": status, "room": room_id or None}


http_app = mcp_server.streamable_http_app()
