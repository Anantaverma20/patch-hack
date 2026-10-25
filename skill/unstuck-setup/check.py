#!/usr/bin/env python3
"""Unstuck workshop readiness check.

Deterministic: every result comes from running a real check on this machine, never from
an agent's judgement. Standard library only, so it runs before anything is installed.

  python check.py --server URL --token TOKEN --setup      write workshop.env (endpoint + key)
  python check.py --server URL --token TOKEN --packages   print packages to pip install
  python check.py --server URL --token TOKEN --install    pip install them into this Python
  python check.py --server URL --token TOKEN              run checks and print results
  python check.py --server URL --token TOKEN --send       ...then ask consent and report

What --send reports: check ids, pass/fail, short error codes/details, OS name, Python
version and the endpoint path. No keys, environment variables or file contents.
"""
import argparse
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

ENV_FILE = "workshop.env"
# Plain distribution names only, so nothing from the manifest can be read as a pip option.
PACKAGE_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
IMPORT_NAMES = {"pyyaml": "yaml", "scikit-learn": "sklearn"}
# The only programs check.py will run. The manifest can name a tool, never a command line.
TOOLS = {
    "git": {"label": "Git", "version": ["git", "--version"]},
    "node": {"label": "Node.js", "version": ["node", "--version"]},
    "docker": {"label": "Docker", "version": ["docker", "--version"], "running": ["docker", "info", "--format", "{{.ServerVersion}}"]},
}


def http(method, url, body=None, headers=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read() or b"{}")
        except ValueError:
            return e.code, {}


def read_env():
    env = {}
    if os.path.exists(ENV_FILE):
        for line in open(ENV_FILE, encoding="utf-8"):
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env


def check_runtime(manifest):
    need = tuple(int(x) for x in manifest.get("minPython", "3.10").split("."))
    have = sys.version_info[:2]
    ver = platform.python_version()
    if have >= need:
        return "pass", f"Python {ver}", ""
    return "fail", f"Python {ver} found; {'.'.join(map(str, need))}+ required", "python_too_old"


def check_packages(pkgs):
    missing = [p for p in pkgs if importlib.util.find_spec(IMPORT_NAMES.get(p, p)) is None]
    if missing:
        return "fail", "missing: " + ", ".join(missing), "module_missing"
    return "pass", "installed: " + ", ".join(pkgs), ""


def _run(cmd, timeout=20):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout or r.stderr).strip().splitlines()[0:1]
    except (OSError, subprocess.TimeoutExpired) as e:
        return 1, [str(e)]


def check_tool(c):
    tool = TOOLS.get(c.get("command", ""))
    if not tool:
        return "fail", f"unknown tool {c.get('command')!r}", "unknown_tool"
    if not shutil.which(tool["version"][0]):
        return "fail", f"{tool['label']} not found on PATH", "tool_missing"
    code, out = _run(tool["version"])
    line = out[0] if out else ""
    if code != 0:
        return "fail", f"{tool['label']} found but `{' '.join(tool['version'])}` failed: {line}", "tool_missing"
    need = c.get("minVersion")
    have = re.search(r"(\d+)\.(\d+)", line)
    if need and have and int(have.group(1)) < int(need.split(".")[0]):
        return "fail", f"{tool['label']} {line} found; {need}+ required", "tool_too_old"
    if "running" in tool:
        code, out = _run(tool["running"])
        if code != 0:
            return "fail", f"{tool['label']} is installed but not running ({out[0] if out else 'no response'})", "docker_not_running"
        return "pass", f"{line}, engine {out[0] if out else 'running'}", ""
    return "pass", line, ""


def check_service(server):
    env = read_env()
    endpoint, key = env.get("WORKSHOP_ENDPOINT"), env.get("WORKSHOP_KEY")
    if not endpoint or not key:
        return "fail", f"{ENV_FILE} missing endpoint or key (run --setup)", "not_signed_in"
    url = endpoint if endpoint.startswith("http") else server.rstrip("/") + endpoint
    try:
        code, body = http("GET", url.rstrip("/") + "/ping", headers={"X-Workshop-Key": key})
    except Exception as e:  # network trouble is a result, not a crash
        return "fail", f"cannot reach {endpoint}: {e}", "unreachable"
    if code == 200:
        return "pass", f"{endpoint} ok", ""
    if code == 410:
        return "fail", f"410 Gone from {endpoint}/ping - {body.get('message', 'endpoint retired')}", "endpoint_retired"
    if code in (401, 403):
        return "fail", f"{code} from {endpoint}: key rejected", "auth_rejected"
    return "fail", f"HTTP {code} from {endpoint}", f"http_{code}"


def check_exercise():
    """The starter eval from the workshop repo, inlined: grade 4 agent answers, expect 0.75."""
    if importlib.util.find_spec("yaml") is None:
        return "fail", "Skipped: Workshop dependencies missing", "blocked_by_previous"
    import yaml

    data = yaml.safe_load(
        "- {q: capital of France, expected: paris, got: Paris}\n"
        "- {q: 2+2, expected: '4', got: '4'}\n"
        "- {q: largest planet, expected: jupiter, got: Saturn}\n"
        "- {q: H2O is, expected: water, got: water}\n")
    acc = sum(r["expected"].lower() == str(r["got"]).lower() for r in data) / len(data)
    if abs(acc - 0.75) < 1e-9:
        return "pass", "starter eval accuracy=0.75 (expected 0.75)", ""
    return "fail", f"starter eval accuracy={acc} (expected 0.75)", "wrong_output"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", default="http://localhost:8000")
    ap.add_argument("--token", required=True)
    ap.add_argument("--setup", action="store_true")
    ap.add_argument("--packages", action="store_true")
    ap.add_argument("--install", action="store_true")
    ap.add_argument("--send", action="store_true")
    ap.add_argument("--yes", action="store_true", help="consent already given by the attendee")
    a = ap.parse_args()

    code, manifest = http("GET", f"{a.server.rstrip('/')}/api/skill/manifest?token={a.token}")
    if code != 200:
        sys.exit(f"Could not load the workshop manifest (HTTP {code}). Check --server and --token.")

    if a.setup:
        with open(ENV_FILE, "w", encoding="utf-8") as f:
            f.write(f"WORKSHOP_ENDPOINT={manifest['endpoint']}\nWORKSHOP_KEY={manifest['key']}\n")
        print(f"Wrote {ENV_FILE} (endpoint {manifest['endpoint']}).")
        return
    packages = sorted({p for c in manifest["checks"] for p in c.get("packages", [])})
    if a.packages:
        print(" ".join(packages))
        return
    if a.install:
        bad = [p for p in packages if not PACKAGE_RE.match(p)]
        if bad:
            sys.exit(f"Refusing to install unexpected package names from the manifest: {bad}")
        # Same interpreter that runs the checks, so it works in any shell and any active venv.
        if packages:
            subprocess.run([sys.executable, "-m", "pip", "install", *packages], check=True)
        print("Installed: " + (", ".join(packages) or "nothing needed"))
        return

    results = []
    for c in manifest["checks"]:
        if c["kind"] == "runtime":
            st, detail, err = check_runtime(manifest)
        elif c["kind"] == "deps":
            st, detail, err = check_packages(c.get("packages", []))
        elif c["kind"] == "tool":
            st, detail, err = check_tool(c)
        elif c["kind"] == "service":
            st, detail, err = check_service(a.server)
        elif c["kind"] == "exercise":
            st, detail, err = check_exercise()
        else:
            continue
        results.append({"checkId": c["id"], "name": c["name"], "status": st, "detail": detail, "errorCode": err})

    print(f"\nUnstuck readiness for {manifest['attendee']}\n")
    for r in results:
        mark = "PASS" if r["status"] == "pass" else "FAIL"
        print(f"  [{mark}] {r['name']:<26} {r['detail']}")
    passed = all(r["status"] == "pass" for r in results)
    print("\n" + ("Your environment passed this workshop's checks." if passed else "Some checks failed. See details above."))
    print("RESULT_JSON " + json.dumps({"results": results}))

    if not a.send:
        return
    if not a.yes:
        ans = input("\nSend these results to Unstuck? Only check ids, pass/fail, short errors, OS, Python version "
                    "and endpoint path are sent. [y/N] ").strip().lower()
        if ans not in ("y", "yes"):
            print("Not sent.")
            return
    env = read_env()
    payload = {"token": a.token, "consent": True,
               "results": [{k: r[k] for k in ("checkId", "status", "detail", "errorCode")} for r in results],
               "env": {"os": {"Darwin": "macos", "Windows": "windows"}.get(platform.system(), "linux"),
                       "python": ".".join(platform.python_version().split(".")[:2]),
                       "endpoint": env.get("WORKSHOP_ENDPOINT", "")}}
    code, body = http("POST", f"{a.server.rstrip('/')}/api/readiness", payload)
    print("Sent." if code == 200 else f"Report failed (HTTP {code}): {body}")


if __name__ == "__main__":
    main()
