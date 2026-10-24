import { useEffect, useRef, useState } from "../vendor/preact-htm.js";
import { Icon, api, html } from "./core.js";

// Minimal, safe formatting for agent replies: escape first, then **bold**, `code`, bullets.
function fmt(text) {
  const esc = text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  return esc
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>")
    .replace(/^\s*[-•] (.*)$/gm, "<span class='cp-li'>$1</span>")
    .replace(/\n/g, "<br/>");
}

const SUGGESTIONS = ["What needs my attention right now?", "Publish the suggested fix for the strongest group.", "Which sessions have the lowest setup readiness?"];

export function Copilot({ visible = true }) {
  const [enabled, setEnabled] = useState(false);
  const [open, setOpen] = useState(false);
  const [msgs, setMsgs] = useState([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [conv, setConv] = useState({});
  const end = useRef();
  useEffect(() => { api("/api/copilot/status").then((s) => setEnabled(s.enabled)).catch(() => {}); }, []);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [msgs, busy]);
  if (!enabled || !visible) return null;  // stays mounted, so chat + pending approvals survive role switches

  const absorb = (r) => {
    setConv({ session_id: r.session_id, previous_turn_id: r.turn_id });
    const add = [];
    if (r.content) add.push({ role: "agent", text: r.content });
    for (const a of r.approvals || []) add.push({ role: "approval", ...a, turn_id: r.turn_id, session_id: r.session_id });
    if (r.status === "error") add.push({ role: "agent", text: "The copilot hit an error. Try again." });
    setMsgs((m) => [...m, ...add]);
  };
  const send = async (t) => {
    const q = (t ?? text).trim();
    if (!q || busy) return;
    setText(""); setMsgs((m) => [...m, { role: "user", text: q }]); setBusy(true);
    try { absorb(await api("/api/copilot/message", { text: q, ...conv })); }
    catch (e) { setMsgs((m) => [...m, { role: "agent", text: "Couldn't reach the copilot. Is TrueForge running?" }]); }
    setBusy(false);
  };
  const decide = async (a, allow) => {
    setMsgs((m) => m.map((x) => (x === a ? { ...x, decided: allow ? "approved" : "denied" } : x))); setBusy(true);
    try { absorb(await api("/api/copilot/approve", { session_id: a.session_id, previous_turn_id: a.turn_id, tool_call_id: a.tool_call_id, thread_id: a.thread_id, allow })); }
    catch (e) {
      setMsgs((m) => [...m.map((x) => (x.tool_call_id === a.tool_call_id ? { ...x, decided: undefined } : x)),
        { role: "agent", text: "Approval didn't go through. Try again." }]);
    }
    setBusy(false);
  };

  return html`
    ${!open && html`<button class="cp-fab" onClick=${() => setOpen(true)} aria-label="Open organizer copilot">
      <${Icon} n="sparkle" s=${20} /> Copilot</button>`}
    ${open && html`<div class="cp-panel" role="dialog" aria-label="Organizer copilot">
      <div class="cp-head">
        <div><b>Organizer copilot</b><div class="small muted">TrueForge · OpenAI · approvals on every change</div></div>
        <button class="btn ghost sm" onClick=${() => setOpen(false)} aria-label="Close"><${Icon} n="x" s=${18} /></button>
      </div>
      <div class="cp-body">
        ${msgs.length === 0 && html`<div class="cp-empty">
          <p class="small muted" style="margin:0 0 10px">Ask about shared blockers, readiness or sessions. Anything that changes what attendees see waits for your approval.</p>
          ${SUGGESTIONS.map((s) => html`<button class="chip" style="margin:0 6px 6px 0" onClick=${() => send(s)}>${s}</button>`)}
        </div>`}
        ${msgs.map((m, i) => m.role === "approval" ? html`<div class="cp-approval fade" key=${i}>
            <div class="small" style="margin-bottom:6px"><${Icon} n="shield" s=${14} /> <b>Approval required</b>: <code>${m.tool}</code></div>
            <pre class="err" style="white-space:pre-wrap;margin:0 0 10px">${JSON.stringify(m.input, null, 1)}</pre>
            ${m.decided ? html`<span class=${`pill ${m.decided === "approved" ? "ready" : ""}`}>${m.decided === "approved" ? "Approved" : "Denied"}</span>`
              : html`<div class="row"><button class="btn sm primary" disabled=${busy} onClick=${() => decide(m, true)}>Approve</button>
                  <button class="btn sm ghost" disabled=${busy} onClick=${() => decide(m, false)}>Deny</button></div>`}
          </div>`
          : html`<div class=${`cp-msg ${m.role} fade`} key=${i} dangerouslySetInnerHTML=${{ __html: fmt(m.text) }}></div>`)}
        ${busy && html`<div class="cp-msg agent"><span class="spinner"></span> <span class="small muted">Working through the graph…</span></div>`}
        <div ref=${end}></div>
      </div>
      <form class="cp-input" onSubmit=${(e) => { e.preventDefault(); send(); }}>
        <input class="input" placeholder="Ask the copilot…" value=${text} onInput=${(e) => setText(e.target.value)} disabled=${busy} />
        <button class="btn primary sm" disabled=${busy || !text.trim()}>Send</button>
      </form>
    </div>`}`;
}
