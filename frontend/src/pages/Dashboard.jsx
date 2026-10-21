import { Bar as RBar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis, Cell } from "recharts";
import { Link } from "react-router-dom";
import { getDashboard, getFleet } from "../api.js";
import { Badge, Count, Priority, brief, fmt, useLoad } from "../ui.jsx";

const SEV = { Mild: "#4A9B78", Moderate: "#D7A23B", Severe: "#D2625B" };
const toRows = (o = {}) => Object.entries(o).map(([name, value]) => ({ name, value }));
const trainLabel = (o) => o.train_number ?? o.train_name ?? (o.train_id != null ? `Train ${o.train_id}` : "");

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

/* tiny stacked bar: healthy / monitor / critical / not inspected for one train */
function Mini({ t }) {
  const idle = t.uninspected_wheels ?? 0;
  const healthy = Math.max(0, (t.healthy_wheels ?? t.healthy ?? 0) - idle);
  return (
    <div className="fleet mini" role="img" aria-label={`${healthy} healthy, ${t.monitor_wheels ?? 0} monitor, ${t.critical_wheels ?? 0} critical, ${idle} not inspected`}>
      <span className="ok" style={{ flex: healthy }} /><span className="warn" style={{ flex: t.monitor_wheels ?? t.monitor ?? 0 }} />
      <span className="bad" style={{ flex: t.critical_wheels ?? t.critical ?? 0 }} /><span className="idle" style={{ flex: idle }} />
    </div>
  );
}

export default function Dashboard() {
  const [data, err] = useLoad(() => Promise.all([getFleet(), getDashboard().catch(() => null)]));
  if (err) return <p className="error">{err}</p>;
  if (!data) return <p className="muted">Loading fleet status...</p>;
  const [f, legacy] = data;

  const top = [["Trains", f.total_trains], ["Coaches", f.total_coaches], ["Wheels tracked", f.total_wheels], ["Healthy", f.healthy_wheels, "ok"], ["Monitor", f.monitor_wheels, "warn"], ["Critical", f.critical_wheels, "bad"]];
  const second = [["Inspected wheels", f.inspected_wheels], ["Not inspected yet", f.uninspected_wheels], ["Pending maintenance jobs", f.pending_maintenance_jobs, "warn"], ["Scheduled jobs", f.scheduled_maintenance_jobs, "ok"]];
  const idle = f.uninspected_wheels ?? 0;
  const trains = f.train_health_summaries ?? [];
  const upcoming = f.upcoming_maintenance ?? [];
  const conflicts = f.operating_schedule_conflicts ?? [];
  const critical = f.critical_wheels_by_train ?? [];

  return (
    <>
      <header className="hero">
        <div><h1>Fleet overview</h1><p>Health of every train, coach and wheel, with maintenance planned around the operating schedule.</p></div>
        <svg className="hero-art" viewBox="0 0 220 160" aria-hidden="true">
          {[70, 50, 30].map((r) => <circle key={r} cx="110" cy="80" r={r} fill="none" stroke="#fff" strokeOpacity={r / 200} strokeWidth="2" />)}
          <path className="pulse" d="M10 84h50l14-34 20 70 16-44 12 8h88" fill="none" stroke="#fff" strokeWidth="3.5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </header>

      {f.critical_wheels > 0 && (
        <div className="alert reveal" role="alert">
          <div><b>{f.critical_wheels} critical wheel{f.critical_wheels === 1 ? "" : "s"} flagged.</b> Urgent inspection and an operational hold are recommended until engineering staff clear them.</div>
          <Link className="ghost" to="/planner">Open planner</Link>
        </div>
      )}

      <div className="stats six">
        {top.map(([l, v, t], i) => <div key={l} style={{ "--i": i }} className={`stat ${t || ""}`}><b><Count to={v} /></b><span>{l}</span></div>)}
      </div>
      {f.total_wheels > 0 && (
        <>
          <div className="fleet" role="img" aria-label={`${f.healthy_wheels - idle} healthy, ${f.monitor_wheels} monitor, ${f.critical_wheels} critical, ${idle} not inspected`}>
            <span className="ok" style={{ flex: Math.max(0, f.healthy_wheels - idle) }} /><span className="warn" style={{ flex: f.monitor_wheels }} />
            <span className="bad" style={{ flex: f.critical_wheels }} /><span className="idle" style={{ flex: idle }} />
          </div>
          <p className="legend"><i className="ok" />Healthy<i className="warn" />Monitor<i className="bad" />Critical<i className="idle" />Not inspected</p>
        </>
      )}
      <div className="stats four">
        {second.map(([l, v, t], i) => <div key={l} style={{ "--i": i }} className={`stat sm ${t || ""}`}><b><Count to={v} /></b><span>{l}</span></div>)}
      </div>

      <div className="grid2">
        <section className="panel">
          <h2>Train health</h2>
          {trains.length ? (
            <table>
              <thead><tr><th>Train</th><th>Wheels</th><th>Critical</th><th>Condition</th></tr></thead>
              <tbody>
                {trains.map((t, i) => (
                  <tr key={t.train_id ?? i}>
                    <td><b>{t.train_number}</b><div className="muted small">{t.train_name}</div></td>
                    <td>{t.total_wheels ?? t.wheels ?? "-"}</td>
                    <td>{(t.critical_wheels ?? t.critical) ? <Badge>Critical</Badge> : <span className="muted">0</span>}</td>
                    <td style={{ minWidth: 120 }}><Mini t={t} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No trains registered yet. Add one in the Trains page.</p>}
        </section>

        <section className="panel">
          <h2>Upcoming maintenance</h2>
          {upcoming.length ? (
            <ul className="timeline">
              {upcoming.map((j, i) => (
                <li key={j.id ?? i}>
                  <b>{j.wheel_asset_id ?? j.asset_id}</b> <Priority value={j.priority} />
                  <div className="muted small">{trainLabel(j)} &middot; {j.suggested_start ? fmt(j.suggested_start) : brief(j)}</div>
                </li>
              ))}
            </ul>
          ) : <p className="muted">No upcoming maintenance jobs.</p>}
        </section>
      </div>

      <div className="grid2">
        <section className="panel">
          <h2>Schedule conflicts</h2>
          {conflicts.length ? (
            <ul className="timeline bad">
              {conflicts.map((c, i) => (
                <li key={i}><b>{typeof c === "object" ? [trainLabel(c), c.wheel_asset_id].filter(Boolean).join(" · ") : "Conflict"}</b>
                  <div className="muted small">{typeof c === "object" ? (c.message ?? c.conflict_note ?? brief(c)) : c}</div></li>
              ))}
            </ul>
          ) : <p className="muted">No maintenance job clashes with an operating run.</p>}
        </section>

        <section className="panel">
          <h2>Critical wheels</h2>
          {critical.length ? (
            <ul className="timeline bad">
              {critical.map((c, i) => (
                <li key={i}><b>{typeof c === "object" ? [trainLabel(c), c.wheel_asset_id ?? c.asset_id].filter(Boolean).join(" · ") : String(c)}</b>
                  {typeof c === "object" && <div className="muted small">{[c.wheel_identifier, c.risk_score != null ? `risk ${c.risk_score}` : ""].filter(Boolean).join(" · ") || brief(c)}</div>}</li>
              ))}
            </ul>
          ) : <p className="muted">No critical wheels right now.</p>}
        </section>
      </div>

      {legacy && (
        <>
          <div className="grid2">
            <Chart title="Defects by severity" data={toRows(legacy.severity_distribution)} colors={SEV} />
            <Chart title="Defects by type" data={toRows(legacy.defect_distribution)} />
          </div>
          <section className="panel">
            <h2>Recent inspections</h2>
            {legacy.recent_inspections?.length ? (
              <table>
                <thead><tr><th>Date</th><th>Wheel</th><th>Defect</th><th>Severity</th><th>Risk</th></tr></thead>
                <tbody>
                  {legacy.recent_inspections.map((r, i) => (
                    <tr key={i}><td>{fmt(r.inspection_date)}</td><td>{r.asset_id}</td><td>{r.label ?? r.defect_label ?? r.defect_type ?? r.defect ?? "-"}</td><td>{r.severity ? <Badge>{r.severity}</Badge> : "-"}</td><td>{r.risk_score ?? "-"}</td></tr>
                  ))}
                </tbody>
              </table>
            ) : <p className="muted">No inspections yet. Start with a new inspection.</p>}
          </section>
        </>
      )}
    </>
  );
}
