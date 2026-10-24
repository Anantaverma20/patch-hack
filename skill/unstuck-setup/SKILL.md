---
name: unstuck-setup
description: Prepare and verify this laptop for the attendee's Future / Forward workshops. Use when the attendee asks to get ready for a workshop, finish setup, or re-run Unstuck checks.
---

# Unstuck workshop setup

Organizer-approved setup package (agent-evals-setup 1.2.0). You prepare the environment;
`check.py` decides whether it is ready. **Never tell the attendee they are ready unless
`check.py` printed "Your environment passed this workshop's checks."**

The attendee gives you two values from their Get Ready page: `SERVER` and `TOKEN`.

## Steps

1. Work in a folder named `unstuck-workshop` (create it if needed) and put `check.py` there:
   `curl -fsSL SERVER/skill/check.py -o check.py`
2. Create and use a virtual environment:
   - `python -m venv .venv-unstuck`
   - activate it (`.venv-unstuck\Scripts\activate` on Windows, `source .venv-unstuck/bin/activate` elsewhere)
3. Sign in to the workshop service: `python check.py --server SERVER --token TOKEN --setup`
4. Install packages: `pip install $(python check.py --server SERVER --token TOKEN --packages)`
   (on Windows PowerShell, run `--packages` first and pass its output to `pip install`).
5. Run the checks: `python check.py --server SERVER --token TOKEN`
6. If a check fails, fix only setup problems (runtime, packages, sign-in, endpoint), using
   the error detail. Do not change or complete the workshop exercise itself. Re-run step 5.
   Stop after two attempts at the same failure and tell the attendee to press **Request help**
   on their Get Ready page, quoting the failing line.
7. Show the attendee the results table and ask: *"Send these results to Unstuck? Only check
   ids, pass/fail, short errors, OS, Python version and endpoint path are sent."*
8. Only if they agree: `python check.py --server SERVER --token TOKEN --send --yes`

## Rules

- Do not send anything without the attendee's explicit yes.
- Do not read or send other files, environment variables or keys.
- Do not edit `check.py`.
