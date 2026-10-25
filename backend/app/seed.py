"""Seeds the fictional "Future / Forward" conference: six days, today plus the next five.

Today's block is relative to the moment of reset so the demo always starts "live": the
keynote is ending, the evals workshop starts in ~15 minutes. Days 1-5 follow a normal
conference agenda in the venue's time zone (San Francisco).
"""
import random
from datetime import date, datetime, time, timedelta, timezone

from .graph import G, bump, now_ms, run

try:
    from zoneinfo import ZoneInfo

    TZ = ZoneInfo("America/Los_Angeles")
except Exception:  # no tz database on this machine; the conference week is in PDT
    TZ = timezone(timedelta(hours=-7))

MIN = 60_000
DAYS = 6
SEED_VERSION = 2  # bump when the seed changes shape; the server reseeds older graphs on start

ROOMS = [
    {"id": "hall-a", "name": "Hall A", "floor": 1},
    {"id": "room-b", "name": "Room B", "floor": 1},
    {"id": "room-c", "name": "Room C", "floor": 1},
    {"id": "atrium", "name": "Atrium", "floor": 1},
    {"id": "lab-1", "name": "Lab 1", "floor": 2},
    {"id": "lab-2", "name": "Lab 2", "floor": 2},
]
CAPACITY = {"hall-a": 800, "room-b": 120, "room-c": 80, "atrium": 150, "lab-1": 40, "lab-2": 40}

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
    {"id": "graphs", "name": "Knowledge graphs & GraphRAG", "short": "knowledge graphs"},
    {"id": "mcp", "name": "Build agent tools with MCP", "short": "agent tools"},
    {"id": "prod", "name": "Ship agents to production", "short": "shipping agents"},
    {"id": "prompting", "name": "Prompt engineering", "short": "prompting"},
]

THEMES = ["Opening day: agents in the wild", "Agents & evaluation", "RAG & knowledge graphs",
          "Tools & MCP", "Shipping to production", "Prompting & hack day"]


def _pip(pkgs: list[str]) -> list[str]:
    return ["Activate `.venv-unstuck`", f"Run `pip install {' '.join(pkgs)}`", "Re-run the check"]


def _deps(id, name, pkgs, order):
    return {"id": id, "name": name, "kind": "deps", "packages": pkgs, "detail": ", ".join(pkgs),
            "order": order, "approvedSteps": _pip(pkgs)}


# Every check is something check.py really verifies on the attendee's laptop.
CHECKS = [
    {"id": "runtime", "name": "Required runtime", "kind": "runtime", "packages": [], "order": 1,
     "detail": "Python 3.10 or newer",
     "approvedSteps": ["Run `python --version` and confirm 3.10+", "Use the workshop venv: `python -m venv .venv-unstuck`"]},
    {"id": "git", "name": "Git", "kind": "tool", "command": "git", "packages": [], "order": 2,
     "detail": "git on your PATH",
     "approvedSteps": ["Install Git from https://git-scm.com/downloads", "Open a new terminal and run `git --version`", "Re-run the check"]},
    {"id": "node", "name": "Node.js 18+", "kind": "tool", "command": "node", "minVersion": "18", "packages": [], "order": 3,
     "detail": "node 18 or newer on your PATH",
     "approvedSteps": ["Install Node.js 20 LTS from https://nodejs.org", "Open a new terminal and run `node --version` (18 or newer)", "Re-run the check"]},
    {"id": "docker", "name": "Docker", "kind": "tool", "command": "docker", "packages": [], "order": 4,
     "detail": "Docker installed and running",
     "approvedSteps": ["Install Docker Desktop (Mac/Windows) or Docker Engine (Linux)", "Start Docker and wait until it reports it is running",
                       "Run `docker info`, then re-run the check"]},
    {"id": "deps-core", "name": "Workshop dependencies", "kind": "deps", "packages": ["pyyaml", "tabulate"], "order": 5,
     "detail": "pyyaml, tabulate",
     "approvedSteps": ["Activate `.venv-unstuck`", "Run `pip install pyyaml tabulate`", "Re-run the check"]},
    {"id": "deps-evals", "name": "Trace grader package", "kind": "deps", "packages": ["jsonschema"], "order": 6,
     "detail": "jsonschema",
     "approvedSteps": ["Activate `.venv-unstuck`", "Run `pip install jsonschema`", "Re-run the check"]},
    _deps("deps-llm", "LLM client libraries", ["openai", "tiktoken"], 7),
    _deps("deps-rag", "Retrieval toolkit", ["numpy", "scikit-learn"], 8),
    _deps("deps-graph", "FalkorDB client", ["falkordb"], 9),
    _deps("deps-mcp", "MCP Python SDK", ["mcp"], 10),
    _deps("deps-api", "Web service toolkit", ["fastapi", "uvicorn", "httpx", "pydantic"], 11),
    _deps("deps-data", "Data analysis toolkit", ["pandas", "matplotlib"], 12),
    {"id": "service", "name": "Service access", "kind": "service", "packages": [], "order": 13,
     "detail": "Workshop API key + endpoint",
     "approvedSteps": ["Open `workshop.env` and confirm WORKSHOP_ENDPOINT", "Confirm WORKSHOP_KEY is set (re-run `check.py --setup`)", "Re-run the check"]},
    {"id": "exercise", "name": "Sample exercise", "kind": "exercise", "packages": ["pyyaml"], "order": 14,
     "detail": "Runs the starter eval and compares output",
     "approvedSteps": ["Make sure Workshop dependencies pass first", "Re-run the check and paste the full output"]},
]

PACKAGES = [  # (id, name, version, status, sandbox, checks it provides)
    ("pkg-evals", "agent-evals-setup", "1.2.0", "published", "passed", ["runtime", "deps-core", "service", "exercise"]),
    ("pkg-traces", "trace-grader-addon", "0.3.0", "published", "passed", ["deps-evals"]),
    ("pkg-rag", "retrieval-lab-setup", "1.0.1", "published", "passed", ["deps-rag", "git"]),
    ("pkg-graph", "graphrag-falkordb-setup", "0.4.0", "published", "passed", ["deps-graph", "docker"]),
    ("pkg-mcp", "mcp-builder-setup", "0.6.0", "published", "passed", ["deps-mcp", "node"]),
    ("pkg-llm", "llm-clients-setup", "1.1.0", "published", "passed", ["deps-llm", "deps-data"]),
    ("pkg-prod", "ship-agents-setup", "0.9.0", "in review", "not run", ["deps-api"]),
]

EVALS_CHECKS = ["runtime", "deps-core", "service", "exercise"]

STEPS = {
    "s2": ["Clone the starter repo", "Load the eval dataset", "Call the workshop API", "Write your first grader", "Compare two agent runs"],
    "s3": ["Install the trace grader", "Capture an agent trace", "Call the workshop API", "Grade tool-call accuracy", "Report a regression"],
    "s4": ["Pick a target app", "Write five attack prompts", "Score the responses"],
    "s6": ["Chunk the sample docs", "Embed and index", "Answer three questions"],
    "s7": ["Package the agent", "Add tracing", "Call the workshop API", "Deploy behind a feature flag"],
    "d1-agent": ["Clone the starter repo", "Define two tools as JSON schemas", "Write the agent loop", "Handle a failing tool call", "Add a step limit"],
    "d1-judge": ["Clone the starter repo", "Label ten answers by hand", "Write a judge prompt", "Measure agreement with your labels", "Fix the judge's worst miss"],
    "d1-traces": ["Load the sample traces", "Find the slowest tool calls", "Plot cost per task", "Spot the failure pattern"],
    "d2-hybrid": ["Clone the starter repo", "Build a BM25 index", "Add TF-IDF vectors", "Blend the two scores", "Compare recall on ten questions"],
    "d2-graphrag": ["Start FalkorDB in Docker", "Load the sample documents", "Extract entities into the graph", "Answer a multi-hop question", "Compare with vector-only RAG"],
    "d2-rageval": ["Load your pipeline's answers", "Score retrieval recall", "Score answer faithfulness", "Find the worst query"],
    "d2-cypher": ["Start FalkorDB in Docker", "Write three Cypher queries", "Wrap them as agent tools", "Let the agent pick the query"],
    "d3-mcp-py": ["Install the MCP SDK", "Create a server with one tool", "Add a resource", "Connect it to your agent client"],
    "d3-mcp-ts": ["Scaffold the project with npm", "Define a tool with a schema", "Run the server over stdio", "Call it from an MCP client"],
    "d3-approvals": ["Clone the starter repo", "Mark write tools as needing approval", "Build the approval endpoint", "Test approve and deny paths"],
    "d3-evals-encore": ["Clone the starter repo", "Load the eval dataset", "Call the workshop API", "Write your first grader", "Compare two agent runs"],
    "d4-fastapi": ["Clone the starter repo", "Wrap the agent in a FastAPI route", "Stream responses", "Add a health check", "Load-test with httpx"],
    "d4-docker": ["Write a Dockerfile", "Build the image", "Run it locally with env vars", "Push and deploy"],
    "d4-structured": ["Define a Pydantic model", "Ask the model for JSON that fits it", "Validate and retry on errors", "Use it in a pipeline"],
    "d4-redteam": ["Pick a target app", "Write five attack prompts", "Score the responses", "Patch the weakest spot"],
    "d5-prompts": ["Write a baseline prompt", "Store prompts as versioned files", "Run them on a test set", "Compare two versions with a table"],
    "d5-hack": ["Form a team", "Pick a problem", "Build a working slice", "Prepare a three-minute demo"],
    "d5-golden": ["Build a golden dataset", "Write graders for it", "Run two prompt versions", "Decide which one ships"],
}


def _today_block(t0: int):
    """Day 0: relative to reset, so the stage demo always starts mid-morning-ish."""
    def s(id, title, speaker, room, start, dur, fmt, level, covers, requires, outcomes, summary, capacity=60, taken=20, **extra):
        return {"id": id, "title": title, "speaker": speaker, "room": room, "day": 0,
                "start": t0 + start * MIN, "end": t0 + (start + dur) * MIN,
                "format": fmt, "level": level, "covers": covers, "requires": requires,
                "outcomes": outcomes, "summary": summary, "capacity": capacity, "taken": taken, **extra}

    return [
        s("s1", "Opening keynote: Agents in the Wild", "Dana Okafor", "hall-a", -40, 45, "talk", "beginner",
          {"evals": 1, "prod": 1}, [], ["Where agents fail in production today", "What changed this year"],
          "The state of agent deployments, failure stories, and what the week covers.", 800, 640, keynote=True),
        s("s2", "Agent Evals, Hands-on", "Priya Natarajan", "lab-1", 15, 60, "workshop", "intermediate",
          {"evals": 3}, EVALS_CHECKS,
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
          {"prod": 3, "evals": 1}, EVALS_CHECKS,
          ["Package and trace an agent", "Roll out behind a flag", "Monitor regressions"],
          "Take a working agent and make it safe to ship.", 40, 22),
        s("s9", "Agent Eval Office Hours", "Priya Natarajan", "atrium", 200, 60, "office hours", "intermediate",
          {"evals": 2}, [], ["Bring your eval questions", "Review your grader with an expert"],
          "Drop-in help on evaluation design with the Agent Evals instructors.", 30, 6),
    ]


# Days 1-5: (id, day, start, minutes, room, title, speaker, format, level, covers, requires, outcomes, summary)
AGENDA = [
    # ---- Day 1: agents & evaluation
    ("d1-key", 1, "09:00", 45, "hall-a", "Keynote: From Demo to Dependable Agents", "Amara Osei", "talk", "beginner",
     {"prod": 2, "evals": 1}, [], ["What separates a demo from a product", "The reliability checklist teams actually use"],
     "Why most agent demos never ship, and the habits of teams whose agents do."),
    ("d1-agent", 1, "10:00", 90, "lab-1", "Build a Tool-Calling Agent from Scratch", "Tomás Rivera", "workshop", "intermediate",
     {"prod": 2, "mcp": 1}, ["runtime", "git", "deps-llm"],
     ["Write an agent loop without a framework", "Define tools with JSON schemas", "Handle tool errors and step limits"],
     "Build a small agent that calls real tools, then make it fail gracefully."),
    ("d1-judge", 1, "10:00", 90, "lab-2", "LLM-as-Judge: Graders You Can Trust", "Priya Natarajan", "workshop", "intermediate",
     {"evals": 3}, EVALS_CHECKS + ["deps-evals"],
     ["Write a judge prompt with a rubric", "Measure agreement with human labels", "Catch judge bias"],
     "A judge model is only useful if it agrees with people. Build one and prove it does."),
    ("d1-tests", 1, "10:00", 40, "room-b", "Why Your Agent Passes Tests and Fails Users", "Nadia Rahman", "talk", "beginner",
     {"evals": 2}, [], ["The gap between test sets and real traffic", "Sampling production conversations for evals"],
     "Stories from teams whose dashboards were green while users churned."),
    ("d1-observe", 1, "11:00", 40, "room-c", "Observability for LLM Apps: Traces, Spans and Cost", "Ethan Park", "talk", "intermediate",
     {"prod": 2, "evals": 1}, [], ["What to log for every model call", "Tracing multi-step agents", "Cost per task, not per token"],
     "Instrument an agent so you can answer 'what happened?' in under a minute."),
    ("d1-lunch", 1, "12:00", 60, "atrium", "Lunch & Birds-of-a-Feather Tables", "Conference team", "networking", "beginner",
     {}, [], ["Topic tables for evals, RAG, MCP and shipping"], "Grab lunch and sit at the table for the topic you care about."),
    ("d1-traces", 1, "13:00", 90, "lab-1", "Analyze Agent Traces with pandas", "Zara Ali", "workshop", "beginner",
     {"evals": 2, "prod": 1}, ["runtime", "git", "deps-data"],
     ["Load agent traces into a DataFrame", "Find slow and expensive steps", "Plot failure patterns"],
     "Turn a pile of JSON traces into answers about speed, cost and failures."),
    ("d1-panel", 1, "13:30", 45, "hall-a", "Panel: Who Grades the Graders?", "Hugo Laurent (moderator)", "panel", "intermediate",
     {"evals": 2}, [], ["When to trust automated evals", "How teams combine human and model review"],
     "Eval leads from four companies argue about judges, labels and leaderboards."),
    ("d1-budget", 1, "14:30", 40, "room-b", "Cost and Latency Budgets for Agents", "Leila Haddad", "talk", "intermediate",
     {"prod": 2}, [], ["Setting a budget per task", "Where agents waste tokens", "Caching and early exits"],
     "Agents are loops, and loops get expensive. Keep them inside a budget."),
    ("d1-clinic", 1, "15:30", 60, "atrium", "Evals Clinic: Bring Your Failing Test", "Priya Natarajan", "office hours", "intermediate",
     {"evals": 2}, [], ["Get feedback on your eval design", "Debug a flaky grader with an expert"],
     "Drop in with a real eval problem and leave with a plan."),
    ("d1-lightning", 1, "16:30", 45, "hall-a", "Lightning Talks: Agent Failure Stories", "Community speakers", "talk", "beginner",
     {"evals": 1, "prod": 1}, [], ["Nine five-minute stories of agents gone wrong", "What each team changed afterwards"],
     "Short, funny and painful lessons from production."),

    # ---- Day 2: RAG & knowledge graphs
    ("d2-key", 2, "09:00", 45, "hall-a", "Keynote: Retrieval Is the Product", "Owen Murphy", "talk", "beginner",
     {"rag": 2, "graphs": 1}, [], ["Why answer quality is mostly retrieval quality", "Where RAG is heading"],
     "Most 'model problems' in RAG apps are retrieval problems in disguise."),
    ("d2-hybrid", 2, "10:00", 90, "lab-1", "Hybrid Search from Scratch: BM25 + Vectors", "Lena Fischer", "workshop", "intermediate",
     {"rag": 3}, ["runtime", "git", "deps-rag"],
     ["Build keyword and vector search", "Blend scores with reciprocal rank fusion", "Measure recall on real questions"],
     "Build hybrid search with numpy and scikit-learn, and see why it beats either half alone."),
    ("d2-graphrag", 2, "10:00", 90, "lab-2", "GraphRAG with FalkorDB", "Sakura Ito", "workshop", "intermediate",
     {"graphs": 3, "rag": 2}, ["runtime", "git", "docker", "deps-graph"],
     ["Run FalkorDB locally in Docker", "Turn documents into a knowledge graph", "Answer multi-hop questions with Cypher"],
     "Combine a knowledge graph with retrieval to answer the questions vector search gets wrong."),
    ("d2-chunking", 2, "10:00", 40, "room-b", "Chunking Strategies That Actually Matter", "Daniel Asante", "talk", "beginner",
     {"rag": 2}, [], ["Fixed, semantic and structural chunking compared", "How chunk size changes answers"],
     "A measured look at chunking, with numbers instead of opinions."),
    ("d2-kg101", 2, "11:00", 40, "room-c", "Knowledge Graphs 101 for LLM Engineers", "Riya Kapoor", "talk", "beginner",
     {"graphs": 2}, [], ["Nodes, edges and properties in five minutes", "When a graph beats a table or a vector index"],
     "Everything you need to know about graphs before tomorrow's hands-on sessions."),
    ("d2-lunch", 2, "12:00", 60, "atrium", "Lunch & Hallway Track", "Conference team", "networking", "beginner",
     {}, [], ["Meet the speakers from the morning sessions"], "Lunch, coffee and the conversations that don't fit in a talk."),
    ("d2-rageval", 2, "13:00", 90, "lab-1", "Evaluate Your RAG Pipeline", "Felix Wagner", "workshop", "intermediate",
     {"rag": 2, "evals": 2}, ["runtime", "deps-rag", "deps-evals"],
     ["Score retrieval recall and precision", "Check answers are faithful to sources", "Build a regression set"],
     "Stop guessing whether a change helped. Measure retrieval and answers separately."),
    ("d2-cypher", 2, "13:00", 90, "lab-2", "Cypher for Agents: Graph Queries as Tools", "Sakura Ito", "workshop", "advanced",
     {"graphs": 3, "mcp": 1}, ["runtime", "docker", "deps-graph"],
     ["Write multi-hop Cypher queries", "Expose queries as agent tools", "Let an agent choose the right query"],
     "Give an agent safe, structured access to a graph database."),
    ("d2-rerank", 2, "14:45", 40, "room-b", "Reranking: The Cheapest Accuracy Win", "Carmen Ruiz", "talk", "intermediate",
     {"rag": 2}, [], ["How cross-encoder rerankers work", "When reranking is worth the latency"],
     "One extra step that often fixes more than a bigger model."),
    ("d2-oh", 2, "15:30", 60, "atrium", "Graph & Retrieval Office Hours", "Lena Fischer & Sakura Ito", "office hours", "intermediate",
     {"graphs": 2, "rag": 2}, [], ["Review your retrieval setup", "Get help modelling your data as a graph"],
     "Bring your RAG or graph questions to the day's instructors."),
    ("d2-lightning", 2, "16:30", 45, "hall-a", "Lightning Talks: RAG in the Real World", "Community speakers", "talk", "beginner",
     {"rag": 1, "graphs": 1}, [], ["Eight short case studies from production RAG apps"], "What worked, what didn't, and what it cost."),

    # ---- Day 3: tools & MCP
    ("d3-key", 3, "09:00", 45, "hall-a", "Keynote: Tools Are the New APIs", "Yusuf Demir", "talk", "beginner",
     {"mcp": 2, "prod": 1}, [], ["How the Model Context Protocol changes integrations", "Designing products agents can use"],
     "If agents are your new users, your tools are your new API."),
    ("d3-mcp-py", 3, "10:00", 90, "lab-1", "Build Your First MCP Server in Python", "Grace Liu", "workshop", "beginner",
     {"mcp": 3}, ["runtime", "git", "deps-mcp"],
     ["Create an MCP server with the Python SDK", "Add tools and resources", "Connect it to an agent client"],
     "From zero to a working MCP server your coding assistant can call."),
    ("d3-mcp-ts", 3, "10:00", 90, "lab-2", "Build an MCP Server in TypeScript", "Mateo Silva", "workshop", "intermediate",
     {"mcp": 3}, ["git", "node"],
     ["Scaffold an MCP server with npm", "Validate tool inputs with schemas", "Run it over stdio and HTTP"],
     "The same ideas as the Python workshop, for teams living in Node."),
    ("d3-schemas", 3, "10:00", 40, "room-b", "Designing Tool Schemas Models Understand", "Ingrid Solberg", "talk", "intermediate",
     {"mcp": 2, "prompting": 1}, [], ["Naming and describing tools well", "Why fewer, clearer parameters win"],
     "Small changes to a tool's description that change how often the model uses it right."),
    ("d3-security", 3, "11:00", 40, "room-c", "Securing Agent Tools: Auth, Scopes and Approvals", "Kwame Boateng", "talk", "advanced",
     {"mcp": 2, "prod": 2}, [], ["Least-privilege tokens for agents", "Human approval for risky actions", "Prompt injection through tools"],
     "What can go wrong when an agent holds the keys, and how to limit it."),
    ("d3-lunch", 3, "12:00", 60, "atrium", "Lunch & Tool Builders Meetup", "Conference team", "networking", "beginner",
     {}, [], ["Show the MCP server you built this morning"], "Lunch with demo tables for anyone who built something."),
    ("d3-approvals", 3, "13:00", 90, "lab-1", "Human-in-the-Loop Approvals for Agents", "Kwame Boateng", "workshop", "intermediate",
     {"prod": 2, "mcp": 2}, ["runtime", "deps-mcp", "deps-api"],
     ["Mark write tools as needing approval", "Build an approve/deny flow", "Log every decision"],
     "Let agents propose changes and keep a person in charge of the ones that matter."),
    ("d3-evals-encore", 3, "13:00", 60, "lab-2", "Agent Evals, Hands-on (encore)", "Priya Natarajan", "workshop", "intermediate",
     {"evals": 3}, EVALS_CHECKS,
     ["Build an eval set from real traces", "Write an LLM-as-judge grader", "Compare two agent versions"],
     "A repeat of opening day's sold-out workshop for everyone who couldn't get a seat."),
    ("d3-panel", 3, "14:45", 45, "hall-a", "Panel: Will MCP Be the USB-C of AI?", "Anika Sharma (moderator)", "panel", "beginner",
     {"mcp": 2}, [], ["Where standard tool protocols help and hurt", "What's missing today"],
     "Platform, startup and open-source maintainers debate the future of agent tools."),
    ("d3-oh", 3, "15:45", 60, "atrium", "MCP Office Hours", "Grace Liu & Mateo Silva", "office hours", "intermediate",
     {"mcp": 2}, [], ["Debug your MCP server with the instructors"], "Bring your server, your errors and your questions."),
    ("d3-night", 3, "18:00", 120, "atrium", "Builders' Night: Demos & Drinks", "Conference team", "networking", "beginner",
     {}, [], ["Open demo stage", "Meet other attendees"], "An evening of demos, food and conversation."),

    # ---- Day 4: shipping to production
    ("d4-key", 4, "09:00", 45, "hall-a", "Keynote: The Boring Parts of AI That Ship", "Lucas Moreau", "talk", "beginner",
     {"prod": 2}, [], ["Deploys, rollbacks and on-call for AI features", "Why boring is a compliment"],
     "The unglamorous engineering behind AI features people rely on."),
    ("d4-fastapi", 4, "10:00", 90, "lab-1", "Serve an Agent Behind a FastAPI Endpoint", "Hannah Kim", "workshop", "intermediate",
     {"prod": 3}, ["runtime", "git", "deps-api", "deps-llm"],
     ["Wrap an agent in a web API", "Stream responses to the client", "Add health checks and timeouts"],
     "Turn a notebook agent into a service other people can call."),
    ("d4-docker", 4, "10:00", 90, "lab-2", "Containerize and Deploy Your Agent", "Arash Tehrani", "workshop", "intermediate",
     {"prod": 3}, ["git", "docker"],
     ["Write a small, secure Dockerfile", "Pass secrets safely", "Deploy and roll back"],
     "Package an agent so it runs the same on your laptop and in the cloud."),
    ("d4-guardrails", 4, "10:00", 40, "room-b", "Guardrails Without the Guesswork", "Bianca Rossi", "talk", "intermediate",
     {"prod": 2, "evals": 1}, [], ["Input and output checks that matter", "Measuring guardrail false positives"],
     "Guardrails are features too. Test them like features."),
    ("d4-caching", 4, "11:00", 40, "room-c", "Prompt Caching and Other Cost Cuts", "Ethan Park", "talk", "intermediate",
     {"prod": 2, "prompting": 1}, [], ["Prompt caching explained", "Batching and smaller models", "Measuring savings"],
     "Cut your model bill without making answers worse."),
    ("d4-lunch", 4, "12:00", 60, "atrium", "Lunch & Hiring Tables", "Conference team", "networking", "beginner",
     {}, [], ["Meet teams hiring AI engineers"], "Lunch with teams who are building and hiring."),
    ("d4-structured", 4, "13:00", 90, "lab-1", "Structured Outputs with Pydantic", "Hannah Kim", "workshop", "beginner",
     {"prompting": 2, "prod": 2}, ["runtime", "deps-api", "deps-llm"],
     ["Define output models with Pydantic", "Validate and retry on bad JSON", "Use typed outputs in a pipeline"],
     "Get reliable, typed data out of a model instead of parsing free text."),
    ("d4-redteam", 4, "13:00", 90, "lab-2", "Red-teaming LLM Apps (encore)", "Ines Duarte", "workshop", "advanced",
     {"evals": 2, "prod": 1}, ["runtime", "deps-core"],
     ["Design adversarial test cases", "Score jailbreak resistance", "Patch the weakest spot"],
     "Opening day's red-teaming workshop, extended with a patching exercise."),
    ("d4-incident", 4, "14:45", 40, "room-b", "Incident Review: When the Agent Went Rogue", "Lucas Moreau", "talk", "beginner",
     {"prod": 2}, [], ["A real incident timeline, step by step", "The fixes that stuck"],
     "A blameless walkthrough of an agent incident and what changed after it."),
    ("d4-oh", 4, "15:30", 60, "atrium", "Production Office Hours", "Hannah Kim & Arash Tehrani", "office hours", "intermediate",
     {"prod": 2}, [], ["Review your deployment plan", "Ask about scaling and monitoring"], "Bring your architecture diagram."),
    ("d4-lightning", 4, "16:30", 45, "hall-a", "Lightning Talks: Shipped It", "Community speakers", "talk", "beginner",
     {"prod": 1}, [], ["Short launch stories from attendees"], "Five minutes each on something that actually shipped."),

    # ---- Day 5: prompting & hack day
    ("d5-key", 5, "09:00", 45, "hall-a", "Keynote: Prompting Is Programming", "Riya Kapoor", "talk", "beginner",
     {"prompting": 2}, [], ["Treating prompts as code", "Versioning, testing and reviewing prompts"],
     "Prompts deserve the same care as the rest of your codebase."),
    ("d5-prompts", 5, "10:00", 90, "lab-1", "Prompt Engineering Lab: From Vibes to Versions", "Ingrid Solberg", "workshop", "beginner",
     {"prompting": 3}, ["runtime", "deps-core", "deps-llm"],
     ["Write and version prompts as files", "Test prompts on a fixed set", "Compare versions side by side"],
     "Replace prompt guesswork with a small, repeatable workflow."),
    ("d5-context", 5, "10:00", 40, "room-b", "Context Engineering for Long-Running Agents", "Yusuf Demir", "talk", "advanced",
     {"prompting": 3, "prod": 1}, [], ["What to keep, summarize or drop", "Memory patterns that scale"],
     "Agents that run for hours need a plan for what they remember."),
    ("d5-hack", 5, "10:00", 300, "atrium", "Hack Sprint: Build Something in Five Hours", "Conference team", "hackathon", "beginner",
     {"prod": 2, "mcp": 1, "rag": 1}, ["runtime", "git"],
     ["Build a working project with a team", "Demo it on the main stage"],
     "Form a team, use anything you learned this week, and demo at 3:30."),
    ("d5-open", 5, "11:00", 40, "room-c", "Small Models, Big Wins: When to Go Open", "Daniel Asante", "talk", "intermediate",
     {"prod": 2, "prompting": 1}, [], ["When a small open model is enough", "Fine-tuning versus prompting"],
     "How to decide whether you need the biggest model at all."),
    ("d5-lunch", 5, "12:00", 60, "room-b", "Lunch & Team Matching", "Conference team", "networking", "beginner",
     {}, [], ["Find a hack sprint team"], "Still looking for a team? Start here."),
    ("d5-golden", 5, "13:00", 90, "lab-1", "Prompt Evals with Golden Datasets", "Felix Wagner", "workshop", "intermediate",
     {"prompting": 2, "evals": 2}, ["runtime", "deps-core", "deps-evals"],
     ["Build a golden dataset", "Grade prompt versions automatically", "Decide what ships"],
     "The evaluation habit that makes prompt changes safe."),
    ("d5-demos", 5, "15:30", 90, "hall-a", "Hack Sprint Demos & Awards", "Conference team", "talk", "beginner",
     {"prod": 1}, [], ["Three-minute demos from every team"], "See what everyone built and cheer them on."),
    ("d5-close", 5, "17:00", 30, "hall-a", "Closing Keynote: What We Learned This Week", "Dana Okafor", "talk", "beginner",
     {"evals": 1, "prod": 1}, [], ["The week's big ideas in thirty minutes"], "A look back at the week and what to try next."),
]
KEYNOTES = {"d1-key", "d2-key", "d3-key", "d4-key", "d5-key"}
ENCORES = {"d3-evals-encore": "s2", "d4-redteam": "s4"}
NEARLY_FULL = {"d2-graphrag": 37, "d3-mcp-py": 39, "d3-evals-encore": 34}


def local_date(ms: int) -> date:
    return datetime.fromtimestamp(ms / 1000, TZ).date()


def at(day0: date, day: int, hhmm: str) -> int:
    """Epoch ms for HH:MM venue time on conference day `day`. Raises ValueError for a bad time."""
    h, m = (int(x) for x in hhmm.split(":"))
    return int(datetime.combine(day0 + timedelta(days=day), time(h, m), tzinfo=TZ).timestamp() * 1000)


def fmt_local(ms: int) -> str:
    """'Tue Oct 27, 10:00 AM' in venue time, for agents and logs."""
    d = datetime.fromtimestamp(ms / 1000, TZ)
    return f"{d:%a %b} {d.day}, {d.hour % 12 or 12}:{d:%M} {'AM' if d.hour < 12 else 'PM'}"


def _agenda(day0: date, rnd: random.Random) -> list[dict]:
    out = []
    for (id, day, hhmm, dur, room, title, speaker, fmt, level, covers, requires, outcomes, summary) in AGENDA:
        start = at(day0, day, hhmm)
        cap = CAPACITY[room]
        s = {"id": id, "title": title, "speaker": speaker, "room": room, "day": day, "start": start,
             "end": start + dur * MIN, "format": fmt, "level": level, "covers": covers, "requires": requires,
             "outcomes": outcomes, "summary": summary, "capacity": cap,
             "taken": NEARLY_FULL.get(id) or int(cap * rnd.uniform(0.15, 0.7))}
        if id in KEYNOTES:
            s["keynote"] = True
        if id in ENCORES:
            s["encoreOf"] = ENCORES[id]
        out.append(s)
    return out


def _materials(s: dict) -> list[str]:
    if s["format"] in ("workshop", "hackathon"):
        return [f"Slides: {s['title']}", f"Starter repo (github.com/future-forward/{s['id']})"]
    if s["format"] == "networking":
        return []
    return [f"Slides: {s['title']}"]


FIRST = ["Ava", "Ben", "Chen", "Diego", "Elif", "Farah", "Gus", "Hana", "Ivan", "Jade", "Kai", "Luis",
         "Mina", "Noor", "Omar", "Pia", "Quinn", "Ravi", "Sofia", "Tariq", "Uma", "Vik", "Wen", "Yara"]


def reset() -> int:
    t0 = (now_ms() // MIN) * MIN
    rnd = random.Random(7)
    day0 = local_date(t0)
    days = [day0 + timedelta(days=i) for i in range(DAYS)]
    try:
        G.delete()
    except Exception:
        pass

    today = _today_block(t0)
    for s in today:  # a late-evening reset can push part of the live block past midnight
        s["day"] = min(max((local_date(s["start"]) - day0).days, 0), DAYS - 1)
    sessions = today + _agenda(day0, random.Random(3))
    last = days[-1]
    dates = (f"{day0:%b} {day0.day}–{last.day}, {last.year}" if day0.month == last.month
             else f"{day0:%b} {day0.day} – {last:%b} {last.day}, {last.year}")
    run("CREATE (:Conference {id:'ff', name:'Future / Forward', city:'San Francisco', dates:$dates, "
        "venue:'Moscone West', endpoint:'/mock/us-old/v1', t0:$t0, day0:$day0, dayKeys:$keys, days:$labels, "
        "themes:$themes, tz:'America/Los_Angeles', seedVersion:$sv, ends:$ends})",
        {"t0": t0, "dates": dates, "day0": day0.isoformat(), "keys": [d.isoformat() for d in days],
         "labels": [f"{d:%a, %b} {d.day}" for d in days], "themes": THEMES, "sv": SEED_VERSION,
         "ends": max(s["end"] for s in sessions)})
    run("UNWIND $rows AS r CREATE (x:Room) SET x = r", {"rows": ROOMS})
    run("UNWIND $rows AS r MATCH (a:Room {id:r[0]}), (b:Room {id:r[1]}) "
        "CREATE (a)-[:WALK {minutes:r[2], stepFree:r[3]}]->(b)", {"rows": [list(w) for w in WALKS]})
    run("UNWIND $rows AS r CREATE (x:Goal) SET x = r", {"rows": GOALS})
    run("UNWIND $rows AS r CREATE (x:Check) SET x = r", {"rows": CHECKS})
    pkgs = [{"id": p[0], "name": p[1], "version": p[2], "status": p[3], "sandbox": p[4]} for p in PACKAGES]
    run("UNWIND $rows AS r CREATE (p:SkillPackage) SET p = r, p.reviewedAt = CASE WHEN r.status = 'published' THEN $t END",
        {"rows": pkgs, "t": t0 - 90 * MIN})
    run("UNWIND $rows AS r MATCH (c:Check {id:r[1]}), (p:SkillPackage {id:r[0]}) CREATE (c)-[:PROVIDED_BY]->(p)",
        {"rows": [[p[0], c] for p in PACKAGES for c in p[5]]})

    props = []
    for s in sessions:
        p = {k: v for k, v in s.items() if k not in ("covers", "requires", "room")}
        p.update(status="open", statusAt=t0 - 30 * MIN, statusSource="organizer", materials=_materials(s))
        props.append({"room": s["room"], "p": p})
    run("UNWIND $rows AS r MATCH (room:Room {id:r.room}) CREATE (s:Session)-[:IN]->(room) SET s = r.p", {"rows": props})
    run("UNWIND $rows AS r MATCH (s:Session {id:r[0]}), (g:Goal {id:r[1]}) CREATE (s)-[:COVERS {depth:r[2]}]->(g)",
        {"rows": [[s["id"], g, d] for s in sessions for g, d in s["covers"].items()]})
    run("UNWIND $rows AS r MATCH (s:Session {id:r[0]}), (k:Check {id:r[1]}) CREATE (s)-[:REQUIRES]->(k)",
        {"rows": [[s["id"], c] for s in sessions for c in s["requires"]]})
    steps = [{"sid": sid, "st": {"id": f"{sid}-st{i + 1}", "n": i + 1, "title": t}}
             for sid, titles in STEPS.items() for i, t in enumerate(titles)]
    run("UNWIND $rows AS r MATCH (s:Session {id:r.sid}) CREATE (s)-[:HAS_STEP]->(x:Step) SET x = r.st", {"rows": steps})

    # The sample attendee: starts un-onboarded so the demo shows the join flow.
    run("CREATE (:Attendee {id:'a-demo', name:'Jordan Lee', level:'intermediate', token:'demo-7Q4K', sample:true, "
        "onboarded:false, stepFree:false, timeNote:''})")

    _seed_crowd(rnd, t0, sessions)
    bump()
    return t0


def _seed_crowd(rnd: random.Random, t0: int, sessions: list[dict]) -> None:
    """24 simulated attendees with check results. Five are stuck on service access and
    all of them still use the retired us-old endpoint from the original handout."""
    old_ep, new_ep = "/mock/us-old/v1", "/mock/us-west/v1"
    stuck_service = set(range(5))
    stuck_deps_win = {5, 6, 7}
    attendees, results, uses, plans, reports = [], [], [], [], []
    week = random.Random(11)  # separate stream so today's demo crowd stays exactly as before
    by_day = {d: [s for s in sessions if s["day"] == d and s["format"] != "networking"] for d in range(1, DAYS)}
    req = {s["id"]: s["requires"] for s in sessions}
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
                            "error": f"HTTPError: 410 Gone for url: https://api.workshop.dev{old_ep}/ping (endpoint retired)",
                            "errorCode": "endpoint_retired", "at": t0 - rnd.randint(2, 25) * MIN})
        if i in (5, 6):
            reports.append({"id": f"r-{aid}", "aid": aid, "session": "s2", "step": "s2-st1", "check": "deps-core",
                            "error": "error: Microsoft Visual C++ 14.0 or greater is required (building wheel for pyyaml)",
                            "errorCode": "build_tools_missing", "at": t0 - rnd.randint(5, 40) * MIN})

        # The rest of the week: two non-clashing sessions a day, plus results for the extra checks they need.
        later = set()
        for d in range(1, DAYS):
            picked = []
            for s in week.sample(by_day[d], len(by_day[d])):
                if len(picked) == 2:
                    break
                if all(p["end"] <= s["start"] or s["end"] <= p["start"] for p in picked):
                    picked.append(s)
            plans += [[aid, s["id"]] for s in picked]
            later.update(c for s in picked for c in req[s["id"]])
        for chk in sorted(later - {"runtime", "deps-core", "service", "exercise"}):
            status, code, detail = "pass", "", ""
            if chk == "docker" and os_name == "windows" and i in (12, 15, 18, 21):
                status, code, detail = "fail", "docker_not_running", "Docker is installed but not running (Cannot connect to the Docker daemon)"
            if chk == "node" and i in (4, 20):
                status, code, detail = "fail", "tool_too_old", "Node.js v16.20.2 found; 18+ required"
            if chk == "deps-rag" and i in (8, 16):
                status, code, detail = "fail", "module_missing", "missing: scikit-learn"
            results.append([aid, chk, status, code, detail, t0 - week.randint(60, 2000) * MIN])

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
