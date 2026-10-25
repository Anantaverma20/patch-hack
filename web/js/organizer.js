import { useState } from "../vendor/preact-htm.js";
import {
  CountUp, DayTabs, Header, Icon, Modal, SessionStatus, Skeleton, TZ, ago, api, cap, dayKey, dayName, fmtTime, fmtWhen, html, rel, serverNow,
  toast, useData,
} from "./core.js";

// The first conference day that still has something ahead (the last day once all are over).
const currentDay = (sessions, now) => {
  const next = sessions.filter((s) => s.end > now).sort((a, b) => a.start - b.start)[0];
  return next ? next.day ?? 0 : Math.max(0, ...sessions.map((s) => s.day ?? 0));
};
const countByDay = (sessions) => sessions.reduce((m, s) => ({ ...m, [s.day ?? 0]: (m[s.day ?? 0] || 0) + 1 }), {});

// ================================================================ Overview

export function Overview() {
  const [s] = useData("/api/org/sessions");
  const [h] = useData("/api/org/help");
  const [r] = useData("/api/org/readiness");
  if (!s || !h || !r) return html`<${Header} eyebrow="Overview" title="Today at a glance." /><${Skeleton} />`;
  const now = s.now;
  const upcoming = s.sessions.filter((x) => x.end > now && x.status !== "cancelled").slice(0, 5);
  const open = h.clusters.flatMap((c) => c.reports).filter((x) => x.status === "open");
  const needing = new Set(h.clusters.flatMap((c) => c.reports.filter((x) => x.status === "open").map((x) => x.aid))).size;
  const changes = s.sessions.filter((x) => x.status !== "open" && x.end > now);
  const strong = h.clusters.filter((c) => c.strength === "strong" && !c.fixSent);
  const tiles = [
    ["Upcoming sessions", upcoming.length, "calendar"], ["Open help reports", open.length, "message"],
    ["Attendees needing help", needing, "users"], ["Possible shared causes", strong.length, "graph"],
  ];
  return html`
    <${Header} eyebrow="Organizer overview" title="Keep the day moving." lede="Upcoming sessions, unresolved incidents, and who needs a hand." />
    <div class="grid4">${tiles.map(([l, n, ic], i) => html`<div class="card stat rise" style=${`--i:${i}`}>
      <span class="muted"><${Icon} n=${ic} s=${18} /></span><div class="num"><${CountUp} value=${n} /></div><div class="lbl">${l}</div></div>`)}</div>

    ${strong.map((c) => html`<div class="card rise section" style="--i:4;border-color:#c8db96">
      <div class="between"><span class="pill lime"><${Icon} n="graph" s=${13} /> Possible common cause</span><a class="btn sm" href="#/organizer/help">Open help queue</a></div>
      <p class="insight">${c.attendees} attendees failed <em>${c.check}</em>. All ${c.attendees} use ${c.fact.key} <code>${c.fact.value}</code>.</p>
      <p class="muted small" style="margin:0">${c.fact.passing} of ${c.passersTotal} attendees who passed use it.</p></div>`)}

    <div class="grid2 section" style="align-items:start">
      <div class="card rise" style="--i:5"><h2>Up next</h2>
        <table class="table"><tbody>${upcoming.map((x) => html`<tr>
          <td style="width:150px;white-space:nowrap"><b>${fmtWhen(x.start)}</b></td>
          <td>${x.title}<div class="muted small">${x.room.name} · ${x.planned} planned${x.ready != null ? ` · ${x.ready} ready` : ""}</div></td>
          <td style="text-align:right"><${SessionStatus} s=${x} /></td></tr>`)}</tbody></table></div>
      <div class="card rise" style="--i:6"><h2>Needs attention</h2>
        ${open.length === 0 && changes.length === 0 && html`<p class="muted">Nothing right now.</p>`}
        ${open.slice(0, 6).map((x) => html`<div class="resolved-row"><span class="pill amber">Help</span><span style="flex:1">${x.name} · ${x.step || "setup"}</span><span class="muted small">${ago(x.at)}</span></div>`)}
        ${changes.map((x) => html`<div class="resolved-row"><${SessionStatus} s=${x} /><span style="flex:1">${x.title}</span><span class="muted small">${ago(x.statusAt)}</span></div>`)}
        ${r.failures.slice(0, 2).map((f) => html`<div class="resolved-row"><span class="pill">Setup</span><span style="flex:1">${f.n}× ${f.check} · ${f.code}</span></div>`)}
      </div>
    </div>`;
}

// ================================================================ Sessions

export function OrgSessions({ conf }) {
  const [data] = useData("/api/org/sessions");
  const [moving, setMoving] = useState(null);
  const [adding, setAdding] = useState(false);
  const [pickedDay, setDay] = useState(null);
  if (!data) return html`<${Header} eyebrow="Sessions" title="Sessions & live updates." /><${Skeleton} />`;
  const now = data.now;
  const c = conf.conference;
  const day = pickedDay ?? currentDay(data.sessions, now);
  const set = async (s, status, room) => {
    await api(`/api/org/sessions/${s.id}/status`, { status, room });
    setMoving(null);
    toast({ title: `Published: ${s.title} is ${status === "open" ? "open again" : status}`, body: `${s.planned} attendees with it in their day will see this now.` });
  };
  return html`
    <${Header} eyebrow="Sessions" title="Sessions & live updates." lede="Publish room changes and availability. Attendees with the session in their day see it right away, with alternatives."
      right=${html`<button class="btn primary" onClick=${() => setAdding(true)}><${Icon} n="plus" s=${16} /> Add session</button>`} />
    <${DayTabs} c=${c} value=${day} onChange=${setDay} counts=${countByDay(data.sessions)} />
    ${c?.themes?.[day] && html`<p class="muted small" style="margin:-6px 0 14px">${c.themes[day]}</p>`}
    ${data.sessions.filter((s) => (s.day ?? 0) === day).map((s, i) => html`<div class=${`card hover rise ${s.end < now ? "past-card" : ""}`} style=${`--i:${Math.min(i, 8)}`} key=${s.id}>
      <div class="between" style="align-items:flex-start;flex-wrap:wrap">
        <div style="min-width:min(100%, 280px);flex:1">
          <div class="row"><h3 style="font-size:17px">${s.title}</h3><${SessionStatus} s=${s} /></div>
          <div class="muted small" style="margin-top:4px">${fmtWhen(s.start)}–${fmtTime(s.end)} (${rel(s.start, now)}) · ${s.room.name} · ${s.speaker} · ${cap(s.format)}</div>
          <div class="row small" style="margin-top:10px">
            <span class="pill">${s.planned} planned · ${s.taken}/${s.capacity} seats</span>
            ${s.requires.length > 0 && html`<span class="pill">${s.ready ?? 0} of ${s.planned} setup-ready</span>`}
            ${s.covers.map((c) => html`<span class="pill lime">${c.name} · ${c.depth}/3</span>`)}
            <span class="muted">Last update ${ago(s.statusAt)}</span>
          </div>
        </div>
        <div class="row" style="justify-content:flex-end">
          ${s.status !== "full" && html`<button class="btn sm" onClick=${() => set(s, "full")}>Mark full</button>`}
          <button class="btn sm" onClick=${() => setMoving(moving === s.id ? null : s.id)}>Move room</button>
          ${s.status !== "cancelled" && html`<button class="btn sm ghost" onClick=${() => set(s, "cancelled")}>Cancel</button>`}
          ${s.status !== "open" && html`<button class="btn sm ghost" onClick=${() => set(s, "open")}>Reopen</button>`}
        </div>
      </div>
      ${moving === s.id && html`<div class="evidence fade row"><span class="small">Move to</span>
        ${conf.rooms.filter((r) => r.id !== s.room.id).map((r) => html`<button class="chip" onClick=${() => set(s, "moved", r.id)}>${r.name}</button>`)}</div>`}
    </div>`)}
    ${adding && html`<${AddSession} conf=${conf} day=${day} onClose=${() => setAdding(false)} />`}`;
}

function AddSession({ conf, day, onClose }) {
  // Default: 45 minutes from now on today's tab, 10:00 on any later day (venue time).
  const soon = new Date(Math.ceil((serverNow() + 45 * 60e3) / 300e3) * 300e3);
  const soonHHMM = new Intl.DateTimeFormat("en-GB", { timeZone: TZ, hour: "2-digit", minute: "2-digit" }).format(soon);
  const soonDay = (conf.conference.dayKeys || []).indexOf(dayKey(soon));
  // On today's tab (or when "soon" already rolled past midnight) use the soon slot with its own day.
  const useSoon = soonDay >= 0 && soonDay >= day;
  const [f, setF] = useState({ title: "", speaker: "", goal: "evals", depth: 2, level: "intermediate", format: "workshop",
    day: useSoon ? soonDay : day, time: useSoon ? soonHHMM : "10:00", duration: 45, room: "room-c", requires: ["runtime"], capacity: 40, outcomes: [""] });
  const up = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    try { await api("/api/org/sessions", { ...f, day: Number(f.day) }); }
    catch (e) { toast({ title: "Couldn't publish the session", body: "Pick a day and a start time that hasn't passed.", kind: "warn" }); return; }
    toast({ title: "Session published", body: `${f.title} · ${dayName(conf.conference, Number(f.day))} ${f.time}` }); onClose();
  };
  return html`<${Modal} onClose=${onClose}>
    <h2>Add a session</h2>
    <div class="grid2">
      <div><label class="field">Title</label><input class="input" value=${f.title} onInput=${up("title")} /></div>
      <div><label class="field">Speaker</label><input class="input" value=${f.speaker} onInput=${up("speaker")} /></div>
      <div><label class="field">Covers goal</label><select class="input" value=${f.goal} onChange=${up("goal")}>${conf.goals.map((g) => html`<option value=${g.id}>${g.name}</option>`)}</select></div>
      <div><label class="field">Room</label><select class="input" value=${f.room} onChange=${up("room")}>${conf.rooms.map((r) => html`<option value=${r.id}>${r.name}</option>`)}</select></div>
      <div><label class="field">Day</label><select class="input" value=${f.day} onChange=${up("day")}>
        ${(conf.conference.days || []).map((_, i) => html`<option value=${i}>${dayName(conf.conference, i)}</option>`)}</select></div>
      <div><label class="field">Starts at (venue time)</label><input class="input" type="time" value=${f.time} onInput=${up("time")} /></div>
      <div><label class="field">Level</label><select class="input" value=${f.level} onChange=${up("level")}><option>beginner</option><option>intermediate</option><option>advanced</option></select></div>
    </div>
    <label class="field">Practical outcome</label><input class="input" value=${f.outcomes[0]} onInput=${(e) => setF({ ...f, outcomes: [e.target.value] })} />
    <label class="field">Technical prerequisites</label>
    <div class="chips">${conf.checks.map((c) => html`<button class=${`chip ${f.requires.includes(c.id) ? "on" : ""}`}
      onClick=${() => setF({ ...f, requires: f.requires.includes(c.id) ? f.requires.filter((x) => x !== c.id) : [...f.requires, c.id] })}>${c.name}</button>`)}</div>
    <div class="row" style="margin-top:20px"><button class="btn primary" disabled=${!f.title} onClick=${save}>Publish session</button><button class="btn ghost" onClick=${onClose}>Cancel</button></div>
  <//>`;
}

// ================================================================ Readiness

export function Readiness({ conf }) {
  const [data] = useData("/api/org/readiness");
  const [busy, setBusy] = useState(null);
  const [pickedDay, setDay] = useState(null);
  if (!data) return html`<${Header} eyebrow="Readiness" title="Who's ready to build?" /><${Skeleton} />`;
  const act = async (p, a) => { setBusy(p.id + a); await api(`/api/org/packages/${p.id}/${a}`); setBusy(null); };
  const now = serverNow();
  const withEnd = data.sessions.map((s) => ({ ...s, end: s.start + 3600e3 }));
  const day = pickedDay ?? currentDay(withEnd, now);
  return html`
    <${Header} eyebrow="Readiness" title="Who's ready to build?" lede="Aggregate results from attendees' setup checks, shared failures, and the setup packages you publish. Fix setup problems days before a workshop, not at the front of the room." />
    <${DayTabs} c=${conf?.conference} value=${day} onChange=${setDay} counts=${countByDay(data.sessions)} />
    <div class="grid2" style="align-items:start">
      ${data.sessions.filter((s) => (s.day ?? 0) === day).length === 0 && html`<div class="soft">No hands-on sessions with setup checks this day.</div>`}
      ${data.sessions.filter((s) => (s.day ?? 0) === day).map((s, i) => html`<div class="card rise" style=${`--i:${i}`} key=${s.id}>
        <div class="between"><h3>${s.title}</h3><span class="muted small" style="white-space:nowrap">${fmtWhen(s.start)}</span></div>
        <table class="table" style="margin-top:10px"><tbody>${s.checks.map((c) => html`<tr>
          <td>${c.name}</td>
          <td style="width:42%"><div class="meter"><i class="p" style=${`width:${c.planned ? (c.pass / c.planned) * 100 : 0}%`}></i><i class="f" style=${`width:${c.planned ? (c.fail / c.planned) * 100 : 0}%`}></i></div></td>
          <td class="small" style="text-align:right;white-space:nowrap">${c.pass}/${c.planned}${c.fail ? html` · <span style="color:var(--amber)">${c.fail} failing</span>` : ""}</td></tr>`)}</tbody></table>
      </div>`)}
    </div>
    <div class="grid2 section" style="align-items:start">
      <div class="card rise"><h2>Shared setup failures</h2>
        ${data.failures.map((f) => html`<div style="padding:10px 0;border-top:1px solid var(--line-2)">
          <div class="between"><b>${f.check}</b><span class="pill amber">${f.n} attendee${f.n > 1 ? "s" : ""}</span></div>
          <div class="muted small" style="margin:3px 0 6px">${f.code}</div><div class="err">${f.example}</div></div>`)}
      </div>
      <div class="card rise"><h2>Setup packages</h2>
        <p class="muted small" style="margin-top:-6px">Every package runs in a clean sandbox before you approve it for attendees.</p>
        ${data.packages.map((p) => html`<div style="padding:12px 0;border-top:1px solid var(--line-2)">
          <div class="between"><div><b>${p.name}</b> <span class="muted small">v${p.version}</span></div>
            <span class=${`pill ${p.status === "published" ? "ready" : "amber"}`}>${p.status === "published" ? "Published" : "In review"}</span></div>
          <div class="row small" style="margin-top:8px">
            <span class="muted">Sandbox: ${p.sandbox === "passed" ? "passed" : "not run"}</span>
            ${p.status !== "published" && html`
              <button class="btn sm" disabled=${busy} onClick=${() => act(p, "sandbox")}>${busy === p.id + "sandbox" ? html`<span class="spinner"></span>` : null} Run in sandbox</button>
              <button class="btn sm primary" disabled=${p.sandbox !== "passed" || busy} onClick=${() => act(p, "publish")}>Approve & publish</button>`}
          </div></div>`)}
      </div>
    </div>`;
}

// ================================================================ Help queue

export function HelpQueue() {
  const [data] = useData("/api/org/help");
  const [fixFor, setFixFor] = useState(null);
  const [openEv, setOpenEv] = useState({});
  if (!data) return html`<${Header} eyebrow="No one left quietly stuck" title="A little help goes a long way." /><${Skeleton} />`;
  const openCount = data.clusters.reduce((n, c) => n + c.reports.filter((r) => r.status === "open").length, 0);
  const lastFix = data.fixes[0];
  return html`
    <${Header} eyebrow="No one left quietly stuck" title="A little help goes a long way." lede="Review shared blockers, assign a helper, and close the loop."
      right=${html`<span class=${`pill ${openCount ? "amber" : "ready"}`}><${CountUp} value=${openCount} /> open reports</span>`} />

    ${data.clusters.length === 0 && html`<div class="card rise" style="padding:26px">
      <h3 style="font-size:18px">${lastFix ? "Shared endpoint issue resolved." : "No open reports."}</h3>
      <p class="muted" style="margin:6px 0 0">${lastFix ? `The approved fix passed verification for all ${data.resolved.filter((r) => r.status === "resolved_verified").length} reports.` : "When attendees press “I'm stuck”, related reports group here."}</p></div>
      <div class="soft rise" style="--i:1;margin-top:18px">Switch to Attendee → Help to submit a new demo report. It shows up here right away.</div>`}

    ${data.clusters.map((c, i) => {
      const total = c.reports.length;
      const ev = openEv[c.checkId + c.code];
      return html`<div class="card rise" style=${`--i:${i};${c.strength === "strong" ? "border-color:#c8db96" : ""}`} key=${c.checkId + c.code}>
        <div class="between">
          <span class=${`pill ${c.strength === "strong" ? "lime" : ""}`}><${Icon} n="graph" s=${13} />
            ${c.strength === "strong" ? "Possible common cause" : c.strength === "weak" ? "Shared symptom · weak signal" : "Shared symptom"}</span>
          ${c.fixSent ? html`<span class="pill lime"><span class="spinner" style="width:11px;height:11px"></span> Fix sent · waiting for checks</span>`
            : html`<span class="muted small">latest ${ago(Math.max(...c.reports.map((r) => r.at)))}</span>`}
        </div>
        <p class="insight"><${CountUp} value=${c.attendees} /> attendee${c.attendees > 1 ? "s" : ""} failed <em>${c.check}</em>${c.fact ? html`. All ${c.attendees} use ${c.fact.key} <code>${c.fact.value}</code>.` : "."}</p>
        ${c.fact && html`<p class="muted small" style="margin:0">${c.fact.passing} of ${c.passersTotal} attendees who passed this check use it too${c.strength === "strong" ? ". That points to a shared cause, so treat it as a lead and confirm with the evidence." : ", so this may be coincidence."}</p>`}
        <div class="row" style="margin-top:16px">
          ${!c.fixSent && html`<button class="btn sm primary" onClick=${() => setFixFor(c)}><${Icon} n="shield" s=${15} /> Review & publish fix</button>`}
          <select class="input" style="width:auto;padding:7px 10px;font-size:13.5px" onChange=${(e) => e.target.value && api("/api/org/help/assign", { ids: c.reports.map((r) => r.id), helper: e.target.value }).then(() => toast({ title: `${e.target.value} assigned`, body: `${total} reports` }))}>
            <option value="">Assign helper…</option>${data.helpers.map((h) => html`<option selected=${c.reports[0]?.helper === h}>${h}</option>`)}</select>
          <button class="btn sm ghost" onClick=${() => setOpenEv({ ...openEv, [c.checkId + c.code]: !ev })}>${ev ? "Hide" : "Inspect"} evidence <${Icon} n="chevron" s=${14} /></button>
        </div>
        ${ev && html`<div class="evidence fade">
          <b class="small">Environment facts every reporter shares</b>
          <table class="table" style="margin:6px 0 14px"><thead><tr><th>Fact</th><th>Reporters</th><th>Passed with it</th></tr></thead><tbody>
            ${c.facts.map((f) => html`<tr><td><code>${f.key} = ${f.value}</code></td><td>${f.n}/${c.attendees}</td><td>${f.passing} of ${c.passersTotal}</td></tr>`)}</tbody></table>
          <b class="small">Reports</b>
          ${c.reports.map((r) => html`<div style="padding:8px 0;border-top:1px solid var(--line-2)">
            <div class="between small"><span><b>${r.name}</b> · ${r.step || "setup"}${r.needsHelper ? html` · <span style="color:var(--red)">asked for a helper</span>` : ""}</span><span class="muted">${ago(r.at)}</span></div>
            <div class="err" style="margin-top:5px">${r.error}</div></div>`)}
        </div>`}
      </div>`;
    })}

    ${data.resolved.length > 0 && html`<div class="section"><h2>Resolved</h2><div class="card">
      ${data.resolved.map((r) => html`<div class="resolved-row" key=${r.id}>
        ${r.status === "resolved_verified" ? html`<span class="pill ready"><${Icon} n="check" s=${13} w=${2.6} /> Verified by check</span>` : html`<span class="pill">Attendee confirmed · not verified</span>`}
        <span style="flex:1">${r.name} · ${r.check}</span><span class="muted small">${ago(r.at)}</span></div>`)}
    </div></div>`}

    ${fixFor && html`<${FixModal} c=${fixFor} onClose=${() => setFixFor(null)} />`}`;
}

function FixModal({ c, onClose }) {
  const [text, setText] = useState(c.suggestedFix);
  const [busy, setBusy] = useState(false);
  const publish = async () => {
    setBusy(true);
    await api("/api/org/fix", { ids: c.reports.map((r) => r.id), text, checkId: c.checkId, key: c.fact?.key || "", value: c.fact?.value || "" });
    toast({ title: "Fix approved and published", body: `Sent to ${c.attendees} attendees. Each report closes only when that attendee's check passes again.` });
    onClose();
  };
  return html`<${Modal} onClose=${onClose}>
    <p class="eyebrow">Human approval</p>
    <h2>Publish a fix to ${c.attendees} attendees</h2>
    <p class="muted small" style="margin-top:-6px">Suspected cause: ${c.check} with ${c.fact ? html`<code>${c.fact.key} = ${c.fact.value}</code>` : "no shared fact"}. Review the wording before it goes out.</p>
    <textarea class="input" rows="5" value=${text} onInput=${(e) => setText(e.target.value)}></textarea>
    ${c.fact?.key === "endpoint" && html`<div class="soft small" style="margin-top:12px">Also updates the endpoint in the setup manifest, so anyone who runs the setup skill from now on gets the corrected value.</div>`}
    <div class="row" style="margin-top:18px">
      <button class="btn primary" disabled=${!text || busy} onClick=${publish}>${busy ? html`<span class="spinner" style="border-top-color:#fff"></span>` : html`<${Icon} n="shield" s=${16} />`} Approve & publish</button>
      <button class="btn ghost" onClick=${onClose}>Cancel</button>
    </div>
  <//>`;
}
