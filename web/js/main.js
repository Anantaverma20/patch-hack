import { render, useEffect, useLayoutEffect, useRef, useState } from "../vendor/preact-htm.js";
import { AID, Icon, LogoMark, Toasts, api, html, toast, useData } from "./core.js";
import { GetReady, Help, Join, MyDay, Rescue, Sessions } from "./attendee.js";
import { HelpQueue, OrgSessions, Overview, Readiness } from "./organizer.js";
import { Copilot } from "./copilot.js";

const NAV = {
  attendee: [["myday", "My Day", "home"], ["sessions", "Sessions", "calendar"], ["ready", "Get Ready", "checkCircle"], ["help", "Help", "message"]],
  organizer: [["overview", "Overview", "home"], ["sessions", "Sessions", "calendar"], ["readiness", "Readiness", "checkCircle"], ["help", "Help queue", "message"]],
};

function parseHash() {
  const [path, qs] = (location.hash.replace(/^#\/?/, "") || "attendee/myday").split("?");
  const [role, page] = path.split("/");
  return { role: role === "organizer" ? "organizer" : "attendee", page: page || "", query: Object.fromEntries(new URLSearchParams(qs || "")) };
}

function RoleSwitch({ role }) {
  const refs = { attendee: useRef(), organizer: useRef() };
  const [thumb, setThumb] = useState(null);
  useLayoutEffect(() => {
    const el = refs[role].current;
    if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth });
  }, [role]);
  return html`<div class="seg" role="tablist" aria-label="View as">
    ${thumb && html`<span class="thumb" style=${`left:${thumb.left}px;width:${thumb.width}px`}></span>`}
    <button ref=${refs.attendee} class=${role === "attendee" ? "on" : ""} onClick=${() => (location.hash = "#/attendee/myday")}>Attendee</button>
    <button ref=${refs.organizer} class=${role === "organizer" ? "on" : ""} onClick=${() => (location.hash = "#/organizer/help")}>Organizer</button>
  </div>`;
}

function App() {
  const [route, setRoute] = useState(parseHash());
  const [rescue, setRescue] = useState(null);
  const [ring, setRing] = useState(false);
  useEffect(() => {
    const f = () => { setRoute(parseHash()); setRescue(null); window.scrollTo({ top: 0, behavior: "smooth" }); };
    addEventListener("hashchange", f); return () => removeEventListener("hashchange", f);
  }, []);
  const [conf] = useData("/api/conference");
  const [me] = useData(`/api/me?aid=${AID}`);
  const [org] = useData("/api/org/help");
  const { role, query } = route;
  let page = route.page;

  // Live alerts: toast + bell when something new needs the viewer's attention.
  const seen = useRef(null);
  useEffect(() => {
    if (!me) return;
    const ids = me.attention.filter((a) => a.urgent).map((a) => a.id);
    if (seen.current) {
      for (const a of me.attention.filter((x) => x.urgent && !seen.current.includes(x.id))) {
        if (role === "attendee") {
          toast({ title: a.kind === "fix" ? "A fix was published for your blocker" : "Your plan changed", body: a.text, kind: "warn",
            onClick: () => (a.sessionId && (a.kind === "full" || a.kind === "cancelled") ? setRescue(a.sessionId) : (location.hash = "#/attendee/ready")) });
        }
        setRing(true); setTimeout(() => setRing(false), 1000);
      }
    }
    seen.current = ids;
  }, [me]);
  const seenReports = useRef(null);
  const openReports = org ? org.clusters.reduce((n, c) => n + c.reports.filter((r) => r.status === "open").length, 0) : 0;
  useEffect(() => {
    if (!org) return;
    if (seenReports.current !== null && openReports > seenReports.current && role === "organizer") {
      toast({ title: "New help report", body: "It was grouped with related reports in the help queue.", onClick: () => (location.hash = "#/organizer/help") });
      setRing(true); setTimeout(() => setRing(false), 1000);
    }
    seenReports.current = openReports;
  }, [openReports]);

  const onboarded = me?.attendee?.onboarded;
  if (role === "attendee" && me && !onboarded) page = "join";
  const nav = NAV[role];
  const current = nav.find(([k]) => k === page) || (page === "join" ? ["join", "Join"] : nav[0]);
  const c = conf?.conference;
  const alertCount = role === "attendee" ? (me?.attention || []).filter((a) => a.urgent).length : openReports;

  let body;
  if (role === "attendee") {
    if (!me || !conf) body = null;
    else if (page === "join") body = html`<${Join} conf=${conf} />`;
    else if (page === "sessions") body = html`<${Sessions} me=${me} conf=${conf} query=${query} />`;
    else if (page === "ready") body = html`<${GetReady} me=${me} />`;
    else if (page === "help") body = html`<${Help} me=${me} query=${query} />`;
    else body = html`<${MyDay} me=${me} conf=${conf} openRescue=${setRescue} />`;
  } else if (conf) {
    if (page === "sessions") body = html`<${OrgSessions} conf=${conf} />`;
    else if (page === "readiness") body = html`<${Readiness} conf=${conf} />`;
    else if (page === "help") body = html`<${HelpQueue} />`;
    else body = html`<${Overview} />`;
  }

  return html`<div class="shell">
    <aside class="side">
      <a class="logo" href="#/attendee/myday"><${LogoMark} /><span class="logo-word">unstuck<i> .</i></span></a>
      <div class="event-card"><span class="event-badge">f</span><div><b>${c?.name || "Future / Forward"}</b><small>${c ? `${c.city} · ${c.dates}` : ""}</small></div></div>
      <div class="side-label">${role === "attendee" ? "YOUR DAY" : "YOUR WORKSPACE"}</div>
      <nav class="nav">${nav.map(([k, label, ic]) => html`<a href=${`#/${role}/${k}`} class=${current[0] === k ? "on" : ""}>
        <${Icon} n=${ic} s=${21} /> ${label}
        ${role === "organizer" && k === "help" && openReports > 0 && html`<span class="count">${openReports}</span>`}
        ${role === "attendee" && k === "myday" && alertCount > 0 && html`<span class="count red">${alertCount}</span>`}</a>`)}</nav>
      <div class="side-promo">
        <${Icon} n="sparkle" s=${22} />
        <b>${role === "attendee" ? "Stuck on a step?" : "A smoother day, together."}</b>
        <p>${role === "attendee" ? "Tell us where. Your instructor sees shared problems, not scattered hands." : "Spot the blockers. Help your attendees get back to learning."}</p>
        <button onClick=${() => (location.hash = role === "attendee" ? "#/attendee/help" : "#/attendee/myday")}>
          ${role === "attendee" ? "Open session companion" : "Meet your companion"} <${Icon} n="arrow" s=${16} /></button>
      </div>
    </aside>

    <main class="main">
      <header class="top">
        <a class="mobile-logo logo" href="#/attendee/myday" style="padding:0"><${LogoMark} s=${32} /></a>
        <div class="crumbs">${c?.name || "Future / Forward"} <${Icon} n="chevron" s=${18} /> <b>${current[1]}</b></div>
        <span class="spacer"></span>
        <span class="demo-tag">INTERACTIVE DEMO</span>
        <${RoleSwitch} role=${role} />
        <button class=${`bell ${ring ? "ring" : ""}`} aria-label=${`${alertCount} alerts`}
          onClick=${() => (location.hash = role === "attendee" ? "#/attendee/myday" : "#/organizer/help")}>
          <${Icon} n="bell" s=${19} />${alertCount > 0 && html`<span class="dot"></span>`}</button>
      </header>
      <div class="content" key=${role + page}>${body}</div>
      <footer class="foot">
        <span><${Icon} n="layers" s=${14} /> Interactive prototype · Fictional conference · Live data in FalkorDB · Setup checks run on your own laptop</span>
        <button onClick=${async () => { await api("/api/reset", {}); setRescue(null); location.hash = "#/attendee/join"; toast({ title: "Demo reset", body: "Fresh conference, schedule starts now." }); }}>
          <${Icon} n="refresh" s=${14} /> Reset demo</button>
      </footer>
    </main>

    ${role === "attendee" && html`<nav class="bottom-nav">${nav.map(([k, label, ic]) => html`
      <a href=${`#/attendee/${k}`} class=${current[0] === k ? "on" : ""}><${Icon} n=${ic} s=${20} />${label}</a>`)}</nav>`}
    ${rescue && html`<${Rescue} sid=${rescue} me=${me} onClose=${() => setRescue(null)} />`}
    <${Copilot} visible=${role === "organizer"} />
    <${Toasts} />
  </div>`;
}

render(html`<${App} />`, document.getElementById("app"));
