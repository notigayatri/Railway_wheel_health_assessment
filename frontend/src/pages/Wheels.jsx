import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getHistory, getServiceHistory, getTrains, getWheels } from "../api.js";
import { Badge, JobStatus, Priority, Trend, fmt, fmtWindow, neverInspected, useLoad } from "../ui.jsx";

export default function Wheels() {
  const [data, loadErr] = useLoad(() => Promise.all([getWheels(), getTrains().catch(() => [])]));
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const [hist, setHist] = useState([]);
  const [service, setService] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => {
    if (!sel) return;
    setHist([]); setService([]);
    getHistory(sel).then(setHist).catch((e) => setErr(e.message));
    getServiceHistory(sel).then(setService).catch(() => {});
  }, [sel]);

  if (err || loadErr) return <p className="error">{err || loadErr}</p>;
  if (!data) return <p className="muted">Loading wheels...</p>;
  const [list, trains] = data;
  const trainNo = (id) => trains.find((t) => t.id === id)?.train_number ?? "-";
  const term = q.toLowerCase();
  const rows = list.filter((w) => `${w.asset_id} ${w.wheel_identifier ?? ""} ${trainNo(w.train_id)}`.toLowerCase().includes(term));
  const series = [...hist].reverse().map((h) => ({ date: new Date(h.inspection_date).toLocaleDateString("en-IN"), risk: h.risk_score }));
  const wheel = list.find((w) => w.asset_id === sel);

  return (
    <>
      <h1>Wheel health history</h1>
      <div className="grid2 wide start">
        <section className="panel">
          <input className="search" placeholder="Search by wheel ID, identifier or train" value={q} onChange={(e) => setQ(e.target.value)} />
          {rows.length ? (
            <table>
              <thead><tr><th>Wheel</th><th>Train</th><th>Status</th><th>Inspections</th><th>Last inspected</th></tr></thead>
              <tbody>
                {rows.map((w) => (
                  <tr key={w.asset_id} className={`click ${sel === w.asset_id ? "sel" : ""}`} onClick={() => setSel(w.asset_id)}>
                    <td>{w.asset_id}{w.wheel_identifier && <div className="muted small">{w.wheel_identifier}</div>}</td>
                    <td>{trainNo(w.train_id)}</td>
                    <td>{neverInspected(w) ? <span className="badge">Not inspected</span> : <Badge>{w.status}</Badge>}</td>
                    <td>{w.inspection_count ?? "-"}</td><td>{fmt(w.latest_inspection)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No wheels match that search.</p>}
        </section>
        <section className="panel">
          {!sel ? <p className="muted">Select a wheel to see how its risk has changed.</p> : (
            <>
              <h2>{sel} history{wheel?.wheel_identifier ? ` · ${wheel.wheel_identifier}` : ""}</h2>
              {hist.length > 0 ? (
                <ResponsiveContainer width="100%" height={170}>
                  <LineChart data={series} margin={{ left: -20 }}>
                    <CartesianGrid vertical={false} stroke="#DDE6E4" />
                    <XAxis dataKey="date" tickLine={false} /><YAxis domain={[0, 100]} tickLine={false} axisLine={false} /><Tooltip />
                    <Line dataKey="risk" stroke="#2F7F79" strokeWidth={2} dot />
                  </LineChart>
                </ResponsiveContainer>
              ) : <p className="muted">No inspections recorded for this wheel yet.</p>}
              <ul className="timeline">
                {hist.map((h, i) => (
                  <li key={i}><b>{h.label}</b> <Badge>{h.severity}</Badge> <Trend value={h.trend_status} />
                    <div className="muted small">{fmt(h.inspection_date)} &middot; risk {h.risk_score} &middot; {h.recommended_action}</div></li>
                ))}
              </ul>
              {service.length > 0 && (
                <>
                  <h2 style={{ marginTop: "1.4rem" }}>Maintenance history</h2>
                  <ul className="timeline">
                    {service.map((j, i) => (
                      <li key={j.id ?? i}><Priority value={j.priority} /> <JobStatus value={j.job_status} />
                        <div className="muted small">{j.suggested_start ? fmtWindow(j.suggested_start, j.suggested_end) : "Routine"}{j.recommended_action ? ` · ${j.recommended_action}` : ""}</div></li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </section>
      </div>
    </>
  );
}
