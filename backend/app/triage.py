"""Turns a free-text "I'm stuck" report into graph facts.

Rules always run so the demo never depends on a model call. When OPENAI_API_KEY is set,
an OpenAI model refines the summary and picks which of the organizer's *approved*
troubleshooting steps apply; it can never invent new steps.
"""
import json
import os
import re

ENDPOINT_RE = re.compile(r"/mock/([\w-]+)/v1")
HTTP_RE = re.compile(r"\b(401|403|404|410|429|500|502|503)\b")


def rules(error: str, check_hint: str | None) -> dict:
    e = error or ""
    low = e.lower()
    out = {"checkId": check_hint, "errorCode": "", "endpoint": None, "summary": ""}
    m = ENDPOINT_RE.search(e)
    if m:
        out["endpoint"] = f"/mock/{m.group(1)}/v1"
    code = HTTP_RE.search(e)
    if "retired" in low or (code and code.group(1) == "410"):
        out.update(checkId=out["checkId"] or "service", errorCode="endpoint_retired",
                   summary="Workshop API rejects the configured endpoint (410 Gone / retired).")
    elif code and code.group(1) in ("401", "403"):
        out.update(checkId=out["checkId"] or "service", errorCode="auth_rejected",
                   summary="Workshop API rejected the key.")
    elif "visual c++" in low or "building wheel" in low:
        out.update(checkId=out["checkId"] or "deps-core", errorCode="build_tools_missing",
                   summary="A dependency needs a compiler that isn't installed.")
    elif "modulenotfounderror" in low or "no module named" in low:
        mod = re.search(r"no module named ['\"]?([\w.]+)", low)
        out.update(checkId=out["checkId"] or "deps-core", errorCode="module_missing",
                   summary=f"Python package {mod.group(1) if mod else ''} isn't installed.".replace("  ", " "))
    elif re.search(r"python 3\.[0-9]\b", low) and "required" in low:
        out.update(checkId=out["checkId"] or "runtime", errorCode="python_too_old",
                   summary="Python version is older than the workshop needs.")
    elif "connection" in low or "timed out" in low:
        out.update(checkId=out["checkId"] or "service", errorCode="unreachable",
                   summary="Can't reach the workshop API.")
    else:
        out.update(checkId=out["checkId"] or "exercise", errorCode="unknown",
                   summary="Unrecognised error; needs a person to look.")
    return out


def triage(error: str, check_hint: str | None, approved_steps: dict[str, list[str]]) -> dict:
    base = rules(error, check_hint)
    base["agent"] = "rules"
    base["steps"] = approved_steps.get(base["checkId"], [])
    key = os.getenv("OPENAI_API_KEY")
    if not key or not error.strip():
        return base
    try:
        from openai import OpenAI

        client = OpenAI(api_key=key, timeout=8)
        steps = approved_steps.get(base["checkId"], [])
        prompt = (
            "You triage setup blockers at a hands-on AI workshop. Do not solve the learning exercise.\n"
            f"Error text:\n{error[:2000]}\n\nRule-based guess: {json.dumps(base)}\n"
            f"Organizer-approved troubleshooting steps (you may only choose from these, by index): {json.dumps(steps)}\n"
            'Reply as JSON: {"summary": one plain sentence, "stepIndexes": [ints]}'
        )
        r = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        data = json.loads(r.choices[0].message.content)
        idx = [i for i in data.get("stepIndexes", []) if isinstance(i, int) and 0 <= i < len(steps)]
        base.update(summary=data.get("summary") or base["summary"], steps=[steps[i] for i in idx] or steps,
                    agent=os.getenv("OPENAI_MODEL", "gpt-5-mini"))
    except Exception as exc:  # model trouble must never block the attendee
        base["agentError"] = str(exc)[:200]
    return base
