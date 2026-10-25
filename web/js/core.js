import { html, useEffect, useRef, useState } from "../vendor/preact-htm.js";

export { html };

// ---------------------------------------------------------------- api

export const AID = "a-demo";

export async function api(path, body) {
  const r = await fetch(path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${r.status} ${await r.text()}`);
  return r.json();
}

// A change counter from the server; every view refetches when it moves.
let version = -1;
let clockOffset = 0;
const listeners = new Set();
export function onChange(fn) { listeners.add(fn); return () => listeners.delete(fn); }
export function bumpLocal() { listeners.forEach((f) => f(version)); }
async function poll() {
  try {
    const r = await api("/api/version");
    clockOffset = r.now - Date.now();
    if (r.v !== version) { version = r.v; listeners.forEach((f) => f(version)); }
  } catch (e) { /* server restarting; try again */ }
  setTimeout(poll, 1500);
}
poll();
export const serverNow = () => Date.now() + clockOffset;

export function useVersion() {
  const [v, setV] = useState(version);
  useEffect(() => onChange(setV), []);
  return v;
}

export function useData(path, deps = []) {
  const v = useVersion();
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    let live = true;
    if (!path) return;
    api(path).then((d) => live && (setData(d), setError(null))).catch((e) => live && setError(e));
    return () => { live = false; };
  }, [path, v, ...deps]);
  return [data, error];
}

export function useNow(ms = 15000) {
  const [, set] = useState(0);
  useEffect(() => { const t = setInterval(() => set((x) => x + 1), ms); return () => clearInterval(t); }, [ms]);
  return serverNow();
}

// ---------------------------------------------------------------- formatting

// Everything is shown in venue time (San Francisco), wherever the viewer is.
export const TZ = "America/Los_Angeles";
const F = {
  time: new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", minute: "2-digit" }),
  day: new Intl.DateTimeFormat("en-US", { timeZone: TZ, weekday: "short", month: "short", day: "numeric" }),
  key: new Intl.DateTimeFormat("en-CA", { timeZone: TZ }),
  hour: new Intl.DateTimeFormat("en-US", { timeZone: TZ, hour: "numeric", hourCycle: "h23" }),
};
export const fmtTime = (ms) => F.time.format(ms);
export const fmtDay = (ms) => F.day.format(ms);
export const dayKey = (ms) => F.key.format(ms);
export const localHour = (ms) => Number(F.hour.format(ms)) % 24;
const dayDiff = (a, b) => Math.round((Date.parse(dayKey(a)) - Date.parse(dayKey(b))) / 864e5);
export const fmtWhen = (ms) => `${fmtDay(ms)} · ${fmtTime(ms)}`;
export const overlaps = (a, b) => a.id !== b.id && a.start < b.end && b.start < a.end;

// "Today", "Tomorrow" or "Tue, Oct 27" for conference day i.
export function dayName(c, i) {
  const key = c?.dayKeys?.[i];
  if (!key) return `Day ${i + 1}`;
  const d = Math.round((Date.parse(key) - Date.parse(dayKey(serverNow()))) / 864e5);
  return d === 0 ? `Today · ${c.days[i]}` : d === 1 ? `Tomorrow · ${c.days[i]}` : c.days[i];
}

export function DayTabs({ c, value, onChange, counts }) {
  return html`<div class="chips day-tabs" role="tablist" aria-label="Conference day">${(c?.days || []).map((_, i) => html`
    <button role="tab" aria-selected=${value === i} class=${`chip ${value === i ? "on" : ""}`} onClick=${() => onChange(i)}>
      ${dayName(c, i)}${counts && html` <span class="small" style="opacity:.65">· ${counts[i] || 0}</span>`}</button>`)}</div>`;
}

export function rel(ms, now = serverNow()) {
  const d = dayDiff(ms, now);
  if (d !== 0 && Math.abs(ms - now) >= 6 * 3600e3) {
    return d === 1 ? "tomorrow" : d === -1 ? "yesterday" : d > 0 ? `in ${d} days` : `${-d} days ago`;
  }
  const m = Math.round((ms - now) / 60000);
  if (m === 0) return "now";
  if (m > 0) return m >= 60 ? `in ${Math.floor(m / 60)} h ${m % 60} min` : `in ${m} min`;
  const a = -m;
  return a >= 60 ? `${Math.floor(a / 60)} h ago` : `${a} min ago`;
}
export const ago = (ms) => {
  const m = Math.max(0, Math.round((serverNow() - ms) / 60000));
  return m === 0 ? "just now" : m < 60 ? `${m} min ago` : m < 1440 ? `${Math.floor(m / 60)} h ago` : `${Math.floor(m / 1440)} d ago`;
};
export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);

// ---------------------------------------------------------------- icons

const P = {
  home: "M3 10.5 12 3l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z",
  calendar: "M4 6h16v14H4zM4 10h16M8 3v4M16 3v4M8 14h2M14 14h2M8 17h2",
  check: "M5 12.5 10 17 19 7",
  checkCircle: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM8 12.2l2.7 2.7L16.2 9.4",
  message: "M4 5h16v11H9l-5 4zM8 9h8M8 12.5h5",
  sparkle: "M12 3l1.8 5.4L19 10l-5.2 1.6L12 17l-1.8-5.4L5 10l5.2-1.6z",
  bell: "M6 16V11a6 6 0 1 1 12 0v5l1.5 2h-15zM10 20.5a2 2 0 0 0 4 0",
  arrow: "M5 12h14M13 6l6 6-6 6",
  pin: "M12 21s-6.5-5.6-6.5-11a6.5 6.5 0 1 1 13 0C18.5 15.4 12 21 12 21zM12 12.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z",
  clock: "M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 2",
  walk: "M13 4.5a1.5 1.5 0 1 0 0-3 1.5 1.5 0 0 0 0 3zM10 21l2-6 3 3v3M9 11l3-3 3 2 2 3M12 8l-1 6",
  alert: "M12 3 2 20h20zM12 10v4M12 17h.01",
  refresh: "M20 11a8 8 0 0 0-14.6-4.5L4 8M4 4v4h4M4 13a8 8 0 0 0 14.6 4.5L20 16M20 20v-4h-4",
  layers: "M12 3 2 8l10 5 10-5zM2 13l10 5 10-5",
  x: "M6 6l12 12M18 6 6 18",
  search: "M11 18a7 7 0 1 0 0-14 7 7 0 0 0 0 14zM20 20l-4-4",
  wrench: "M14.5 6.5a4 4 0 0 0 5 5L12 19a2.1 2.1 0 0 1-3-3l7.5-7.5zM14.5 6.5 17 4",
  users: "M9 11a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7zM2.5 20a6.5 6.5 0 0 1 13 0M16 4.3a3.5 3.5 0 0 1 0 6.4M21.5 20a6.5 6.5 0 0 0-4-6",
  zap: "M13 2 4 14h7l-1 8 9-12h-7z",
  chevron: "M9 6l6 6-6 6",
  copy: "M8 8h12v12H8zM4 16V4h12",
  terminal: "M4 5h16v14H4zM7 9l3 3-3 3M12 15h5",
  shield: "M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z",
  graph: "M6 6a2 2 0 1 0 0-.01M18 6a2 2 0 1 0 0-.01M12 18a2 2 0 1 0 0-.01M7.5 7.5l3.5 9M16.5 7.5l-3.5 9M8 6h8",
  plus: "M12 5v14M5 12h14",
  door: "M6 21V4h10v17M16 21h3M13 12h.01",
  route: "M6 19a2 2 0 1 0 0-.01M18 5a2 2 0 1 0 0-.01M6 17V9a3 3 0 0 1 3-3h4M18 7v8a3 3 0 0 1-3 3h-4",
};

export function Icon({ n, s = 20, w = 1.8, cls = "" }) {
  return html`<svg class=${cls} width=${s} height=${s} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width=${w} stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d=${P[n]} /></svg>`;
}

export function LogoMark({ s = 38 }) {
  return html`<span class="logo-mark" style=${`width:${s}px;height:${s}px`}>
    <svg width=${s * 0.6} height=${s * 0.6} viewBox="0 0 24 24" fill="none" stroke="#1d221f" stroke-width="2.6" stroke-linecap="round">
      <path d="M5 7h10a3.5 3.5 0 0 1 0 7H9a3.5 3.5 0 0 0 0 7h10" /><circle cx="5" cy="7" r="1.6" fill="#1d221f" /><circle cx="19" cy="21" r="1.6" fill="#1d221f" />
    </svg></span>`;
}

// ---------------------------------------------------------------- atoms

const STATUS = {
  open: ["Open", ""], full: ["Full", "full"], moved: ["Moved", "moved"], cancelled: ["Cancelled", "cancelled"],
};
export function SessionStatus({ s }) {
  if (s.live && s.status !== "cancelled") return html`<span class="pill live lime">Live now</span>`;
  const [label, cls] = STATUS[s.status] || [s.status, ""];
  return s.status === "open" ? null : html`<span class=${`pill ${cls}`}>${label}</span>`;
}

export function ReadyPill({ r }) {
  if (!r || !r.total) return null;
  return r.ready
    ? html`<span class="pill ready"><${Icon} n="check" s=${13} w=${2.6} /> Ready</span>`
    : html`<span class="pill action">Action needed · ${r.passed}/${r.total}</span>`;
}

export function Skeleton({ n = 3 }) {
  return html`${Array.from({ length: n }, (_, i) => html`<div class="skeleton" style=${`--i:${i};opacity:${1 - i * 0.2}`}></div>`)}`;
}

export function Header({ eyebrow, title, lede, right }) {
  return html`<div class="head rise">
    <div><p class="eyebrow">${eyebrow}</p><h1 class="title">${title}</h1>${lede && html`<p class="lede">${lede}</p>`}</div>
    ${right && html`<div>${right}</div>`}
  </div>`;
}

export function CountUp({ value }) {
  const [shown, setShown] = useState(value);
  const prev = useRef(value);
  useEffect(() => {
    const from = prev.current, to = value; prev.current = value;
    if (from === to) return;
    const t0 = performance.now();
    let raf;
    const step = (t) => {
      const k = Math.min(1, (t - t0) / 600);
      setShown(Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3))));
      if (k < 1) raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return html`${shown}`;
}

export function Copy({ text }) {
  const [done, setDone] = useState(false);
  return html`<div class="cmd"><pre>${text}</pre><button onClick=${() => {
    navigator.clipboard?.writeText(text); setDone(true); setTimeout(() => setDone(false), 1400);
  }}>${done ? "Copied" : "Copy"}</button></div>`;
}

// ---------------------------------------------------------------- toasts

let pushToast = () => {};
export const toast = (t) => pushToast(t);
export function Toasts() {
  const [items, setItems] = useState([]);
  pushToast = (t) => {
    const id = Math.random();
    setItems((xs) => [...xs, { ...t, id }]);
    setTimeout(() => setItems((xs) => xs.filter((x) => x.id !== id)), t.ms || 6000);
  };
  return html`<div class="toasts" aria-live="polite">${items.map((t) => html`
    <div class=${`toast ${t.kind || ""}`} key=${t.id} onClick=${() => { t.onClick?.(); setItems((xs) => xs.filter((x) => x.id !== t.id)); }}>
      <span class="tdot"></span><div><b>${t.title}</b>${t.body && html`<small>${t.body}</small>`}</div>
    </div>`)}</div>`;
}

export function Drawer({ onClose, children }) {
  useEffect(() => {
    const k = (e) => e.key === "Escape" && onClose();
    addEventListener("keydown", k); return () => removeEventListener("keydown", k);
  }, []);
  return html`<div class="backdrop" onClick=${onClose}></div>
    <aside class="drawer" role="dialog" aria-modal="true">
      <button class="btn ghost x" onClick=${onClose} aria-label="Close"><${Icon} n="x" /></button>${children}</aside>`;
}

export function Modal({ onClose, children }) {
  return html`<div class="backdrop" onClick=${onClose}></div>
    <div class="modal" role="dialog" aria-modal="true">
      <button class="btn ghost x" onClick=${onClose} aria-label="Close"><${Icon} n="x" /></button>${children}</div>`;
}
