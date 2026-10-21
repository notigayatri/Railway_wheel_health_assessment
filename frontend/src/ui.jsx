import { useEffect, useState } from "react";
import { Link } from "react-router-dom";

/* ---------- hooks ---------- */
export function useCount(target, ms = 900) {
  const [n, setN] = useState(0);
  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) { setN(target); return; }
    let raf, t0;
    const step = (t) => { t0 = t0 ?? t; const p = Math.min(1, (t - t0) / ms); setN(target * (1 - Math.pow(1 - p, 3))); if (p < 1) raf = requestAnimationFrame(step); };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, [target, ms]);
  return n;
}
export const Count = ({ to }) => Math.round(useCount(to || 0));

/* load something async; returns [data, error, reload] */
export function useLoad(fn, deps = []) {
  const [data, setData] = useState(null);
  const [err, setErr] = useState("");
  const [tick, setTick] = useState(0);
  useEffect(() => {
    let live = true;
    setErr("");
    fn().then((d) => live && setData(d)).catch((e) => live && setErr(e.message));
    return () => { live = false; };
  }, [...deps, tick]); // eslint-disable-line react-hooks/exhaustive-deps
  return [data, err, () => setTick((t) => t + 1)];
}

/* ---------- risk (thresholds match the backend: Healthy < 50, Monitor 50-79, Critical >= 80) ---------- */
export const riskTone = (s) => (s < 50 ? "ok" : s < 80 ? "warn" : "bad");
export const riskColor = (s) => `var(--${riskTone(s)})`;

/* ---------- text helpers ---------- */
export const human = (s) => (s ? String(s).replace(/_/g, " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : "-");
export const fmt = (d) => (d ? new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "-");
export const fmtWindow = (a, b) => (a ? `${fmt(a)} to ${fmt(b)}` : "-");

/* generic one-line description for list items whose exact shape we do not control */
export function brief(o) {
  if (o == null) return "";
  if (typeof o !== "object") return String(o);
  const pick = (...k) => k.map((x) => o[x]).find((v) => v != null && v !== "");
  const parts = [pick("train_number", "train_name"), pick("wheel_asset_id", "asset_id"), pick("message", "conflict_note", "scheduling_notes", "notes")].filter(Boolean);
  return parts.length ? parts.join(" · ") : Object.values(o).filter((v) => v != null && typeof v !== "object").join(" · ");
}

/* ---------- badges ---------- */
const TONE = {
  Mild: "ok", Moderate: "warn", Severe: "bad", HIGH: "ok", MEDIUM: "warn", LOW: "bad",
  Healthy: "ok", Monitor: "warn", Critical: "bad", Active: "ok", "Under Maintenance": "warn", Decommissioned: "",
};
export const Badge = ({ children }) => <span className={`badge ${TONE[children] || ""}`}>{children}</span>;

const PRIORITY = { CRITICAL: "bad", MODERATE: "warn", LOW: "ok" };
export const Priority = ({ value }) => <span className={`badge ${PRIORITY[value] || ""}`}>{human(value)}</span>;

const JOB = { PENDING: ["Pending review", "warn"], SCHEDULED: ["Scheduled", "ok"], IN_PROGRESS: ["In progress", "warn"], COMPLETED: ["Completed", "ok"], CANCELLED: ["Cancelled", ""] };
export const JobStatus = ({ value }) => { const [t, c] = JOB[value] || [human(value), ""]; return <span className={`badge ${c}`}>{t}</span>; };

export const Sched = ({ value }) => {
  const v = value || "";
  const tone = /CONFLICT|CLEARANCE/i.test(v) ? "bad" : /NO_|NONE|ROUTINE/i.test(v) ? "" : "ok";
  return <span className={`badge ${tone}`}>{human(v)}</span>;
};

const TREND = {
  WORSENING: ["▲ Worsening", "bad"], STABLE: ["■ Stable", "warn"], IMPROVING: ["▼ Improving", "ok"],
  FIRST_INSPECTION: ["First inspection", ""], INSUFFICIENT_HISTORY: ["Not enough history", ""],
};
export const Trend = ({ value }) => { const [t, c] = TREND[value] || [value, ""]; return <span className={`badge ${c}`}>{t}</span>; };

/* ---------- wheels ---------- */
export const neverInspected = (w) => w.inspection_count === 0 || (w.inspection_count == null && !w.latest_inspection);
export const wheelState = (w) => (neverInspected(w) ? ["Not inspected", ""] : [w.status, TONE[w.status] || ""]);
export function WheelChip({ w, to }) {
  const [label, tone] = wheelState(w);
  const body = <><span>{w.wheel_identifier || w.asset_id}</span><small>{label}</small></>;
  return to
    ? <Link className={`chip ${tone}`} to={to} title={`${w.asset_id}. Open in inspection`}>{body}</Link>
    : <span className={`chip ${tone}`} title={w.asset_id}>{body}</span>;
}

/* ---------- gauge and bar ---------- */
export function Gauge({ value: target = 0, size = 240 }) {
  const value = useCount(target, 1200);
  const c = Math.PI * 80, pct = Math.max(0, Math.min(100, value)) / 100;
  const ticks = Array.from({ length: 11 }, (_, i) => {
    const a = Math.PI - (i * Math.PI) / 10;
    return <line key={i} x1={100 + 88 * Math.cos(a)} y1={100 - 88 * Math.sin(a)} x2={100 + 96 * Math.cos(a)} y2={100 - 96 * Math.sin(a)} stroke="var(--steel)" strokeWidth={i % 5 ? 1 : 2} />;
  });
  return (
    <svg viewBox="0 0 200 124" width={size} role="img" aria-label={`Risk score ${Math.round(value)} out of 100`}>
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--line)" strokeWidth="12" />
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke={riskColor(value)} strokeWidth="12" strokeDasharray={`${c * pct} ${c}`} style={{ transition: "stroke-dasharray .8s ease" }} />
      {ticks}
      <text x="100" y="94" textAnchor="middle" className="gauge-num">{Math.round(value)}</text>
      <text x="100" y="116" textAnchor="middle" className="gauge-lbl">risk score out of 100</text>
    </svg>
  );
}
export const Bar = ({ value, max = 1 }) => (
  <span className="bar"><span style={{ width: `${Math.min(100, (value / max) * 100)}%` }} /></span>
);

/* ---------- operational hold notice (recommend-only, never certifies safety) ---------- */
export const Hold = () => (
  <div className="hold">
    <b>Operational hold recommended</b>
    Urgent inspection is required before the next scheduled operation. Authorised engineering staff must assess and clear this wheel. This system only recommends and flags conflicts.
  </div>
);

/* ---------- maintenance plan card (used after an inspection) ---------- */
export function Plan({ rec, busy, err, onGenerate }) {
  if (!rec) {
    return (
      <section className="panel reveal" style={{ "--i": 1 }}>
        <h2>Maintenance plan</h2>
        <p className="muted">Turn this result into a schedule-aware recommendation, using the train's operating runs and maintenance windows.</p>
        {err && <p className="error" style={{ marginBottom: ".8rem" }}>{err}</p>}
        <button className="primary" disabled={busy} onClick={onGenerate}>{busy ? "Planning..." : "Generate maintenance plan"}</button>
      </section>
    );
  }
  const hold = rec.requires_operational_clearance || rec.priority === "CRITICAL";
  return (
    <section className="panel reveal plan">
      <h2>Maintenance plan</h2>
      {hold && <Hold />}
      <div className="meta">
        <div>Priority <Priority value={rec.priority} /></div>
        <div>Scheduling <Sched value={rec.scheduling_status} /></div>
        <div>Suggested window <b>{rec.suggested_start ? fmtWindow(rec.suggested_start, rec.suggested_end) : "Routine, at next depot turnaround"}</b></div>
        <div>Job <b>{rec.maintenance_job_id ? `#${rec.maintenance_job_id}` : "-"}</b>{rec.duplicate_job && <span className="muted small"> (open job already existed)</span>}</div>
      </div>
      {rec.conflict_notes?.length > 0 && <ul className="conf">{rec.conflict_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
      {rec.scheduling_notes && <p className="muted small">{rec.scheduling_notes}</p>}
      <Link className="ghost" to="/planner">Open maintenance planner</Link>
    </section>
  );
}

/* ---------- simulated-data note ---------- */
export const SimNote = () => (
  <p className="simnote">Simulated fleet data. Maintenance dates are rule-based recommendations, not certified railway safety decisions.</p>
);
