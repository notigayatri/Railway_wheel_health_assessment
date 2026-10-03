import { useEffect, useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { getHistory, getWheels } from "../api.js";
import { Badge, Trend, fmt } from "../ui.jsx";

export default function Wheels() {
  const [list, setList] = useState(null);
  const [q, setQ] = useState("");
  const [sel, setSel] = useState(null);
  const [hist, setHist] = useState([]);
  const [err, setErr] = useState("");

  useEffect(() => { getWheels().then(setList).catch((e) => setErr(e.message)); }, []);
  useEffect(() => { if (sel) getHistory(sel).then(setHist).catch((e) => setErr(e.message)); }, [sel]);

  if (err) return <p className="error">{err}</p>;
  if (!list) return <p className="muted">Loading wheels...</p>;
  const rows = list.filter((w) => w.asset_id.toLowerCase().includes(q.toLowerCase()));
  const series = [...hist].reverse().map((h) => ({ date: new Date(h.inspection_date).toLocaleDateString("en-IN"), risk: h.risk_score }));

  return (
    <>
      <h1>Wheels</h1>
      <div className="grid2 wide">
        <section className="panel">
          <input className="search" placeholder="Search by wheel ID" value={q} onChange={(e) => setQ(e.target.value)} />
          {rows.length ? (
            <table>
              <thead><tr><th>Wheel</th><th>Status</th><th>Inspections</th><th>Last inspected</th></tr></thead>
              <tbody>
                {rows.map((w) => (
                  <tr key={w.asset_id} className={`click ${sel === w.asset_id ? "sel" : ""}`} onClick={() => setSel(w.asset_id)}>
                    <td>{w.asset_id}</td><td><Badge>{w.status}</Badge></td><td>{w.inspection_count}</td><td>{fmt(w.latest_inspection)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No wheels match that ID.</p>}
        </section>
        <section className="panel">
          {!sel ? <p className="muted">Select a wheel to see its inspection history.</p> : (
            <>
              <h2>{sel} history</h2>
              <ResponsiveContainer width="100%" height={170}>
                <LineChart data={series} margin={{ left: -20 }}>
                  <CartesianGrid vertical={false} stroke="#DDE6E4" />
                  <XAxis dataKey="date" tickLine={false} /><YAxis domain={[0, 100]} tickLine={false} axisLine={false} /><Tooltip />
                  <Line dataKey="risk" stroke="#2F7F79" strokeWidth={2} dot />
                </LineChart>
              </ResponsiveContainer>
              <ul className="timeline">
                {hist.map((h, i) => (
                  <li key={i}><b>{h.label}</b> <Badge>{h.severity}</Badge> <Trend value={h.trend_status} />
                    <div className="muted small">{fmt(h.inspection_date)} &middot; risk {h.risk_score} &middot; {h.recommended_action}</div></li>
                ))}
              </ul>
            </>
          )}
        </section>
      </div>
    </>
  );
}
