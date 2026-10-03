import { useEffect, useState } from "react";
import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { getDashboard } from "../api.js";
import { Badge, Count, fmt } from "../ui.jsx";

const SEV = { Mild: "#4A9B78", Moderate: "#D7A23B", Severe: "#D2625B" };
const toRows = (o = {}) => Object.entries(o).map(([name, value]) => ({ name, value }));

function Chart({ title, data, colors }) {
  return (
    <section className="panel">
      <h2>{title}</h2>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={data} margin={{ left: -20 }}>
          <CartesianGrid vertical={false} stroke="#DDE6E4" />
          <XAxis dataKey="name" tickLine={false} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} />
          <Tooltip cursor={{ fill: "#EAF1EF" }} />
          <RBar dataKey="value" radius={[2, 2, 0, 0]}>
            {data.map((d) => <Cell key={d.name} fill={colors?.[d.name] || "#2F7F79"} />)}
          </RBar>
        </BarChart>
      </ResponsiveContainer>
    </section>
  );
}

export default function Dashboard() {
  const [d, setD] = useState(null);
  const [err, setErr] = useState("");
  useEffect(() => { getDashboard().then(setD).catch((e) => setErr(e.message)); }, []);
  if (err) return <p className="error">{err}</p>;
  if (!d) return <p className="muted">Loading fleet status...</p>;
  const stats = [["Wheels tracked", d.total_wheels], ["Defect records", d.total_inspections], ["Healthy", d.healthy, "ok"], ["Monitor", d.monitor, "warn"], ["Critical", d.critical, "bad"]];
  return (
    <>
      <header className="hero">
        <div><h1>Fleet overview</h1><p>Current condition of every inspected wheel, updated from the latest images.</p></div>
        <svg className="hero-art" viewBox="0 0 220 160" aria-hidden="true">
          {[70, 50, 30].map((r) => <circle key={r} cx="110" cy="80" r={r} fill="none" stroke="#fff" strokeOpacity={r / 200} strokeWidth="2" />)}
          <path className="pulse" d="M10 84h50l14-34 20 70 16-44 12 8h88" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </header>
      <div className="stats">
        {stats.map(([l, v, t], i) => <div key={l} style={{ "--i": i }} className={`stat ${t || ""}`}><b><Count to={v} /></b><span>{l}</span></div>)}
      </div>
      {d.total_wheels > 0 && (
        <div className="fleet" role="img" aria-label={`${d.healthy} healthy, ${d.monitor} monitor, ${d.critical} critical`}>
          <span className="ok" style={{ flex: d.healthy }} /><span className="warn" style={{ flex: d.monitor }} /><span className="bad" style={{ flex: d.critical }} />
        </div>
      )}
      <div className="grid2">
        <Chart title="Defects by severity" data={toRows(d.severity_distribution)} colors={SEV} />
        <Chart title="Defects by type" data={toRows(d.defect_distribution)} />
      </div>
      <section className="panel">
        <h2>Recent inspections</h2>
        {d.recent_inspections?.length ? (
          <table>
            <thead><tr><th>Date</th><th>Wheel</th><th>Defect</th><th>Severity</th><th>Risk</th></tr></thead>
            <tbody>
              {d.recent_inspections.map((r, i) => (
                <tr key={i}><td>{fmt(r.inspection_date)}</td><td>{r.asset_id}</td><td>{r.label ?? r.defect_label ?? r.defect_type ?? r.defect ?? "-"}</td><td>{r.severity ? <Badge>{r.severity}</Badge> : "-"}</td><td>{r.risk_score ?? "-"}</td></tr>
              ))}
            </tbody>
          </table>
        ) : <p className="muted">No inspections yet. Start with a new inspection.</p>}
      </section>
    </>
  );
}
