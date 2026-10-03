import { useEffect, useState } from "react";
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
export const Count = ({ to }) => Math.round(useCount(to));
export const riskColor = (s) => (s < 34 ? "var(--ok)" : s < 67 ? "var(--warn)" : "var(--bad)");
const TONE = { Mild: "ok", Moderate: "warn", Severe: "bad", HIGH: "ok", MEDIUM: "warn", LOW: "bad", Healthy: "ok", Monitor: "warn", Critical: "bad" };
export const Badge = ({ children }) => <span className={`badge ${TONE[children] || ""}`}>{children}</span>;

const TREND = {
  WORSENING: ["▲ Worsening", "bad"], STABLE: ["■ Stable", "warn"], IMPROVING: ["▼ Improving", "ok"],
  FIRST_INSPECTION: ["First inspection", ""], INSUFFICIENT_HISTORY: ["Not enough history", ""],
};
export const Trend = ({ value }) => { const [t, c] = TREND[value] || [value, ""]; return <span className={`badge ${c}`}>{t}</span>; };

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
export const fmt = (d) => (d ? new Date(d).toLocaleString("en-IN", { dateStyle: "medium", timeStyle: "short" }) : "-");
