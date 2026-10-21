import { useEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getCoaches, getTrains, getWheels, imgUrl, inspect, recommend } from "../api.js";
import { Badge, Bar, Gauge, Plan, Trend, WheelChip, fmt, riskTone } from "../ui.jsx";

const STAGES = ["Detecting defects", "Measuring severity", "Checking reliability", "Building heatmap", "Scoring risk"];

function Viewer({ res, preview }) {
  const [tab, setTab] = useState("det");
  // Prefer the real backend-generated image; fall back to local preview only if URL is null
  const backendSrc = imgUrl(tab === "det" ? res.annotated_image_url : res.gradcam_image_url);
  const src = backendSrc || preview;
  const hasGradcam = !!res.gradcam_image_url;
  return (
    <section className="panel">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "det"} onClick={() => setTab("det")}>Detections</button>
        <button role="tab" aria-selected={tab === "cam"} onClick={() => setTab("cam")}>Model attention</button>
      </div>
      <div className="viewer">
        {src ? (
          <a href={src} target="_blank" rel="noreferrer" title="Open full size"><img src={src} alt={tab === "det" ? "Wheel with detected defects" : "Model attention heatmap"} /></a>
        ) : (
          <p className="muted">No {tab === "det" ? "annotated" : "Grad-CAM"} image was generated for this inspection.</p>
        )}
      </div>
      {tab === "cam" && hasGradcam && <p className="muted small">The heatmap shows where the model looked. It does not outline the exact defect boundary.</p>}
      {tab === "cam" && !hasGradcam && <p className="muted small">Grad-CAM heatmap was not generated. The backend may have encountered an error during generation.</p>}
    </section>
  );
}

export default function Inspect() {
  const [params] = useSearchParams();
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [trainId, setTrainId] = useState(params.get("train") || "");
  const [coachId, setCoachId] = useState(params.get("coach") || "");
  const [wheelId, setWheelId] = useState(params.get("wheel") || "");
  const [trains, setTrains] = useState([]);
  const [coaches, setCoaches] = useState([]);
  const [wheels, setWheels] = useState([]);
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const [plan, setPlan] = useState(null);
  const [planBusy, setPlanBusy] = useState(false);
  const [planErr, setPlanErr] = useState("");
  const input = useRef();

  useEffect(() => { getTrains().then(setTrains).catch(() => {}); getWheels().then(setWheels).catch(() => {}); }, []);
  useEffect(() => { if (!trainId) { setCoaches([]); return; } getCoaches(trainId).then(setCoaches).catch(() => {}); }, [trainId]);
  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 700);
    return () => clearInterval(t);
  }, [busy]);

  const wheelOpts = wheels.filter((w) => String(w.coach_id) === String(coachId));
  const picked = wheels.find((w) => w.asset_id === wheelId);
  const trainOf = (id) => trains.find((t) => t.id === id);

  const pickTrain = (v) => { setTrainId(v); setCoachId(""); setWheelId(""); };
  const pickCoach = (v) => { setCoachId(v); setWheelId(""); };
  const pick = (f) => { if (!f) return; setFile(f); setPreview(URL.createObjectURL(f)); setRes(null); setPlan(null); setErr(""); };
  const run = async () => {
    setBusy(true); setStage(0); setErr(""); setRes(null); setPlan(null); setPlanErr("");
    try { setRes(await inspect(file, wheelId, coachId)); getWheels().then(setWheels).catch(() => {}); } catch (e) { setErr(e.message); }
    setBusy(false);
  };
  const makePlan = async () => {
    setPlanBusy(true); setPlanErr("");
    try { setPlan(await recommend(res.asset_id)); } catch (e) { setPlanErr(e.message); }
    setPlanBusy(false);
  };

  const t = res && trainOf(res.train_id);

  return (
    <>
      <h1>New inspection</h1>
      <section className="panel form">
        <div className="drop" onClick={() => input.current.click()} onDragOver={(e) => e.preventDefault()}
             onDrop={(e) => { e.preventDefault(); pick(e.dataTransfer.files[0]); }}>
          {preview ? <img src={preview} alt="Selected wheel" /> : <span>Drop a wheel image here, or click to choose (JPEG or PNG)</span>}
          {busy && <div className="scan" />}
          <input ref={input} type="file" accept="image/jpeg,image/png" hidden onChange={(e) => pick(e.target.files[0])} />
        </div>
        <div className="fields">
          <label>Train
            <select value={trainId} onChange={(e) => pickTrain(e.target.value)}>
              <option value="">Select a train</option>
              {trains.map((x) => <option key={x.id} value={x.id}>{x.train_number} · {x.train_name}</option>)}
            </select>
          </label>
          <label>Coach
            <select value={coachId} disabled={!trainId} onChange={(e) => pickCoach(e.target.value)}>
              <option value="">{trainId ? "Select a coach" : "Pick a train first"}</option>
              {coaches.map((c) => <option key={c.id} value={c.id}>{c.coach_number}{c.coach_type ? ` · ${c.coach_type}` : ""}</option>)}
            </select>
          </label>
          <label>Wheel
            <select value={wheelId} disabled={!coachId} onChange={(e) => setWheelId(e.target.value)}>
              <option value="">{coachId ? (wheelOpts.length ? "Select a wheel" : "No wheels on this coach") : "Pick a coach first"}</option>
              {wheelOpts.map((w) => <option key={w.asset_id} value={w.asset_id}>{w.wheel_identifier} · {w.asset_id}</option>)}
            </select>
          </label>
          {picked && <div className="chips" style={{ margin: 0 }}><WheelChip w={picked} /><span className="muted small">{picked.inspection_count ?? 0} past inspection(s)</span></div>}
          <p className="muted small">Choose the wheel from the registry so this result joins its history, trend and schedule. Leave empty to inspect an image without a registered wheel.</p>
          <button className="primary" disabled={!file || busy} onClick={run}>{busy ? "Inspecting..." : "Run inspection"}</button>
        </div>
      </section>

      {!res && !busy && (
        <section className="panel">
          <h2>What happens to your image</h2>
          <ol className="pipe">
            {["Defect detection", "Severity grading", "Reliability check", "Attention heatmap", "Risk and trend", "Health record"].map((s, i) => <li key={s} style={{ "--i": i }}>{s}</li>)}
          </ol>
        </section>
      )}
      {busy && (
        <ol className="stages" aria-live="polite">
          {STAGES.map((s, i) => <li key={s} className={i < stage ? "done" : i === stage ? "now" : ""}>{s}</li>)}
        </ol>
      )}
      {err && <p className="error">{err}</p>}

      {res && (
        <>
          <section className={`reveal banner ${riskTone(res.wheel_risk_score)}`}>
            <Gauge value={res.wheel_risk_score} />
            <div>
              <h2>{res.wheel_recommended_action}</h2>
              <p>Wheel {res.asset_id}{t ? ` · Train ${t.train_number}` : ""} &middot; {res.total_defects_detected} defect(s) found &middot; {res.processing_time_seconds}s</p>
              <Trend value={res.trend_status} />
              <p className="muted small">{fmt(res.inspection_date)}</p>
            </div>
          </section>
          <Plan rec={plan} busy={planBusy} err={planErr} onGenerate={makePlan} />
          <Viewer res={res} preview={preview} />
          <section className="panel">
            <h2>Defects</h2>
            {res.defects.map((d, i) => (
              <article key={i} style={{ "--i": i + 1 }} className={`reveal defect ${{ Mild: "ok", Moderate: "warn", Severe: "bad" }[d.severity] || ""}`}>
                <header><h3>{d.label}</h3><Badge>{d.severity}</Badge><span className="risk">Risk {d.risk_score}</span></header>
                <div className="meta">
                  <div>Detection confidence <Bar value={d.confidence} /> {(d.confidence * 100).toFixed(0)}%</div>
                  <div>Stability across tests <Badge>{d.reliability}</Badge>{d.std_deviation != null && <> (spread {d.std_deviation})</>}</div>
                </div>
                <p><b>{d.recommended_action}.</b> <span className="muted">{d.trend_note}</span></p>
              </article>
            ))}
          </section>
        </>
      )}
    </>
  );
}
