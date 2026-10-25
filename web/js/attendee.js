import { useEffect, useRef, useState } from "../vendor/preact-htm.js";
import {
  AID, Copy, Drawer, Header, Icon, ReadyPill, SessionStatus, Skeleton, ago, api, cap, dayName, fmtTime, fmtWhen, html, localHour, rel,
  serverNow, toast, useData, useNow,
} from "./core.js";

const HANDS_ON = ["workshop", "hackathon"];
// Consecutive runs of sessions on the same conference day.
function byDay(list) {
  const out = [];
  for (const s of list) {
    const g = out[out.length - 1];
    if (g && g.day === (s.day ?? 0)) g.items.push(s); else out.push({ day: s.day ?? 0, items: [s] });
  }
  return out;
}

const go = (h) => { location.hash = h; };
const first = (name) => (name || "").split(" ")[0];

// ================================================================ Join

export function Join({ conf }) {
  const [sessions] = useData(`/api/sessions?aid=${AID}`);
  const [goals, setGoals] = useState([]);
  const [level, setLevel] = useState("intermediate");
  const [interests, setInterests] = useState([]);
  const [stepFree, setStepFree] = useState(false);
  const [timeNote, setTimeNote] = useState("");
  const [busy, setBusy] = useState(false);
  const toggle = (xs, set, id) => set(xs.includes(id) ? xs.filter((x) => x !== id) : [...xs, id]);
  const sample = () => { setGoals(["evals"]); setLevel("intermediate"); setInterests(["s2", "s7"]); setStepFree(false); setTimeNote("Need to leave by 5:30 PM"); };
  const build = async () => {
    setBusy(true);
    await api("/api/onboard", { aid: AID, goals, level, interests, stepFree, timeNote });
    go("#/attendee/myday");
  };
  const c = conf?.conference;
  const pickable = (sessions?.sessions || []).filter((s) => s.end > serverNow() && HANDS_ON.includes(s.format));

  return html`<div class="join">
    <div class="hero-card rise">
      <div class="blob"></div>
      <p class="eyebrow" style="color:#b7baaf">You're invited</p>
      <h1>${c?.name || "Future / Forward"}</h1>
      <p style="color:#d6d8cf;margin:0">${c?.city} · ${c?.dates} · ${c?.venue}</p>
      <div class="row" style="margin-top:22px">
        <a class="btn lime" href="#join-form"><${Icon} n="users" s=${17} /> Join as attendee</a>
        <a class="btn" style="background:#2a302c;color:#fff;border-color:#3a413c" href="#/organizer/overview">Organizer view <${Icon} n="arrow" s=${16} /></a>
      </div>
    </div>

    <div class="sample-note rise" style="--i:1;margin-top:18px">
      <${Icon} n="sparkle" />
      <div style="flex:1"><b>Demo shortcut.</b> <span class="muted">Fill the form with a sample attendee who wants to learn agent evaluation.</span></div>
      <button class="btn sm" onClick=${sample}>Use sample attendee</button>
    </div>

    <div class="card rise" id="join-form" style="--i:2;margin-top:18px">
      <h2>Build your day</h2>
      <label class="field">What do you want to learn?</label>
      <div class="chips">${(conf?.goals || []).map((g) => html`
        <button class=${`chip ${goals.includes(g.id) ? "on" : ""}`} onClick=${() => toggle(goals, setGoals, g.id)}>${g.name}</button>`)}</div>

      <label class="field">Your experience level</label>
      <div class="chips">${["beginner", "intermediate", "advanced"].map((l) => html`
        <button class=${`chip ${level === l ? "on" : ""}`} onClick=${() => setLevel(l)}>${cap(l)}</button>`)}</div>

      <label class="field">Hands-on workshops you'd like to join <span class="muted small">(optional; talks are added for your goals)</span></label>
      ${byDay(pickable).map((g) => html`<div class="pick-day">
        <div class="small muted pick-day-label">${dayName(c, g.day)}${c?.themes?.[g.day] ? ` · ${c.themes[g.day]}` : ""}</div>
        <div class="chips">${g.items.map((s) => html`
          <button class=${`chip ${interests.includes(s.id) ? "on" : ""}`} onClick=${() => toggle(interests, setInterests, s.id)}>
            ${s.title} <span class="muted small">· ${fmtTime(s.start)}</span></button>`)}</div></div>`)}

      <label class="field">Preferences <span class="muted small">(optional)</span></label>
      <div class="row">
        <button class=${`chip ${stepFree ? "on" : ""}`} onClick=${() => setStepFree(!stepFree)}>Step-free routes only</button>
        <input class="input" style="max-width:320px" placeholder="Time constraints, e.g. leave by 5:30" value=${timeNote} onInput=${(e) => setTimeNote(e.target.value)} />
      </div>

      <div class="row" style="margin-top:26px">
        <button class="btn primary" disabled=${!goals.length || busy} onClick=${build}>
          ${busy ? html`<span class="spinner" style="border-top-color:#fff"></span>` : html`<${Icon} n="sparkle" s=${17} />`} Build my day</button>
        ${!goals.length && html`<span class="muted small">Pick at least one goal.</span>`}
      </div>
    </div>
  </div>`;
}

// ================================================================ My Day

export function MyDay({ me, conf, openRescue }) {
  const now = useNow(10000);
  const [shown, setShown] = useState({});
  if (!me) return html`<${Skeleton} />`;
  const a = me.attendee;
  const c = conf?.conference;
  const hour = localHour(now);
  const greet = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
  const n = me.nextUp;
  const groups = byDay(me.plan);
  // The first two days that still have something ahead start open; the rest fold away.
  const openByDefault = new Set(groups.filter((g) => g.items.some((s) => s.end > now)).slice(0, 2).map((g) => g.day));
  const isOpen = (d) => shown[d] ?? openByDefault.has(d);
  return html`
    <${Header} eyebrow="My day" title=${`${greet}, ${first(a.name)}.`} lede="What's next, and only what needs your attention." />
    ${n ? html`<${NextUp} s=${n} openRescue=${openRescue} now=${now} />` : html`<div class="card rise">You're done for the week. Nice work.</div>`}

    ${me.attention.length > 0 && html`<div class="section">
      <h2 class="rise">Needs attention</h2>
      ${me.attention.map((x, i) => html`<${Attention} key=${x.id} x=${x} i=${i} openRescue=${openRescue} />`)}
    </div>`}

    <div class="section">
      <div class="between"><h2 class="rise">Your week</h2><a class="btn ghost sm" href="#/attendee/sessions"><${Icon} n="plus" s=${16} /> Add sessions</a></div>
      ${groups.map((g) => html`<div class="day-group" key=${g.day}>
        <button class=${`day-head ${isOpen(g.day) ? "open" : ""}`} aria-expanded=${isOpen(g.day)} onClick=${() => setShown({ ...shown, [g.day]: !isOpen(g.day) })}>
          <span><b>${dayName(c, g.day)}</b> <span class="muted small">${c?.themes?.[g.day] || ""}</span></span>
          <span class="muted small">${g.items.length} session${g.items.length > 1 ? "s" : ""} <${Icon} n="chevron" s=${15} cls="chev" /></span>
        </button>
        ${isOpen(g.day) && html`<div class="timeline">${g.items.map((s, i) => html`<${TimelineItem} key=${s.id} s=${s} i=${i} now=${now} openRescue=${openRescue} />`)}</div>`}
      </div>`)}
    </div>`;
}

function NextUp({ s, openRescue, now }) {
  const disrupted = s.status === "full" || s.status === "cancelled";
  const needsSetup = s.requires.length > 0 && !s.readiness.ready;
  return html`<div class="next-card rise" style="--i:1">
    <div class="blob"></div>
    <div class="between" style="position:relative">
      <p class="eyebrow" style="margin:0">${s.live ? "Happening now" : "Next up"}</p>
      <span class="countdown">${s.live ? "live" : rel(s.start, now)}</span>
    </div>
    <h2 style="position:relative">${s.title}</h2>
    <div class="meta" style="position:relative">
      <span><${Icon} n="clock" s=${16} /> ${fmtWhen(s.start, now)}–${fmtTime(s.end)}</span>
      <span><${Icon} n="pin" s=${16} /> ${s.room.name}</span>
      <span><${Icon} n="users" s=${16} /> ${s.speaker}</span>
      ${s.status !== "open" && html`<${SessionStatus} s=${s} />`}
      ${s.requires.length > 0 && html`<${ReadyPill} r=${s.readiness} />`}
    </div>
    <div class="row" style="position:relative">
      ${disrupted ? html`<button class="btn lime" onClick=${() => openRescue(s.id)}><${Icon} n="route" s=${17} /> View alternatives</button>`
        : needsSetup ? html`<a class="btn lime" href="#/attendee/ready"><${Icon} n="wrench" s=${17} /> Get ready</a>`
        : s.live ? html`<a class="btn lime" href="#/attendee/help"><${Icon} n="message" s=${17} /> Open session companion</a>`
        : html`<a class="btn lime" href=${`#/attendee/sessions?open=${s.id}`}>View next session <${Icon} n="arrow" s=${16} /></a>`}
      <a class="btn" href=${`#/attendee/sessions?open=${s.id}`}>View details</a>
    </div>
  </div>`;
}

const ATTN = {
  full: ["alert", "var(--red-soft)", "var(--red)"], cancelled: ["alert", "var(--red-soft)", "var(--red)"],
  moved: ["door", "var(--blue-soft)", "var(--blue)"], setup: ["wrench", "var(--amber-soft)", "var(--amber)"],
  fix: ["zap", "var(--lime-soft)", "var(--lime-ink)"],
};
function Attention({ x, i, openRescue }) {
  const [ic, bg, fg] = ATTN[x.kind] || ATTN.setup;
  const action = {
    full: html`<button class="btn sm primary" onClick=${() => openRescue(x.sessionId)}>View alternatives</button>`,
    cancelled: html`<button class="btn sm primary" onClick=${() => openRescue(x.sessionId)}>View alternatives</button>`,
    moved: html`<button class="btn sm" onClick=${() => api("/api/ack", { aid: AID, sid: x.sessionId })}>Got it</button>`,
    setup: html`<a class="btn sm" href="#/attendee/ready">Get ready</a>`,
    fix: html`<a class="btn sm lime" href="#/attendee/ready">Run check again</a>`,
  }[x.kind];
  return html`<div class=${`card attn ${x.urgent ? "urgent" : "rise"}`} style=${`--i:${i}`}>
    <span class="ic" style=${`background:${bg};color:${fg}`}><${Icon} n=${ic} /></span>
    <div class="grow"><b>${x.text}</b>${x.at && html`<div class="muted small">Updated by the organizer ${ago(x.at)}</div>`}</div>
    ${action}
  </div>`;
}

function TimelineItem({ s, i, now, openRescue }) {
  const past = s.end < now;
  const struck = s.status === "full" || s.status === "cancelled";
  return html`<div class=${`tl-item rise ${s.live ? "live" : ""} ${past ? "past" : ""} ${struck ? "struck" : ""}`} style=${`--i:${i + 2}`}>
    ${s.travel?.gap != null && !past && html`<div class="travel"><${Icon} n="walk" s=${15} />
      ${s.travel.walk}-min walk to ${s.room.name} · ${Math.max(0, s.travel.gap)} min between sessions
      ${s.travel.gap < s.travel.walk && html`<span class="pill amber">Tight</span>`}</div>`}
    <div class="card hover" style="display:flex;gap:18px;align-items:flex-start">
      <div class="time-col">${fmtTime(s.start)}</div>
      <div style="flex:1;min-width:0">
        <div class="row"><h3>${s.title}</h3><${SessionStatus} s=${s} /></div>
        <div class="muted small" style="margin:4px 0 10px">${s.room.name} · ${s.speaker} · ${cap(s.format)} · until ${fmtTime(s.end)}</div>
        <div class="row">
          ${s.requires.length > 0 && html`<${ReadyPill} r=${s.readiness} />`}
          <span class="spacer" style="flex:1"></span>
          ${struck && html`<button class="btn sm primary" onClick=${() => openRescue(s.id)}>View alternatives</button>`}
          ${!struck && s.requires.length > 0 && !s.readiness.ready && !past && html`<a class="btn sm" href="#/attendee/ready">Get ready</a>`}
          ${s.live && !struck && html`<a class="btn sm" href="#/attendee/help">Get help</a>`}
          <a class="btn sm ghost" href=${`#/attendee/sessions?open=${s.id}`}>View details</a>
        </div>
      </div>
    </div>
  </div>`;
}

// ================================================================ Sessions

export function Sessions({ me, conf, query }) {
  const [data] = useData(`/api/sessions?aid=${AID}`);
  const [q, setQ] = useState("");
  const [topic, setTopic] = useState("");
  const [level, setLevel] = useState("");
  const [format, setFormat] = useState("");
  const [when, setWhen] = useState("upcoming");
  const [open, setOpen] = useState(query.open || null);
  useEffect(() => { if (query.open) setOpen(query.open); }, [query.open]);
  if (!data) return html`<${Header} eyebrow="Sessions" title="Find your sessions." /><${Skeleton} />`;
  const now = data.now;
  const goals = me?.attendee?.goals || [];
  const c = conf?.conference;
  const inWhen = (s) => when === "all" ? true : when === "upcoming" ? s.end > now
    : when === "hour" ? s.start < now + 3600e3 && s.end > now : (s.day ?? 0) === Number(when.slice(4));
  const list = data.sessions.filter((s) =>
    (!q || (s.title + s.speaker + s.summary).toLowerCase().includes(q.toLowerCase())) &&
    (!topic || s.covers.some((c) => c.goal === topic)) && (!level || s.level === level) && (!format || s.format === format) && inWhen(s));
  const goalNames = Object.fromEntries((data.sessions.flatMap((s) => s.covers)).map((c) => [c.goal, c.name]));
  const formats = [...new Set(data.sessions.map((s) => s.format))];
  let n = 0;
  return html`
    <${Header} eyebrow="Sessions" title="Find your sessions." lede=${`${data.sessions.length} sessions over ${c?.days?.length || 1} days. Fit and setup readiness are shown separately: having the tools installed doesn't mean the level is right for you.`} />
    <div class="card rise" style="padding:14px;display:grid;grid-template-columns:2fr repeat(4,1fr);gap:10px" >
      <div style="position:relative"><span style="position:absolute;left:12px;top:11px;color:var(--muted)"><${Icon} n="search" s=${18} /></span>
        <input class="input" style="padding-left:38px" placeholder="Search sessions or speakers" value=${q} onInput=${(e) => setQ(e.target.value)} /></div>
      <select class="input" value=${topic} onChange=${(e) => setTopic(e.target.value)}><option value="">All topics</option>
        ${Object.entries(goalNames).map(([id, n]) => html`<option value=${id}>${n}</option>`)}</select>
      <select class="input" value=${when} onChange=${(e) => setWhen(e.target.value)}>
        <option value="upcoming">All upcoming</option><option value="hour">Next hour</option>
        ${(c?.days || []).map((_, i) => html`<option value=${`day-${i}`}>${dayName(c, i)}</option>`)}
        <option value="all">Whole week, incl. past</option></select>
      <select class="input" value=${level} onChange=${(e) => setLevel(e.target.value)}><option value="">Any level</option>
        <option value="beginner">Beginner</option><option value="intermediate">Intermediate</option><option value="advanced">Advanced</option></select>
      <select class="input" value=${format} onChange=${(e) => setFormat(e.target.value)}><option value="">Any format</option>
        ${formats.map((f) => html`<option value=${f}>${cap(f)}</option>`)}</select>
    </div>
    <div class="section" style="margin-top:18px">
      ${list.length === 0 && html`<div class="soft">No sessions match those filters.</div>`}
      ${byDay(list).map((g) => html`<div key=${g.day}>
        <h2 class="day-title rise">${dayName(c, g.day)}<span class="muted small">${c?.themes?.[g.day] ? ` · ${c.themes[g.day]}` : ""} · ${g.items.length} session${g.items.length > 1 ? "s" : ""}</span></h2>
        ${g.items.map((s) => html`<${SessionCard} key=${s.id} s=${s} i=${n++} now=${now} goals=${goals} myLevel=${me?.attendee?.level}
          open=${open === s.id} onToggle=${() => setOpen(open === s.id ? null : s.id)} />`)}</div>`)}
    </div>`;
}

function SessionCard({ s, i, now, open, onToggle, myLevel }) {
  const [detail] = useData(open ? `/api/session/${s.id}` : null);
  const [busy, setBusy] = useState(false);
  const fit = s.fit[0];
  const toggle = async () => { setBusy(true); await api("/api/plan", { aid: AID, sid: s.id, action: s.inPlan ? "remove" : "add" }); setBusy(false); };
  return html`<div class="card hover rise" style=${`--i:${Math.min(i, 8)}`}>
    <div class="between" style="align-items:flex-start">
      <div style="min-width:0">
        <div class="row"><h3 style="font-size:17px">${s.title}</h3><${SessionStatus} s=${s} />${s.inPlan && html`<span class="pill lime">In your day</span>`}</div>
        <div class="muted small" style="margin-top:3px">${s.speaker} · ${cap(s.format)}</div>
      </div>
      <button class=${`btn sm ${s.inPlan ? "" : "primary"}`} disabled=${busy || s.status === "cancelled" || (s.status === "full" && !s.inPlan)} onClick=${toggle}>
        ${s.inPlan ? "Remove" : html`<${Icon} n="plus" s=${15} /> Add to my day`}</button>
    </div>
    <ul style="margin:12px 0;padding-left:18px;color:var(--ink-2)">${s.outcomes.slice(0, 2).map((o) => html`<li>${o}</li>`)}</ul>
    <div class="row small">
      <span class="pill"><${Icon} n="clock" s=${13} /> ${fmtWhen(s.start, now)}–${fmtTime(s.end)} · ${rel(s.start, now)}</span>
      <span class="pill"><${Icon} n="pin" s=${13} /> ${s.room.name}</span>
      <span class="pill">Recommended: ${cap(s.level)}${myLevel && s.level !== myLevel ? ` · you: ${cap(myLevel)}` : ""}</span>
      <span class=${`pill ${s.status === "full" ? "full" : s.seats < 5 ? "amber" : ""}`}>
        ${s.status === "full" ? "Full" : `${s.seats} seats left`} · organizer-reported ${ago(s.statusAt)}</span>
    </div>
    <div class="row small" style="margin-top:10px">
      ${fit ? html`<span class="pill lime"><${Icon} n="sparkle" s=${13} /> Matches your goal: ${fit.name}</span>` : html`<span class="muted">Not linked to your goals</span>`}
      ${s.requires.length > 0 && html`<span class="muted">Technical setup:</span><${ReadyPill} r=${s.readiness} />`}
      <button class="linkish" style="margin-left:auto" onClick=${onToggle}>${open ? "Hide details" : "Prerequisites & materials"}</button>
    </div>
    ${open && html`<div class="evidence fade">
      ${!detail ? html`<span class="spinner"></span>` : html`<div class="grid2">
        <div><b class="small">What you'll leave with</b><ul style="margin:6px 0;padding-left:18px">${detail.outcomes.map((o) => html`<li>${o}</li>`)}</ul>
          <b class="small">Materials</b><ul style="margin:6px 0;padding-left:18px">${detail.materials.map((o) => html`<li>${o}</li>`)}</ul></div>
        <div><b class="small">Technical prerequisites</b>
          ${detail.checks.length === 0 ? html`<p class="muted small">None. Just bring yourself.</p>` : html`<ul style="margin:6px 0;padding-left:18px">
            ${detail.checks.map((c) => html`<li>${c.name} <span class="muted small">— ${c.detail}</span></li>`)}</ul>`}
          <b class="small">Recommended experience</b><p class="small" style="margin:6px 0">${cap(detail.level)}. ${detail.summary}</p>
          ${detail.checks.length > 0 && html`<a class="btn sm" href="#/attendee/ready">Get ready</a>`}</div>
      </div>`}
    </div>`}
  </div>`;
}

// ================================================================ Get Ready

const LABEL = (c, r) => {
  if (!r) return ["Not checked", ""];
  if (r.status === "pass" && r.verified) return ["Ready", "ready"];
  if (r.status === "pass") return ["Unverified", "amber"];
  if (r.errorCode === "blocked_by_previous") return ["Waiting on earlier check", ""];
  if (c.kind === "deps") return ["Needs installation", "action"];
  if (r.errorCode === "docker_not_running") return ["Start Docker", "action"];
  if (c.kind === "tool") return [r.errorCode === "tool_too_old" ? "Needs update" : "Needs install", "action"];
  if (r.errorCode === "not_signed_in" || r.errorCode === "auth_rejected") return ["Needs sign-in", "action"];
  if (r.errorCode === "endpoint_retired") return ["Blocked · endpoint retired", "red"];
  return ["Action needed", "action"];
};

export function GetReady({ me }) {
  const [started, setStarted] = useState(false);
  const [tab, setTab] = useState("claude");
  const prev = useRef({});
  const lastAt = useRef(null);
  const latest = me ? Math.max(0, ...me.needed.map((id) => me.results[id]?.at || 0)) : 0;
  useEffect(() => {
    if (lastAt.current !== null && latest > lastAt.current) toast({ title: "Report received from your laptop", body: "Checklist updated from check.py results." });
    if (me) lastAt.current = latest;
  }, [latest]);
  if (!me) return html`<${Skeleton} />`;
  const origin = location.origin;
  const token = me.attendee.token;
  const checks = me.checks.filter((c) => me.needed.includes(c.id)).sort((a, b) => (a.order ?? 99) - (b.order ?? 99));
  const allReady = checks.length > 0 && checks.every((c) => me.results[c.id]?.status === "pass" && me.results[c.id]?.verified);
  const flash = {};
  for (const c of checks) {
    const key = `${me.results[c.id]?.status}-${me.results[c.id]?.at}`;
    if (prev.current[c.id] && prev.current[c.id] !== key) flash[c.id] = true;
    prev.current[c.id] = key;
  }
  const sessionsFor = (cid) => me.plan.filter((s) => s.requires.includes(cid) && s.end > serverNow() && s.status !== "full").map((s) => s.title);
  const cmds = {
    claude: `mkdir unstuck-workshop && cd unstuck-workshop
mkdir -p .claude/skills/unstuck-setup
curl -fsSL ${origin}/skill/SKILL.md -o .claude/skills/unstuck-setup/SKILL.md
claude "Use the unstuck-setup skill. SERVER=${origin} TOKEN=${token}"`,
    codex: `mkdir unstuck-workshop && cd unstuck-workshop
curl -fsSL ${origin}/skill/SKILL.md -o AGENTS.md
codex "Follow AGENTS.md to prepare this laptop. SERVER=${origin} TOKEN=${token}"`,
    manual: `curl -fsSL ${origin}/skill/check.py -o check.py
python check.py --server ${origin} --token ${token} --setup
python check.py --server ${origin} --token ${token} --install
python check.py --server ${origin} --token ${token} --send`,
  };

  return html`
    <${Header} eyebrow="Get ready" title="Set up once. Verified for real."
      lede="An organizer-approved setup skill prepares your laptop with your own Claude Code or Codex. Only the check results count. An agent saying it's done doesn't."
      right=${html`<span class=${`pill ${allReady ? "ready" : "amber"}`}>${checks.filter((c) => me.results[c.id]?.status === "pass" && me.results[c.id]?.verified).length} of ${checks.length} verified</span>`} />

    ${allReady && html`<div class="success-banner" style="margin-bottom:18px">
      <span class="check-ic pass" style="width:40px;height:40px"><svg class="tick" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5 10 17 19 7" /></svg></span>
      <div><b>Your environment passed this workshop's checks.</b><div class="small">Verified from check.py results${me.results.service?.verified ? " and the workshop API's own sign-in log" : ""}.</div></div>
    </div>`}

    <div class="checklist rise" style="--i:1">
      ${checks.map((c) => {
        const r = me.results[c.id];
        const [label, cls] = LABEL(c, r);
        const failing = r && r.status === "fail" && r.errorCode !== "blocked_by_previous";
        return html`<div class=${`check-row ${flash[c.id] ? "flash" : ""}`} key=${c.id}>
          <span class=${`check-ic ${r?.status === "pass" && r.verified ? "pass" : failing ? "fail" : ""}`}>
            ${r?.status === "pass" && r.verified ? html`<svg class="tick" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12.5 10 17 19 7" /></svg>`
              : failing ? html`<${Icon} n="alert" s=${16} />` : html`<span style="width:8px;height:8px;border-radius:50%;background:#c9c6b9"></span>`}</span>
          <div style="min-width:0">
            <b>${c.name}</b> <span class="muted small">· ${c.detail}</span>
            ${r?.detail && html`<div class=${failing ? "err" : "muted small"} style="margin-top:5px">${r.detail}</div>`}
            <div class="muted small" style="margin-top:4px">For ${sessionsFor(c.id).join(", ") || "your sessions"}${r ? ` · checked ${ago(r.at)} via ${r.source === "simulated" ? "simulated report" : r.source === "report" ? "help report" : "local skill"}` : ""}</div>
          </div>
          <div class="row" style="justify-content:flex-end">
            <span class=${`pill ${cls}`}>${label}</span>
            ${failing && html`<a class="btn sm" href=${`#/attendee/help?check=${c.id}&error=${encodeURIComponent(r.detail || "")}`}>Request help</a>`}
          </div>
        </div>`;
      })}
    </div>

    <div class="section">
      ${!started ? html`<div class="row rise" style="--i:2">
          <button class="btn primary" onClick=${() => setStarted(true)}><${Icon} n="terminal" s=${17} /> Start guided setup</button>
          <button class="btn" onClick=${() => setStarted(true)}>Open setup instructions</button>
        </div>`
      : html`<div class="card fade">
          <div class="between"><h2 style="margin:0">Run the setup skill on your laptop</h2><span class="pill">${checks.length} checks for your week · organizer-approved</span></div>
          <div class="row" style="margin:16px 0 12px">
            ${[["claude", "Claude Code"], ["codex", "Codex"], ["manual", "Without an agent"]].map(([k, l]) => html`
              <button class=${`chip ${tab === k ? "on" : ""}`} onClick=${() => setTab(k)}>${l}</button>`)}
          </div>
          <${Copy} text=${cmds[tab]} />
          <p class="small muted" style="margin:12px 0 0">The skill installs what's missing, runs <code>check.py</code>, shows you the results and asks before sending anything.
            Only check ids, pass/fail, short errors, OS, Python version and the endpoint path are reported. No keys or files.</p>
          <div class="soft waiting" style="margin-top:16px"><span class="radar"></span> Waiting for your laptop's report. This page updates by itself.</div>
        </div>`}
      <p class="small muted" style="margin-top:14px">Service access is double-checked against the workshop API's own sign-in log.
        <button class="linkish" style="margin-left:6px" onClick=${() => api("/api/simulate-report", { aid: AID })}>Use simulated report (demo backup)</button></p>
    </div>`;
}

// ================================================================ Help / Session companion

export function Help({ me, query }) {
  const session = me && (me.current || me.plan.find((s) => s.end > Date.now() && s.status !== "full" && s.status !== "cancelled" && s.requires.length));
  const [detail] = useData(session ? `/api/session/${session.id}` : null);
  const [step, setStep] = useState(null);
  const [form, setForm] = useState(!!query.check);
  const [error, setError] = useState(query.error || "");
  const [checkId, setCheckId] = useState(query.check || "");
  const [result, setResult] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (query.check) { setForm(true); setCheckId(query.check); setError(query.error || ""); } }, [query.check, query.error]);
  useEffect(() => {
    if (!detail) return;
    let saved = null;
    try { saved = localStorage.getItem(`unstuck-step-${detail.id}`); } catch (e) { /* storage blocked */ }
    setStep(saved || detail.steps[Math.min(2, detail.steps.length - 1)]?.id);
  }, [detail?.id]);
  if (!me) return html`<${Skeleton} />`;
  const pick = (id) => { setStep(id); try { localStorage.setItem(`unstuck-step-${detail.id}`, id); } catch (e) { /* ignore */ } };
  const submit = async () => {
    setBusy(true);
    const r = await api("/api/help", { aid: AID, sessionId: session?.id, stepId: step, checkId: checkId || null, error });
    setResult(r); setBusy(false); setForm(false);
  };
  const stepObj = detail?.steps.find((s) => s.id === step);

  return html`
    <${Header} eyebrow=${session?.live ? "Session companion · live" : "Session companion"} title=${session ? session.title : "Help"}
      lede=${session ? `${session.room.name} · ${fmtWhen(session.start)}–${fmtTime(session.end)} · ${session.speaker}` : "No hands-on session in your plan right now."} />
    ${session && html`<div class="grid2" style="align-items:start">
      <div class="card rise" style="--i:1">
        <h2>Exercise steps</h2>
        <p class="muted small" style="margin-top:-8px">Tap the step you're on. It helps the instructor see where people get stuck.</p>
        ${!detail ? html`<${Skeleton} n=${2} />` : html`<div class="steps">${detail.steps.map((st) => html`
          <div class=${`step-row ${st.id === step ? "on" : ""}`} onClick=${() => pick(st.id)}>
            <span class="step-num">${st.n}</span><span style="flex:1">${st.title}</span>${st.id === step && html`<span class="pill lime">You're here</span>`}</div>`)}</div>
          <h3 style="margin:18px 0 6px">Resources</h3>
          <ul style="margin:0;padding-left:18px" class="small">${detail.materials.map((m) => html`<li>${m}</li>`)}</ul>`}
      </div>

      <div>
        ${!form && !result && html`<div class="card rise" style="--i:2;text-align:center;padding:30px 24px">
          <div style="width:56px;height:56px;border-radius:16px;background:var(--lime);display:grid;place-items:center;margin:0 auto 14px;animation:float 4s ease-in-out infinite"><${Icon} n="message" s=${26} /></div>
          <h2 style="margin-bottom:6px">I'm stuck</h2>
          <p class="muted small" style="margin:0 0 16px">On step ${stepObj?.n || "—"}: ${stepObj?.title || ""}. Help focuses on what's blocking you. It won't do the exercise for you.</p>
          <button class="btn lime" onClick=${() => setForm(true)}>Get help with this step</button>
        </div>`}

        ${form && html`<div class="card fade">
          <h2>What's blocking you?</h2>
          <label class="field" style="margin-top:4px">Step</label>
          <select class="input" value=${step} onChange=${(e) => pick(e.target.value)}>${detail?.steps.map((st) => html`<option value=${st.id}>${st.n}. ${st.title}</option>`)}</select>
          <label class="field">Which part fails? <span class="muted small">(optional)</span></label>
          <select class="input" value=${checkId} onChange=${(e) => setCheckId(e.target.value)}><option value="">Not sure</option>
            ${me.checks.map((c) => html`<option value=${c.id}>${c.name}</option>`)}</select>
          <label class="field">Error message <span class="muted small">(optional)</span></label>
          <textarea class="input mono" rows="4" placeholder="Paste the error you see" value=${error} onInput=${(e) => setError(e.target.value)}></textarea>
          <div class="row" style="margin-top:16px">
            <button class="btn primary" disabled=${busy} onClick=${submit}>${busy ? html`<span class="spinner" style="border-top-color:#fff"></span>` : null} Get help with this step</button>
            <button class="btn ghost" onClick=${() => setForm(false)}>Cancel</button>
          </div>
        </div>`}

        ${result && html`<div class="card fade">
          <div class="between"><span class="pill amber">Reported · ${result.agent === "rules" ? "triaged" : `triaged by ${result.agent}`}</span>
            <button class="btn ghost sm" onClick=${() => setResult(null)}>New report</button></div>
          <h2 style="margin-top:12px">${result.summary}</h2>
          <b class="small">Try these approved steps</b>
          <ol style="padding-left:20px;margin:8px 0 16px">${result.steps.map((s, i) => html`<li class="rise" style=${`--i:${i}`}>${s}</li>`)}</ol>
          <div class="row">
            <a class="btn lime sm" href="#/attendee/ready"><${Icon} n="refresh" s=${15} /> Run check again</a>
            <button class="btn sm" onClick=${() => { api(`/api/help/${result.id}/escalate`); toast({ title: "Helper requested", body: "An organizer can see your report and step." }); }}>Still blocked: request a helper</button>
          </div>
        </div>`}
      </div>
    </div>`}

    ${me.reports.length > 0 && html`<div class="section"><h2>Your reports</h2>
      ${me.reports.map((r, i) => html`<${ReportRow} key=${r.report.id} r=${r} i=${i} />`)}</div>`}`;
}

function ReportRow({ r, i }) {
  const st = r.report.status;
  const pill = {
    open: html`<span class="pill amber">Open${r.report.helper ? ` · ${r.report.helper} assigned` : ""}</span>`,
    fix_sent: html`<span class="pill lime">Fix published</span>`,
    resolved_verified: html`<span class="pill ready"><${Icon} n="check" s=${13} w=${2.6} /> Verified by check</span>`,
    resolved_self: html`<span class="pill">You marked this resolved · not verified</span>`,
  }[st];
  return html`<div class="card rise" style=${`--i:${i}`}>
    <div class="between"><div><b>${r.checkName}</b>${r.step && html`<span class="muted small"> · ${r.step}</span>`}</div>${pill}</div>
    ${r.report.error && html`<div class="err" style="margin-top:10px">${r.report.error}</div>`}
    ${r.fix && st !== "resolved_verified" && html`<div class="soft" style="margin-top:12px"><b>Organizer fix:</b> ${r.fix.text}</div>`}
    ${(st === "open" || st === "fix_sent") && html`<div class="row" style="margin-top:12px">
      <a class="btn sm lime" href="#/attendee/ready"><${Icon} n="refresh" s=${15} /> Run check again</a>
      <button class="btn sm" onClick=${() => api(`/api/help/${r.report.id}/confirm`)}>I understand now, confirm resolved</button>
    </div>`}
  </div>`;
}

// ================================================================ Plan Rescue

export function Rescue({ sid, me, onClose }) {
  const [data] = useData(`/api/rescue?sid=${sid}&aid=${AID}`);
  const [why, setWhy] = useState(null);
  const [confirm, setConfirm] = useState(null);
  const [done, setDone] = useState(null);
  const orig = me?.plan.find((s) => s.id === sid) || data?.original?.s;
  const switchTo = async (o) => {
    await api("/api/switch", { aid: AID, from: sid, to: o.session.id });
    setDone(o); setConfirm(null);
  };
  return html`<${Drawer} onClose=${onClose}>
    <p class="eyebrow">Plan rescue</p>
    ${!data || !orig ? html`<${Skeleton} />` : done ? html`<div class="fade">
      <h1 class="title" style="font-size:34px">You're in “${done.session.title}”.</h1>
      <p class="lede">${done.room.name} · starts ${rel(done.session.start)} · ${done.walk}-min walk from ${done.from}.</p>
      ${done.missing.length ? html`<div class="card" style="margin-top:20px">
          <b>One more setup step: ${done.missingNames.join(", ")}.</b>
          <p class="muted small">The setup skill can prepare it. Run it again from Get Ready.</p>
          <a class="btn lime" href="#/attendee/ready" onClick=${onClose}><${Icon} n="wrench" s=${16} /> Get ready</a></div>`
        : html`<div class="success-banner" style="margin-top:20px"><b>Your setup already passes this session's checks.</b></div>`}
      <button class="btn" style="margin-top:16px" onClick=${onClose}>Back to my day</button>
    </div>` : html`
      <h1 class="title" style="font-size:32px;padding-right:40px">“${orig.title}” is ${orig.status === "cancelled" ? "cancelled" : "full"}.</h1>
      <p class="lede">Updated by the organizer ${ago(orig.statusAt)}. Here are the alternatives that still fit your goal, your setup and your route.</p>
      <div class="section" style="margin-top:22px">
        ${data.options.length === 0 && html`<div class="card"><b>No suitable alternative right now.</b>
          <p class="muted small">Nothing else covering your goal fits your time and route. The session materials are still available, and an organizer can help.</p>
          <div class="row"><a class="btn sm" href=${`#/attendee/sessions?open=${sid}`}>View materials</a><a class="btn sm" href="#/attendee/help">Ask an organizer</a></div></div>`}
        ${data.options.map((o, i) => {
          const passed = o.requires.length - o.missing.length;
          const setup = o.requires.length === 0 ? "no setup is needed"
            : o.missing.length === 0 ? "your setup passes its checks" : `your setup passes ${passed} of ${o.requires.length} checks`;
          return html`<div class=${`card opt rise ${i === 0 ? "best" : ""}`} style=${`--i:${i};margin-top:${i ? 18 : 6}px`} key=${o.session.id}>
            ${i === 0 && html`<span class="pill lime rank">Best fit</span>`}
            <div class="between" style="align-items:flex-start"><h3 style="font-size:18px">${o.session.title}</h3>
              <span class="row" style="gap:6px">${o.encore ? html`<span class="pill lime">Encore</span>` : o.later ? html`<span class="pill">Later this week</span>` : null}<span class="pill">${cap(o.session.format)}</span></span></div>
            <p style="margin:8px 0 0">This session covers <b>${o.goal.short}</b>, ${setup}, and it starts <b>${rel(o.session.start)}</b>${o.walk <= 4 ? " nearby" : ""}.</p>
            <div class="facts">
              <div class="fact"><span class="muted">Starts</span><b>${fmtWhen(o.session.start)}</b>${rel(o.session.start)}</div>
              <div class="fact"><span class="muted">Where</span><b>${o.room.name}</b>${o.walk}-min walk${o.stepFree ? " · step-free" : ""}</div>
              <div class="fact"><span class="muted">Seats</span><b>${o.seats} left</b>organizer, ${ago(o.session.statusAt)}</div>
            </div>
            <div class="row small">
              <span class=${`pill ${o.levelFit ? "green" : "amber"}`}>Recommended: ${cap(o.session.level)}${o.levelFit ? " · matches you" : ` · you: ${cap(me.attendee.level)}`}</span>
              ${o.missing.length ? html`<span class="pill amber">Setup needed: ${o.missingNames.join(", ")}</span>` : o.requires.length ? html`<span class="pill ready">Setup ready</span>` : null}
            </div>
            ${why === o.session.id && html`<div class="path">${o.path.map((p, k) => html`<span class=${p.kind === "edge" ? "edge" : `node ${p.kind}`} style=${`--i:${k}`}>${p.label}</span>`)}</div>
              <p class="muted small" style="margin:10px 0 0">Found by following your goal through the conference graph: sessions that cover it, their rooms and walking times, and the checks they require joined with your verified results.</p>`}
            <div class="row" style="margin-top:14px">
              ${confirm === o.session.id
                ? html`<span class="small">Leave “${orig.title}” and switch?</span><button class="btn sm primary" onClick=${() => switchTo(o)}>Confirm switch</button><button class="btn sm ghost" onClick=${() => setConfirm(null)}>Cancel</button>`
                : html`<button class=${`btn sm ${i === 0 ? "primary" : ""}`} onClick=${() => setConfirm(o.session.id)}>Switch to this session</button>
                  <button class="btn sm ghost" onClick=${() => setWhy(why === o.session.id ? null : o.session.id)}><${Icon} n="graph" s=${15} /> Why this?</button>`}
            </div>
          </div>`;
        })}
        ${data.rejected.length > 0 && html`<div class="soft" style="margin-top:18px"><b class="small">Also considered</b>
          ${data.rejected.map((r) => html`<div class="small" style="margin-top:4px">${r.title}: <span class="muted">${r.reason}</span></div>`)}</div>`}
      </div>`}
  <//>`;
}
