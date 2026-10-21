import { useEffect, useState } from "react";
import { createCoach, createSchedule, createTrain, createWheel, getSchedules, getTrainTree, getTrains, updateSchedule, updateTrain } from "../api.js";
import { Badge, WheelChip, fmt, human, useLoad } from "../ui.jsx";

const STATUSES = ["Active", "Under Maintenance", "Decommissioned"];
const TYPES = { OPERATING: ["Operating run", "warn"], MAINTENANCE_WINDOW: ["Maintenance window", "ok"], NON_OPERATING: ["Non-operating", ""] };
const DAY = 864e5;

function useForm(init) {
  const [f, setF] = useState(init);
  const on = (k) => (e) => setF((p) => ({ ...p, [k]: e.target.value }));
  return [f, on, () => setF(init)];
}

/* 7-day lane view: when the train runs, when it is free for maintenance */
function Availability({ items }) {
  const t0 = new Date(); t0.setHours(0, 0, 0, 0);
  const start = t0.getTime(), span = 7 * DAY;
  const pct = (t) => Math.max(0, Math.min(100, ((t - start) / span) * 100));
  const days = Array.from({ length: 7 }, (_, i) => new Date(start + i * DAY));
  return (
    <div className="lanes" role="img" aria-label="Next seven days of operating runs and maintenance windows">
      <div className="lane"><span /><div className="dayrow">{days.map((d) => <span key={+d}>{d.toLocaleDateString("en-IN", { weekday: "short", day: "numeric" })}</span>)}</div></div>
      {Object.entries(TYPES).map(([k, [label]]) => (
        <div className="lane" key={k}>
          <span className="lane-l">{label}</span>
          <div className="track">
            {items.filter((s) => s.schedule_type === k).map((s) => {
              const a = pct(+new Date(s.departure_datetime)), b = pct(+new Date(s.arrival_datetime));
              if (!(b > a)) return null;
              return <i key={s.id} className={`seg ${k} ${s.status === "CANCELLED" ? "off" : ""}`} style={{ left: `${a}%`, width: `${b - a}%` }} title={`${label}: ${fmt(s.departure_datetime)} to ${fmt(s.arrival_datetime)}`} />;
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

function RegisterTrain({ onDone }) {
  const [f, on, reset] = useForm({ train_number: "", train_name: "", train_type: "Superfast Express", operational_status: "Active" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setMsg("");
    try { const t = await createTrain({ ...f, train_number: f.train_number.trim(), train_name: f.train_name.trim() }); reset(); onDone(t); } catch (x) { setMsg(x.message); }
    setBusy(false);
  };
  return (
    <details className="addbox">
      <summary>Register a train</summary>
      <form onSubmit={submit}>
        <div className="inline">
          <label>Train number<input required value={f.train_number} onChange={on("train_number")} placeholder="e.g. 12627" /></label>
          <label>Train name<input required value={f.train_name} onChange={on("train_name")} placeholder="e.g. Karnataka Express" /></label>
          <label>Type<input value={f.train_type} onChange={on("train_type")} /></label>
          <label>Status<select value={f.operational_status} onChange={on("operational_status")}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></label>
        </div>
        {msg && <p className="error" style={{ marginTop: ".7rem" }}>{msg}</p>}
        <button className="primary sm" style={{ marginTop: ".8rem" }} disabled={busy}>{busy ? "Saving..." : "Register train"}</button>
      </form>
    </details>
  );
}

function AddCoach({ trainId, onDone }) {
  const [f, on, reset] = useForm({ coach_number: "", coach_type: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setMsg("");
    try { await createCoach(trainId, { coach_number: f.coach_number.trim(), coach_type: f.coach_type.trim() || undefined }); reset(); onDone(); } catch (x) { setMsg(x.message); }
    setBusy(false);
  };
  return (
    <details className="addbox">
      <summary>Add a coach</summary>
      <form onSubmit={submit}>
        <div className="inline">
          <label>Coach number<input required value={f.coach_number} onChange={on("coach_number")} placeholder="e.g. B3" /></label>
          <label>Coach type<input value={f.coach_type} onChange={on("coach_type")} placeholder="e.g. AC 3 Tier" /></label>
        </div>
        {msg && <p className="error" style={{ marginTop: ".7rem" }}>{msg}</p>}
        <button className="primary sm" style={{ marginTop: ".8rem" }} disabled={busy}>{busy ? "Saving..." : "Add coach"}</button>
      </form>
    </details>
  );
}

function AddWheel({ coach, onDone }) {
  const [f, on, reset] = useForm({ wheel_identifier: "", axle_number: "1", position: "Left" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const suggest = `${coach.coach_number}-A${f.axle_number || 1}-${f.position === "Right" ? "R" : "L"}`;
  const submit = async (e) => {
    e.preventDefault(); setBusy(true); setMsg("");
    try { await createWheel(coach.id, { wheel_identifier: f.wheel_identifier.trim() || suggest, axle_number: Number(f.axle_number), position: f.position }); reset(); onDone(); } catch (x) { setMsg(x.message); }
    setBusy(false);
  };
  return (
    <details className="addbox">
      <summary>Add a wheel</summary>
      <form onSubmit={submit}>
        <div className="inline">
          <label>Axle<input type="number" min="1" required value={f.axle_number} onChange={on("axle_number")} /></label>
          <label>Position<select value={f.position} onChange={on("position")}><option>Left</option><option>Right</option></select></label>
          <label>Identifier<input value={f.wheel_identifier} onChange={on("wheel_identifier")} placeholder={suggest} /></label>
        </div>
        {msg && <p className="error" style={{ marginTop: ".7rem" }}>{msg}</p>}
        <button className="primary sm" style={{ marginTop: ".8rem" }} disabled={busy}>{busy ? "Saving..." : "Add wheel"}</button>
      </form>
    </details>
  );
}

function Schedules({ train }) {
  const [list, err, reload] = useLoad(() => getSchedules(train.id), [train.id]);
  const [f, on, reset] = useForm({ schedule_type: "OPERATING", departure_datetime: "", arrival_datetime: "", notes: "" });
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState("");
  const submit = async (e) => {
    e.preventDefault(); setMsg("");
    if (f.arrival_datetime <= f.departure_datetime) { setMsg("Arrival must be after departure."); return; }
    setBusy(true);
    try { await createSchedule(train.id, { ...f, notes: f.notes.trim() || undefined }); reset(); reload(); } catch (x) { setMsg(x.message); }
    setBusy(false);
  };
  const cancel = async (s) => { try { await updateSchedule(s.id, { status: "CANCELLED" }); reload(); } catch (x) { setMsg(x.message); } };
  const rows = [...(list || [])].sort((a, b) => String(a.departure_datetime).localeCompare(String(b.departure_datetime)));

  return (
    <section className="panel">
      <h2>Schedule and availability</h2>
      {err && <p className="error">{err}</p>}
      {list && <Availability items={rows} />}
      <ul className="sched">
        {rows.map((s) => {
          const [label, tone] = TYPES[s.schedule_type] || [human(s.schedule_type), ""];
          return (
            <li key={s.id} className={s.status === "CANCELLED" ? "off" : ""}>
              <span><span className={`badge ${tone}`}>{label}</span></span>
              <span>{fmt(s.departure_datetime)} to {fmt(s.arrival_datetime)}{s.notes && <div className="muted small">{s.notes}</div>}</span>
              {s.status === "CANCELLED" ? <span className="badge">Cancelled</span>
                : <button className="ghost danger" onClick={() => cancel(s)}>Cancel</button>}
            </li>
          );
        })}
        {list && !rows.length && <li className="muted">No schedule entries yet.</li>}
      </ul>
      <details className="addbox">
        <summary>Add a schedule entry</summary>
        <form onSubmit={submit}>
          <div className="inline">
            <label>Type<select value={f.schedule_type} onChange={on("schedule_type")}>{Object.entries(TYPES).map(([k, [l]]) => <option key={k} value={k}>{l}</option>)}</select></label>
            <label>Departure<input type="datetime-local" required value={f.departure_datetime} onChange={on("departure_datetime")} /></label>
            <label>Arrival<input type="datetime-local" required value={f.arrival_datetime} onChange={on("arrival_datetime")} /></label>
            <label>Notes<input value={f.notes} onChange={on("notes")} placeholder="optional" /></label>
          </div>
          {msg && <p className="error" style={{ marginTop: ".7rem" }}>{msg}</p>}
          <button className="primary sm" style={{ marginTop: ".8rem" }} disabled={busy}>{busy ? "Saving..." : "Add entry"}</button>
        </form>
      </details>
    </section>
  );
}

function TrainDetail({ train, onChanged }) {
  const [tree, err, reload] = useLoad(() => getTrainTree(train.id), [train.id]);
  const [msg, setMsg] = useState("");
  const setStatus = async (e) => { setMsg(""); try { await updateTrain(train.id, { operational_status: e.target.value }); onChanged(); } catch (x) { setMsg(x.message); } };
  const wheelCount = tree?.reduce((n, c) => n + c.wheels.length, 0) ?? 0;

  return (
    <>
      <section className="panel">
        <header className="split">
          <div><h2 style={{ marginBottom: ".2rem" }}>{train.train_number} &middot; {train.train_name}</h2><span className="muted small">{train.train_type || "Train"}{tree ? ` · ${tree.length} coach${tree.length === 1 ? "" : "es"} · ${wheelCount} wheel${wheelCount === 1 ? "" : "s"}` : ""}</span></div>
          <label className="statussel">Status<select value={train.operational_status} onChange={setStatus}>{STATUSES.map((s) => <option key={s}>{s}</option>)}</select></label>
        </header>
        {msg && <p className="error">{msg}</p>}
        {err && <p className="error">{err}</p>}
        {!tree && !err && <p className="muted">Loading coaches...</p>}
        {tree?.map((c) => (
          <div className="coach" key={c.id}>
            <header><h3>Coach {c.coach_number}</h3><span className="muted small">{c.coach_type}</span></header>
            {c.wheels.length ? (
              <div className="chips">{c.wheels.map((w) => <WheelChip key={w.asset_id} w={w} to={`/inspect?train=${train.id}&coach=${c.id}&wheel=${w.asset_id}`} />)}</div>
            ) : <p className="muted small" style={{ margin: ".5rem 0 0" }}>No wheels registered on this coach yet.</p>}
            <AddWheel coach={c} onDone={reload} />
          </div>
        ))}
        {tree && !tree.length && <p className="muted">No coaches yet. Add the first one below.</p>}
        <AddCoach trainId={train.id} onDone={reload} />
        {tree?.some((c) => c.wheels.length) && <p className="muted small" style={{ marginTop: ".8rem" }}>Click a wheel to inspect it.</p>}
      </section>
      <Schedules train={train} />
    </>
  );
}

export default function Trains() {
  const [trains, err, reload] = useLoad(getTrains);
  const [sel, setSel] = useState(null);
  useEffect(() => { if (trains?.length && (sel == null || !trains.some((t) => t.id === sel))) setSel(trains[0].id); }, [trains]); // eslint-disable-line react-hooks/exhaustive-deps
  if (err) return <p className="error">{err}</p>;
  if (!trains) return <p className="muted">Loading trains...</p>;
  const train = trains.find((t) => t.id === sel);

  return (
    <>
      <h1>Train registry</h1>
      <div className="grid2 wide start">
        <section className="panel">
          <h2>Trains</h2>
          {trains.length ? (
            <table>
              <thead><tr><th>Number</th><th>Name</th><th>Status</th></tr></thead>
              <tbody>
                {trains.map((t) => (
                  <tr key={t.id} className={`click ${sel === t.id ? "sel" : ""}`} onClick={() => setSel(t.id)}>
                    <td><b>{t.train_number}</b></td><td>{t.train_name}</td><td><Badge>{t.operational_status}</Badge></td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <p className="muted">No trains yet. Register the first one below.</p>}
          <RegisterTrain onDone={(t) => { reload(); if (t?.id != null) setSel(t.id); }} />
        </section>
        <div>
          {train ? <TrainDetail key={train.id} train={train} onChanged={reload} /> : <section className="panel"><p className="muted">Select a train to see its coaches, wheels and schedule.</p></section>}
        </div>
      </div>
    </>
  );
}
