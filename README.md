# Unstuck Live

> "The instructor moved on. You're still stuck on step three."

Unstuck helps conference attendees **get ready**, **get into the right session**, and **keep going when something breaks**, and shows organizers which problems are shared.

| Stage | What Unstuck does |
|---|---|
| Before | An organizer-approved setup skill prepares the attendee's laptop with their own Claude Code or Codex. `check.py` verifies it. |
| Choosing sessions | Shows goal fit, recommended level and verified technical readiness as separate signals. |
| During | Room changes, full or cancelled sessions trigger **Plan Rescue**: feasible alternatives by goal, time, walk and setup. |
| Inside the session | "I'm stuck" reports are triaged and grouped by shared cause. The organizer approves one fix for everyone. |

## Why FalkorDB

One graph holds attendees, goals, sessions, rooms, walking routes, required checks, verified results, environment facts, help reports, causes and fixes. The planner, the setup skill and the triage step all share it.

- **Plan Rescue** (`backend/app/planner.py`) walks `Attendee → WANTS → Goal ← COVERS ← Session → IN → Room`, joins `Session → REQUIRES → Check` with the attendee's `RESULT` edges, and uses `WALK` edges to decide whether they can arrive in time. Every answer is explainable as a path ("Why this?"), and rejected candidates keep their reasons.
- **Shared-cause detection** (`clusters()` in `backend/app/main.py`) groups open reports by failed check, finds the `EnvFact` every reporter `USES`, then counts how many attendees who *passed* the same check share it. "6 failed Service access, all use `/mock/us-old/v1`, 0 of 19 passers do" is a strong lead. "2 Windows users failed, but 9 Windows users passed" is labelled weak.

```
(Attendee)-[:WANTS]->(Goal)<-[:COVERS {depth}]-(Session)-[:IN]->(Room)-[:WALK {minutes, stepFree}]-(Room)
(Attendee)-[:PLANS]->(Session)-[:REQUIRES]->(Check)-[:PROVIDED_BY]->(SkillPackage)
(Attendee)-[:RESULT {status, verified, errorCode}]->(Check)    (Attendee)-[:USES]->(EnvFact)
(HelpReport)-[:FROM|FAILED|AT_STEP|IN_SESSION]->(...)   (Fix)-[:RESOLVES]->(Cause)-[:EXPLAINS]->(HelpReport)
```

## TrueForge + OpenAI: organizer copilot

Unstuck exposes its FalkorDB-backed organizer functions as an MCP server at `/mcp` (streamable HTTP, `backend/app/mcp_tools.py`):

| Tool | Kind |
|---|---|
| `list_shared_blockers`, `get_blocker_evidence`, `get_readiness_summary`, `list_sessions` | read |
| `publish_fix`, `assign_helper`, `set_session_status` | write: require approval |

In TrueForge (`npx @truefoundry/trueforge@latest`, then http://localhost:8790):

1. **Settings → Models**: add OpenAI with your key.
2. **Settings → Connectors → Add MCP Server**: URL `https://<your-app>/mcp`, header `Authorization: Bearer <MCP_TOKEN>`.
3. **Settings → Skills → Import from GitHub**: this repo, `skill/unstuck-setup`. Optionally add a Daytona sandbox so the agent can run the setup skill in a clean environment before it is published.
4. **Build Agent**: model `openai/...`, the `unstuck` MCP tools, approval required for `publish_fix`, `assign_helper` and `set_session_status`, and the instructions in `trueforge/agent-instructions.md`.

## Trust rules

- Readiness changes **only** from `check.py` results. An agent saying "done" changes nothing.
- Service access is cross-checked against the workshop API's own sign-in log (`verified`).
- Nothing is sent without the attendee's explicit consent: check ids, pass/fail, short errors, OS, Python version and endpoint path. No keys or files.
- A help report is "Verified by check" only when the check passes again. "I understand now" is recorded separately as self-reported.
- Triage only suggests organizer-approved steps and never completes the exercise.
- Shared symptoms are shown as a *possible* common cause with the evidence; a human approves every published fix.

## Run locally

```bash
cp .env.example .env            # FalkorDB Cloud creds, or keep localhost and run: docker compose up -d
pip install -r requirements.txt
cd backend && uvicorn app.main:app --port 8765 --reload
# open http://localhost:8765
```

Optional: set `OPENAI_API_KEY` (and `OPENAI_MODEL`) to let an OpenAI model refine triage summaries. Rules-based triage always runs, so the demo never depends on a model call.

## Deploy

**Render (recommended):** New → Blueprint → pick this repo. Render reads `render.yaml` and asks for the FalkorDB host, port, username and password (leave `OPENAI_API_KEY` empty if you don't have one). Every push to `main` redeploys. The free plan sleeps after 15 idle minutes, so open the site a minute before demoing.

**Railway:** New project → Deploy from GitHub repo, copy the variables from `.env`. Railway reads `railway.json`.

## Demo script (about 4 minutes)

**Before going on stage**
- Open the live site a minute early: Render's free plan sleeps after 15 idle minutes and takes ~40 s to wake.
- Start TrueForge in your own terminal (`npx @truefoundry/trueforge@latest`) and open http://localhost:8790 → **Agents** → **unstuck-organizer-copilot** → **Try**.
- Put the attendee view (phone width), the organizer Help queue and the TrueForge chat side by side.
- Press **Reset demo**. The schedule is relative to the reset time.

**Run**
1. **Join** → *Use sample attendee* → **Build my day**. The goal is evaluating AI agents.
2. **Get Ready** → *Start guided setup* → run the Claude Code command in a terminal. The skill installs packages; the checklist turns green live. **Service access** stays blocked: the handout's endpoint was retired.
3. **Request help** → **Organizer → Help queue**: "6 attendees failed Service access. All 6 use endpoint `/mock/us-old/v1`. 0 of 19 who passed use it." → *Inspect evidence*.
4. **TrueForge copilot** (OpenAI model, Unstuck MCP tools):
   - Ask *"What needs my attention right now?"* It calls `list_shared_blockers` and `get_blocker_evidence`, leads with the strong lead, calls it a *possible* common cause, and marks the Windows build-tools group as weak.
   - Ask *"Publish the suggested fix for the endpoint group."* It calls `publish_fix`, and TrueForge **pauses for approval**. Point at the Help queue: nothing has changed yet.
   - Click **Approve**. The Help queue flips to **Fix sent**, and the simulated attendees re-verify within seconds.
   - (Without TrueForge, the same step is *Review & publish fix* in the Help queue.)
5. Back in the terminal, the agent re-runs setup → all checks pass, and the report closes as **Verified by check**.
6. **Organizer → Sessions** → *Mark full* on "Agent Evals, Hands-on". (Or ask the copilot to mark it full: another approval.)
7. **Attendee → My Day** shows the alert → **View alternatives** → "Grading Agent Traces covers agent evaluation, your setup passes 4 of 5 checks, starts in 18 min nearby" → **Why this?** shows the graph path → *Switch*.
8. It needs one more package → **Get ready** → re-run the skill → Ready.

**What each sponsor did**
- **FalkorDB**: Plan Rescue and shared-cause detection are multi-hop graph queries; "Why this?" is the path.
- **TrueForge + OpenAI**: the organizer copilot reasons over the graph through MCP tools, and every write waits for a human approval. On-site triage uses an OpenAI model too.
- **Qodo**: reviewed every PR; see PRs #2 and #3 for the findings it caught and the fixes.

**Backups**
- Terminal fails: "Use simulated report (demo backup)" on Get Ready. It goes through the same endpoint and is labelled simulated.
- TrueForge fails: use *Review & publish fix* in the Help queue (same approval story, in the app).
