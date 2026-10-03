import { useEffect, useRef, useState } from "react";
import { MOCK, imgUrl, inspect } from "../api.js";
import { Badge, Bar, Gauge, Trend, fmt } from "../ui.jsx";

const STAGES = ["Detecting defects", "Measuring severity", "Checking reliability", "Building heatmap", "Scoring risk"];

function Viewer({ res, preview }) {
  const [tab, setTab] = useState("det");
  const src = MOCK ? preview : imgUrl(tab === "det" ? res.annotated_image_url : res.gradcam_image_url);
  return (
    <section className="panel">
      <div className="tabs" role="tablist">
        <button role="tab" aria-selected={tab === "det"} onClick={() => setTab("det")}>Detections</button>
        <button role="tab" aria-selected={tab === "cam"} onClick={() => setTab("cam")}>Model attention</button>
      </div>
      <div className="viewer">
        <a href={src} target="_blank" rel="noreferrer" title="Open full size"><img src={src} alt={tab === "det" ? "Wheel with detected defects" : "Model attention heatmap"} /></a>
        {MOCK && tab === "cam" && <div className="heat" />}
      </div>
      {tab === "cam" && <p className="muted small">The heatmap shows where the model looked. It does not outline the exact defect boundary.</p>}
    </section>
  );
}

export default function Inspect() {
  const [file, setFile] = useState(null);
  const [preview, setPreview] = useState("");
  const [wheelId, setWheelId] = useState("");
  const [busy, setBusy] = useState(false);
  const [stage, setStage] = useState(0);
  const [res, setRes] = useState(null);
  const [err, setErr] = useState("");
  const input = useRef();

  useEffect(() => {
    if (!busy) return;
    const t = setInterval(() => setStage((s) => Math.min(s + 1, STAGES.length - 1)), 700);
    return () => clearInterval(t);
  }, [busy]);

  const pick = (f) => { if (!f) return; setFile(f); setPreview(URL.createObjectURL(f)); setRes(null); setErr(""); };
  const run = async () => {
    setBusy(true); setStage(0); setErr(""); setRes(null);
    try { setRes(await inspect(file, wheelId.trim())); } catch (e) { setErr(e.message); }
    setBusy(false);
  };

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
          <label>Wheel ID (optional)
            <input value={wheelId} onChange={(e) => setWheelId(e.target.value)} placeholder="e.g. WH000001" />
          </label>
          <p className="muted small">Leave empty for a new wheel. Enter an existing ID to add this inspection to its history and trend.</p>
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
          <section className={`reveal banner ${res.wheel_risk_score < 34 ? "ok" : res.wheel_risk_score < 67 ? "warn" : "bad"}`}>
            <Gauge value={res.wheel_risk_score} />
            <div>
              <h2>{res.wheel_recommended_action}</h2>
              <p>Wheel {res.asset_id} &middot; {res.total_defects_detected} defect(s) found &middot; {res.processing_time_seconds}s</p>
              <Trend value={res.trend_status} />
              <p className="muted small">{fmt(res.inspection_date)}</p>
            </div>
          </section>
          <Viewer res={res} preview={preview} />
          <section className="panel">
            <h2>Defects</h2>
            {res.defects.map((d, i) => (
              <article key={i} style={{ "--i": i + 1 }} className={`reveal defect ${{ Mild: "ok", Moderate: "warn", Severe: "bad" }[d.severity] || ""}`}>
                <header><h3>{d.label}</h3><Badge>{d.severity}</Badge><span className="risk">Risk {d.risk_score}</span></header>
                <div className="meta">
                  <div>Detection confidence <Bar value={d.confidence} /> {(d.confidence * 100).toFixed(0)}%</div>
                  <div>Stability across tests <Badge>{d.reliability}</Badge> (spread {d.std_deviation})</div>
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
