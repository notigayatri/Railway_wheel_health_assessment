import { useState } from "react";
import { confirmJob, getJobs, getTrains, getWheels, recommend, setJobStatus } from "../api.js";
import { Count, Hold, JobStatus, Priority, Sched, SimNote, fmtWindow, neverInspected, useLoad } from "../ui.jsx";

const OPEN = ["PENDING", "SCHEDULED", "IN_PROGRESS"];
const RANK = { CRITICAL: 0, MODERATE: 1, LOW: 2 };
const TONE = { CRITICAL: "bad", MODERATE: "warn", LOW: "ok" };
const TABS = [["all", "All jobs"], ["pending", "Pending review"], ["urgent", "Urgent"]];
const NEXT = { PENDING: [["Confirm slot", "confirm"]], SCHEDULED: [["Start work", "IN_PROGRESS"]], IN_PROGRESS: [["Mark complete", "COMPLETED"]] };

export default function Planner() {
  const [data, err, reload] = useLoad(() => Promise.all([getJobs(), getTrains(), getWheels()]));
  const [tab, setTab] = useState("all");
  const [busy, setBusy] = useState(null);
  const [msgs, setMsgs] = useState({});
  const [pick, setPick] = useState("");
  const [genBusy, setGenBusy] = useState(false);
  const [genMsg, setGenMsg] = useState("");

  if (err) return <p className="error">{err}</p>;
  if (!data) return <p className="muted">Loading maintenance jobs...</p>;
  const [jobs, trains, wheels] = data;
  const train = (id) => trains.find((t) => t.id === id);
  const isOpen = (j) => OPEN.includes(j.job_status);
  const urgent = jobs.filter((j) => j.priority === "CRITICAL" && isOpen(j));

  const shown = jobs
    .filter((j) => (tab === "pending" ? j.job_status === "PENDING" : tab === "urgent" ? urgent.includes(j) : true))
    .sort((a, b) => Number(!isOpen(a)) - Number(!isOpen(b)) || (RANK[a.priority] ?? 3) - (RANK[b.priority] ?? 3) || String(a.suggested_start).localeCompare(String(b.suggested_start)));

  const stats = [
    ["Urgent", urgent.length, "bad"],
    ["Pending review", jobs.filter((j) => j.job_status === "PENDING").length, "warn"],
    ["Scheduled", jobs.filter((j) => j.job_status === "SCHEDULED").length, "ok"],
    ["With schedule conflicts", jobs.filter((j) => isOpen(j) && j.conflict_notes.length).length, "bad"],
  ];

  const act = async (j, kind) => {
    setBusy(j.id); setMsgs((m) => ({ ...m, [j.id]: "" }));
    try { await (kind === "confirm" ? confirmJob(j.id) : setJobStatus(j.id, kind)); reload(); }
    catch (e) { setMsgs((m) => ({ ...m, [j.id]: e.status === 409 ? "That slot overlaps another confirmed job for this wheel (409 conflict). Pick a different window." : e.message })); }
    setBusy(null);
  };
  const generate = async () => {
    setGenBusy(true); setGenMsg("");
    try { const r = await recommend(pick); setGenMsg(r.duplicate_job ? `${pick} already has an open job (#${r.maintenance_job_id}).` : `Created job #${r.maintenance_job_id} for ${pick}.`); setPick(""); reload(); }
    catch (e) { setGenMsg(e.message); }
    setGenBusy(false);
  };
  const inspected = wheels.filter((w) => !neverInspected(w));

  return (
    <>
      <h1>Maintenance planner</h1>
      {urgent.length > 0 && (
        <div className="alert reveal" role="alert">
          <div><b>{urgent.length} urgent job{urgent.length === 1 ? "" : "s"}.</b> Urgent inspection is recommended before the next scheduled operation of the affected train{urgent.length === 1 ? "" : "s"}, with an operational hold until authorised staff clear the wheel.</div>
        </div>
      )}
      <div className="stats four">
        {stats.map(([l, v, t], i) => <div key={l} style={{ "--i": i }} className={`stat sm ${t}`}><b><Count to={v} /></b><span>{l}</span></div>)}
      </div>

      <section className="panel">
        <div className="split">
          <div className="tabs" role="tablist">
            {TABS.map(([k, l]) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)}>{l}</button>)}
          </div>
          <div className="genrow">
            <select value={pick} onChange={(e) => setPick(e.target.value)} aria-label="Wheel to plan">
              <option value="">Plan maintenance for a wheel...</option>
              {inspected.map((w) => <option key={w.asset_id} value={w.asset_id}>{w.wheel_identifier ?? w.asset_id} · {w.status}</option>)}
            </select>
            <button className="primary sm" disabled={!pick || genBusy} onClick={generate}>{genBusy ? "Planning..." : "Generate"}</button>
          </div>
        </div>
        {genMsg && <p className="muted small" style={{ margin: ".2rem 0 .8rem" }}>{genMsg}</p>}

        {shown.length ? shown.map((j) => {
          const t = train(j.train_id);
          const open = isOpen(j);
          const hold = open && (j.requires_operational_clearance || j.priority === "CRITICAL");
          return (
            <article key={j.id} className={`job ${open ? TONE[j.priority] || "" : "done"}`}>
              <header>
                <h3>{j.wheel_asset_id}</h3><Priority value={j.priority} /><JobStatus value={j.job_status} />
                {j.risk_score != null && <span className="risk">Risk {Math.round(j.risk_score)}</span>}
              </header>
              <div className="meta">
                <div>Train <b>{t ? `${t.train_number} · ${t.train_name}` : j.train_id ?? "-"}</b></div>
                <div>Scheduling <Sched value={j.scheduling_status} /></div>
                <div>Suggested window <b>{j.suggested_start ? fmtWindow(j.suggested_start, j.suggested_end) : "Routine, at next depot turnaround"}</b></div>
                <div>Recommended action <b>{j.recommended_action ?? "-"}</b></div>
              </div>
              {hold && <Hold />}
              {j.conflict_notes.length > 0 && open && <ul className="conf">{j.conflict_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>}
              {j.scheduling_notes && open && <p className="muted small" style={{ margin: ".4rem 0 0" }}>{j.scheduling_notes}</p>}
              {msgs[j.id] && <p className="error" style={{ marginTop: ".7rem" }}>{msgs[j.id]}</p>}
              {open && (
                <div className="acts">
                  {(NEXT[j.job_status] || []).map(([label, kind]) => <button key={kind} className="primary sm" disabled={busy === j.id} onClick={() => act(j, kind)}>{busy === j.id ? "Working..." : label}</button>)}
                  <button className="ghost danger" disabled={busy === j.id} onClick={() => act(j, "CANCELLED")}>Cancel job</button>
                </div>
              )}
            </article>
          );
        }) : <p className="muted">{tab === "all" ? "No maintenance jobs yet. Inspect a wheel, then generate a plan." : "Nothing in this view."}</p>}
      </section>
      <SimNote />
    </>
  );
}
