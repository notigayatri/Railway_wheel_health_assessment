// 127.0.0.1 avoids a ~2s IPv6 lookup delay per request on Windows (see backend README).
const BASE = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000";
export const MOCK = import.meta.env.VITE_USE_MOCK !== "false";
export const imgUrl = (p) => (p ? BASE + p : null);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const clone = (v) => JSON.parse(JSON.stringify(v));

/* ---------- small helpers ---------- */
const pad = (n) => String(n).padStart(2, "0");
const iso = (x) => `${x.getFullYear()}-${pad(x.getMonth() + 1)}-${pad(x.getDate())}T${pad(x.getHours())}:${pad(x.getMinutes())}:00`;
const at = (d, h, m = 0) => { const x = new Date(); x.setDate(x.getDate() + d); x.setHours(h, m, 0, 0); return iso(x); };
const inHours = (h) => { const x = new Date(Date.now() + h * 36e5); x.setMinutes(0, 0, 0); return iso(x); };
const fail = (status, message) => Object.assign(new Error(message), { status });
const nextId = (arr) => Math.max(0, ...arr.map((x) => x.id)) + 1;
const overlaps = (aS, aE, bS, bE) => aS < bE && aE > bS;
const OPEN = ["PENDING", "SCHEDULED", "IN_PROGRESS"];
const asList = (r) => (Array.isArray(r) ? r : r?.items ?? r?.jobs ?? r?.trains ?? r?.coaches ?? r?.wheels ?? r?.schedules ?? r?.history ?? []);
const withTime = (v) => (v && v.length === 16 ? v + ":00" : v);

/* conflict_notes can arrive as an array, a JSON string or plain text */
function normJob(j) {
  let notes = j.conflict_notes;
  if (typeof notes === "string") { try { notes = JSON.parse(notes); } catch { notes = notes ? [notes] : []; } }
  return { ...j, job_status: j.job_status ?? j.status, conflict_notes: Array.isArray(notes) ? notes : [] };
}

/* =====================================================================
   MOCK BACKEND (VITE_USE_MOCK=true). Same shapes as the real API, kept in
   memory so registering trains, inspecting and planning all work offline.
   All of this is simulated demo data.
   ===================================================================== */
const db = {
  trains: [
    { id: 1, train_number: "12627", train_name: "Karnataka Express", train_type: "Superfast Express", operational_status: "Active" },
    { id: 2, train_number: "TR-2048", train_name: "Vande Bharat Express", train_type: "Superfast Express", operational_status: "Active" },
    { id: 3, train_number: "TR-3110", train_name: "Depot Shuttle", train_type: "Passenger", operational_status: "Under Maintenance" },
  ],
  coaches: [
    { id: 1, train_id: 1, coach_number: "B1", coach_type: "AC 3 Tier" },
    { id: 2, train_id: 1, coach_number: "B2", coach_type: "AC 3 Tier" },
    { id: 3, train_id: 2, coach_number: "C1", coach_type: "Executive Chair Car" },
  ],
  wheels: [
    { asset_id: "WH000001", coach_id: 1, train_id: 1, wheel_identifier: "B1-A1-L", axle_number: 1, position: "Left", status: "Healthy", inspection_count: 1 },
    { asset_id: "WH000002", coach_id: 1, train_id: 1, wheel_identifier: "B1-A1-R", axle_number: 1, position: "Right", status: "Critical", inspection_count: 2 },
    { asset_id: "WH000003", coach_id: 1, train_id: 1, wheel_identifier: "B1-A2-L", axle_number: 2, position: "Left", status: "Monitor", inspection_count: 2 },
    { asset_id: "WH000004", coach_id: 1, train_id: 1, wheel_identifier: "B1-A2-R", axle_number: 2, position: "Right", status: "Healthy", inspection_count: 0 },
    { asset_id: "WH000005", coach_id: 2, train_id: 1, wheel_identifier: "B2-A1-L", axle_number: 1, position: "Left", status: "Healthy", inspection_count: 1 },
    { asset_id: "WH000006", coach_id: 2, train_id: 1, wheel_identifier: "B2-A1-R", axle_number: 1, position: "Right", status: "Healthy", inspection_count: 0 },
    { asset_id: "WH000007", coach_id: 3, train_id: 2, wheel_identifier: "C1-A1-L", axle_number: 1, position: "Left", status: "Healthy", inspection_count: 1 },
    { asset_id: "WH000008", coach_id: 3, train_id: 2, wheel_identifier: "C1-A1-R", axle_number: 1, position: "Right", status: "Monitor", inspection_count: 1 },
  ],
  history: {
    WH000001: [{ inspection_date: at(-9, 8, 30), label: "Cracks-Scratches", severity: "Mild", risk_score: 24, trend_status: "FIRST_INSPECTION", recommended_action: "Monitor only" }],
    WH000002: [
      { inspection_date: at(-1, 9, 40), label: "Shelling", severity: "Severe", risk_score: 84, trend_status: "WORSENING", recommended_action: "Immediate inspection" },
      { inspection_date: at(-6, 10, 5), label: "Shelling", severity: "Moderate", risk_score: 58, trend_status: "FIRST_INSPECTION", recommended_action: "Schedule maintenance" },
    ],
    WH000003: [
      { inspection_date: at(-2, 13, 17), label: "Shelling", severity: "Moderate", risk_score: 58, trend_status: "WORSENING", recommended_action: "Schedule maintenance" },
      { inspection_date: at(-8, 10, 2), label: "Shelling", severity: "Mild", risk_score: 31, trend_status: "FIRST_INSPECTION", recommended_action: "Monitor only" },
    ],
    WH000005: [{ inspection_date: at(-4, 16, 5), label: "Flange Wear", severity: "Mild", risk_score: 22, trend_status: "FIRST_INSPECTION", recommended_action: "Monitor only" }],
    WH000007: [{ inspection_date: at(-3, 11, 45), label: "Cracks-Scratches", severity: "Mild", risk_score: 27, trend_status: "FIRST_INSPECTION", recommended_action: "Monitor only" }],
    WH000008: [{ inspection_date: at(-1, 15, 20), label: "Flat Spots", severity: "Moderate", risk_score: 58, trend_status: "FIRST_INSPECTION", recommended_action: "Schedule maintenance" }],
  },
  schedules: [
    { id: 1, train_id: 1, schedule_type: "OPERATING", departure_datetime: at(1, 6), arrival_datetime: at(1, 22), status: "ACTIVE", notes: "Scheduled passenger run" },
    { id: 2, train_id: 1, schedule_type: "MAINTENANCE_WINDOW", departure_datetime: at(3, 1), arrival_datetime: at(3, 7), status: "ACTIVE", notes: "Depot slot" },
    { id: 3, train_id: 2, schedule_type: "OPERATING", departure_datetime: at(1, 16), arrival_datetime: at(1, 23), status: "ACTIVE", notes: "Scheduled passenger run" },
    { id: 4, train_id: 2, schedule_type: "MAINTENANCE_WINDOW", departure_datetime: at(1, 18), arrival_datetime: at(1, 22), status: "ACTIVE", notes: "Depot slot" },
    { id: 5, train_id: 2, schedule_type: "OPERATING", departure_datetime: at(4, 6), arrival_datetime: at(4, 20), status: "ACTIVE", notes: "Scheduled passenger run" },
  ],
  jobs: [
    { id: 1, wheel_asset_id: "WH000002", train_id: 1, coach_id: 1, priority: "CRITICAL", risk_score: 84, job_status: "PENDING", recommended_action: "Immediate inspection", trend_status: "WORSENING", suggested_start: at(0, 23), suggested_end: at(1, 1), scheduling_status: "CLEARANCE_REQUIRED", requires_operational_clearance: true, scheduling_notes: "Critical defect. Urgent inspection is required before the next operation.", conflict_notes: [`Conflicts with operating schedule (departure=${at(1, 6)}, arrival=${at(1, 22)})`] },
    { id: 2, wheel_asset_id: "WH000008", train_id: 2, coach_id: 3, priority: "MODERATE", risk_score: 58, job_status: "PENDING", recommended_action: "Schedule maintenance", trend_status: "FIRST_INSPECTION", suggested_start: at(1, 18), suggested_end: at(1, 22), scheduling_status: "CONFLICT", requires_operational_clearance: false, scheduling_notes: "A maintenance window was found but it overlaps an operating run. Consider moving the window.", conflict_notes: [`Conflicts with operating schedule (departure=${at(1, 16)}, arrival=${at(1, 23)})`] },
    { id: 3, wheel_asset_id: "WH000003", train_id: 1, coach_id: 1, priority: "MODERATE", risk_score: 58, job_status: "SCHEDULED", recommended_action: "Schedule maintenance", trend_status: "WORSENING", suggested_start: at(3, 1), suggested_end: at(3, 7), scheduling_status: "OK", requires_operational_clearance: false, scheduling_notes: "Fits the next free maintenance window with no operating conflict.", conflict_notes: [] },
  ],
};
const statusFor = (risk) => (risk < 50 ? "Healthy" : risk < 80 ? "Monitor" : "Critical");
const priorityFor = (risk) => (risk < 50 ? "LOW" : risk < 80 ? "MODERATE" : "CRITICAL");
const latestRisk = (id) => db.history[id]?.[0]?.risk_score ?? 0;

function addWheel({ coach_id, wheel_identifier, axle_number, position }) {
  const coach = db.coaches.find((c) => c.id === Number(coach_id));
  const w = {
    asset_id: "WH" + String(db.wheels.length + 1).padStart(6, "0"), coach_id: coach?.id ?? null, train_id: coach?.train_id ?? null,
    wheel_identifier: wheel_identifier || "UNASSIGNED", axle_number: axle_number ?? null, position: position ?? null, status: "Healthy", inspection_count: 0,
  };
  db.wheels.push(w);
  return w;
}

function mockWheels() {
  return db.wheels.map((w) => ({ ...w, latest_inspection: db.history[w.asset_id]?.[0]?.inspection_date ?? null }));
}

function mockLegacyDashboard() {
  const all = Object.entries(db.history).flatMap(([id, h]) => h.map((x) => ({ ...x, asset_id: id })));
  const count = (key) => all.reduce((o, x) => ((o[x[key]] = (o[x[key]] || 0) + 1), o), {});
  const c = (s) => db.wheels.filter((w) => w.status === s).length;
  return {
    total_wheels: db.wheels.length, total_inspections: all.length, healthy: c("Healthy"), monitor: c("Monitor"), critical: c("Critical"),
    severity_distribution: count("severity"), defect_distribution: count("label"),
    recent_inspections: all.sort((a, b) => b.inspection_date.localeCompare(a.inspection_date)).slice(0, 6),
  };
}

function mockFleet() {
  const w = db.wheels;
  const n = (s) => w.filter((x) => x.status === s).length;
  const idle = w.filter((x) => !x.inspection_count).length;
  const tnum = (id) => db.trains.find((t) => t.id === id)?.train_number;
  const open = db.jobs.filter((j) => OPEN.includes(j.job_status)).sort((a, b) => a.suggested_start.localeCompare(b.suggested_start));
  const events = Object.values(db.history).reduce((a, h) => a + h.length, 0);
  return {
    total_trains: db.trains.length, total_coaches: db.coaches.length, total_wheels: w.length,
    total_inspections: events, total_inspection_events: events,
    inspected_wheels: w.length - idle, uninspected_wheels: idle,
    healthy_wheels: n("Healthy"), monitor_wheels: n("Monitor"), critical_wheels: n("Critical"),
    pending_maintenance_jobs: db.jobs.filter((j) => j.job_status === "PENDING").length,
    scheduled_maintenance_jobs: db.jobs.filter((j) => j.job_status === "SCHEDULED").length,
    train_health_summaries: db.trains.map((t) => {
      const tw = w.filter((x) => x.train_id === t.id);
      const k = (s) => tw.filter((x) => x.status === s).length;
      return { train_id: t.id, train_number: t.train_number, train_name: t.train_name, total_wheels: tw.length, healthy_wheels: k("Healthy"), monitor_wheels: k("Monitor"), critical_wheels: k("Critical"), uninspected_wheels: tw.filter((x) => !x.inspection_count).length };
    }),
    critical_wheels_by_train: w.filter((x) => x.status === "Critical").map((x) => ({ train_number: tnum(x.train_id), wheel_asset_id: x.asset_id, wheel_identifier: x.wheel_identifier, risk_score: latestRisk(x.asset_id) })),
    upcoming_maintenance: open.map((j) => ({ ...j, train_number: tnum(j.train_id) })),
    operating_schedule_conflicts: open.filter((j) => j.conflict_notes.length).map((j) => ({ train_number: tnum(j.train_id), wheel_asset_id: j.wheel_asset_id, priority: j.priority, message: j.conflict_notes[0] })),
  };
}

function mockInspect(file, wheelId, coachId) {
  let w = db.wheels.find((x) => x.asset_id === wheelId);
  if (!w) w = addWheel({ coach_id: coachId });
  const mode = w.asset_id === "WH000002" ? "severe" : w.asset_id === "WH000004" ? "mild" : "mod";
  const R = {
    severe: { risk: 84, trend: "WORSENING", action: "Immediate inspection", defects: [
      { label: "Shelling", confidence: 0.93, severity: "Severe", mean_confidence: 0.9, std_deviation: 0.02, reliability: "HIGH", risk_score: 84, recommended_action: "Immediate inspection", trend_note: "Severity is above the historical average for Shelling on this wheel." },
      { label: "Flange Wear", confidence: 0.74, severity: "Moderate", mean_confidence: 0.69, std_deviation: 0.07, reliability: "MEDIUM", risk_score: 52, recommended_action: "Schedule maintenance", trend_note: "First time this defect type was seen on this wheel." }] },
    mod: { risk: 58, trend: "WORSENING", action: "Schedule maintenance", defects: [
      { label: "Shelling", confidence: 0.86, severity: "Moderate", mean_confidence: 0.82, std_deviation: 0.04, reliability: "HIGH", risk_score: 58, recommended_action: "Schedule maintenance", trend_note: "Severity has increased since the previous inspection." },
      { label: "Cracks-Scratches", confidence: 0.72, severity: "Mild", mean_confidence: 0.64, std_deviation: 0.11, reliability: "MEDIUM", risk_score: 33, recommended_action: "Monitor only", trend_note: "First time this defect type was seen on this wheel." }] },
    mild: { risk: 31, trend: "STABLE", action: "Monitor only", defects: [
      { label: "Cracks-Scratches", confidence: 0.78, severity: "Mild", mean_confidence: 0.75, std_deviation: 0.03, reliability: "HIGH", risk_score: 31, recommended_action: "Monitor only", trend_note: "Within the normal range for this wheel." }] },
  }[mode];
  const when = iso(new Date());
  const top = R.defects[0];
  db.history[w.asset_id] = [{ inspection_date: when, label: top.label, severity: top.severity, risk_score: R.risk, trend_status: R.trend, recommended_action: R.action }, ...(db.history[w.asset_id] || [])];
  w.status = statusFor(R.risk);
  w.inspection_count += 1;
  return {
    inspection_id: "INS" + String(Date.now()).slice(-6), inspection_event_id: "EVT" + String(Date.now()).slice(-5), asset_id: w.asset_id, train_id: w.train_id, coach_id: w.coach_id,
    image_name: file.name, inspection_date: when, trend_status: R.trend, wheel_risk_score: R.risk, wheel_recommended_action: R.action,
    total_defects_detected: R.defects.length, processing_time_seconds: 2.4, annotated_image_url: null, gradcam_image_url: null, defects: R.defects,
  };
}

function mockRecommend(wheelId) {
  const w = db.wheels.find((x) => x.asset_id === wheelId);
  if (!w) throw fail(404, "Wheel not found");
  if (!w.inspection_count) throw fail(422, "This wheel has not been inspected yet");
  const risk = latestRisk(wheelId), priority = priorityFor(risk);
  const existing = db.jobs.find((j) => j.wheel_asset_id === wheelId && OPEN.includes(j.job_status));
  if (existing) return { ...clone(existing), maintenance_job_id: existing.id, duplicate_job: true };
  const runs = db.schedules.filter((s) => s.train_id === w.train_id && s.schedule_type === "OPERATING" && s.status === "ACTIVE");
  const clash = (a, b) => runs.filter((r) => overlaps(a, b, r.departure_datetime, r.arrival_datetime)).map((r) => `Conflicts with operating schedule (departure=${r.departure_datetime}, arrival=${r.arrival_datetime})`);
  let start = null, end = null, status = "ROUTINE", notes = "Low risk. Routine monitoring; maintain at the next depot turnaround.", conflicts = [], clearance = false;
  if (priority === "CRITICAL") {
    start = inHours(1); end = inHours(3); conflicts = clash(start, end); clearance = true; status = "CLEARANCE_REQUIRED";
    notes = "Critical defect. Urgent inspection is required before the next operation.";
  } else if (priority === "MODERATE") {
    const win = db.schedules.filter((s) => s.train_id === w.train_id && s.schedule_type === "MAINTENANCE_WINDOW" && s.status === "ACTIVE" && s.arrival_datetime > iso(new Date())).sort((a, b) => a.departure_datetime.localeCompare(b.departure_datetime))[0];
    if (win) { start = win.departure_datetime; end = win.arrival_datetime; conflicts = clash(start, end); status = conflicts.length ? "CONFLICT" : "OK"; notes = conflicts.length ? "A maintenance window was found but it overlaps an operating run. Consider moving the window." : "Fits the next free maintenance window with no operating conflict."; }
    else { status = "NO_WINDOW"; notes = "No upcoming maintenance window is registered for this train. Add one in the train registry."; }
  }
  const job = {
    id: nextId(db.jobs), wheel_asset_id: wheelId, train_id: w.train_id, coach_id: w.coach_id, priority, risk_score: risk, job_status: "PENDING",
    recommended_action: db.history[wheelId][0].recommended_action, trend_status: db.history[wheelId][0].trend_status,
    suggested_start: start, suggested_end: end, scheduling_status: status, requires_operational_clearance: clearance, scheduling_notes: notes, conflict_notes: conflicts,
  };
  db.jobs.push(job);
  return { ...clone(job), maintenance_job_id: job.id, duplicate_job: false };
}

/* =====================================================================
   REAL BACKEND
   ===================================================================== */
async function req(path, init) {
  let r;
  try { r = await fetch(BASE + path, init); } catch { throw new Error(`Cannot reach the backend at ${BASE}. Is it running?`); }
  if (!r.ok) {
    let detail = "";
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : j.detail ? JSON.stringify(j.detail) : ""; } catch { /* no body */ }
    throw fail(r.status, detail || `Backend returned ${r.status} for ${path}`);
  }
  return r.status === 204 ? null : r.json();
}
const send = (method, body) => ({ method, headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
const lag = async (fn, ms = 250) => { await sleep(ms); return clone(fn()); };

/* ---------- fleet and legacy dashboards ---------- */
export const getFleet = () => (MOCK ? lag(mockFleet, 350) : req("/api/fleet/dashboard"));
export const getDashboard = () => (MOCK ? lag(mockLegacyDashboard, 300) : req("/api/dashboard"));

/* ---------- trains, coaches, wheels ---------- */
export const getTrains = async () => (MOCK ? lag(() => db.trains, 200) : asList(await req("/api/trains")));
export async function createTrain(body) {
  if (!MOCK) return req("/api/trains", send("POST", body));
  await sleep(250);
  if (db.trains.some((t) => t.train_number === body.train_number)) throw fail(409, "A train with that number is already registered");
  const t = { id: nextId(db.trains), operational_status: "Active", ...body };
  db.trains.push(t);
  return clone(t);
}
export async function updateTrain(id, body) {
  if (!MOCK) return req(`/api/trains/${id}`, send("PATCH", body));
  await sleep(150);
  Object.assign(db.trains.find((t) => t.id === id), body);
  return clone(db.trains.find((t) => t.id === id));
}
export const getCoaches = async (trainId) => (MOCK ? lag(() => db.coaches.filter((c) => c.train_id === Number(trainId)), 150) : asList(await req(`/api/trains/${trainId}/coaches`)));
export async function createCoach(trainId, body) {
  if (!MOCK) return req(`/api/trains/${trainId}/coaches`, send("POST", body));
  await sleep(200);
  const c = { id: nextId(db.coaches), train_id: Number(trainId), ...body };
  db.coaches.push(c);
  return clone(c);
}
export async function createWheel(coachId, body) {
  if (!MOCK) return req(`/api/coaches/${coachId}/wheels`, send("POST", body));
  await sleep(200);
  return clone(addWheel({ coach_id: coachId, ...body }));
}
export const getWheels = async () => (MOCK ? lag(mockWheels, 250) : asList(await req("/api/wheels")));
export async function getTrainTree(trainId) {
  const [coaches, wheels] = await Promise.all([getCoaches(trainId), getWheels()]);
  return coaches.map((c) => ({ ...c, wheels: wheels.filter((w) => w.coach_id === c.id) }));
}

/* ---------- schedules ---------- */
export const getSchedules = async (trainId) => (MOCK ? lag(() => db.schedules.filter((s) => s.train_id === Number(trainId)), 150) : asList(await req(`/api/trains/${trainId}/schedules`)));
export async function createSchedule(trainId, body) {
  const b = { ...body, departure_datetime: withTime(body.departure_datetime), arrival_datetime: withTime(body.arrival_datetime) };
  if (!MOCK) return req(`/api/trains/${trainId}/schedules`, send("POST", b));
  await sleep(200);
  const s = { id: nextId(db.schedules), train_id: Number(trainId), status: "ACTIVE", ...b };
  db.schedules.push(s);
  return clone(s);
}
export async function updateSchedule(id, body) {
  if (!MOCK) return req(`/api/schedules/${id}`, send("PATCH", body));
  await sleep(150);
  Object.assign(db.schedules.find((s) => s.id === id), body);
  return clone(db.schedules.find((s) => s.id === id));
}

/* ---------- history ---------- */
export const getHistory = async (id) => (MOCK ? lag(() => db.history[id] || [], 250) : asList(await req(`/api/wheels/${id}/history`)));
export async function getServiceHistory(id) {
  if (MOCK) return lag(() => db.jobs.filter((j) => j.wheel_asset_id === id), 200);
  try { return asList(await req(`/api/maintenance/history/${id}`)).map(normJob); } catch { return []; }
}

/* ---------- inspection ---------- */
export async function inspect(file, wheelId, coachId) {
  if (MOCK) { await sleep(3000); return mockInspect(file, wheelId, coachId); }
  const fd = new FormData();
  fd.append("image", file);
  if (wheelId) fd.append("wheel_id", wheelId);
  if (coachId) fd.append("coach_id", coachId);
  const r = await fetch(BASE + "/api/inspect", { method: "POST", body: fd }).catch(() => null);
  if (!r) throw new Error(`Cannot reach the backend at ${BASE}. Is it running?`);
  if (!r.ok) {
    let detail = "";
    try { const j = await r.json(); detail = typeof j.detail === "string" ? j.detail : ""; } catch { /* no body */ }
    throw new Error(detail || `Inspection failed (${r.status}). Check that the backend is running.`);
  }
  return r.json();
}

/* ---------- maintenance planner ---------- */
export const getJobs = async () => (MOCK ? lag(() => db.jobs.map(normJob), 250) : asList(await req("/api/maintenance/jobs")).map(normJob));
export async function recommend(wheelId) {
  if (!MOCK) return normJob(await req(`/api/maintenance/recommend/${wheelId}`, { method: "POST" }));
  await sleep(600);
  return normJob(mockRecommend(wheelId));
}
export async function confirmJob(id) {
  if (!MOCK) return req(`/api/maintenance/jobs/${id}/confirm`, send("POST", {}));
  await sleep(300);
  const j = db.jobs.find((x) => x.id === id);
  const clash = db.jobs.some((o) => o.id !== id && o.wheel_asset_id === j.wheel_asset_id && ["SCHEDULED", "IN_PROGRESS"].includes(o.job_status) && j.suggested_start && overlaps(o.suggested_start, o.suggested_end, j.suggested_start, j.suggested_end));
  if (clash) throw fail(409, "Overlaps another confirmed job for this wheel");
  j.job_status = "SCHEDULED";
  return clone(j);
}
export async function setJobStatus(id, status) {
  if (!MOCK) return req(`/api/maintenance/jobs/${id}/status`, send("PATCH", { job_status: status, status }));
  await sleep(250);
  const j = db.jobs.find((x) => x.id === id);
  j.job_status = status;
  if (status === "COMPLETED") {
    const w = db.wheels.find((x) => x.asset_id === j.wheel_asset_id);
    if (w) w.status = "Healthy";
  }
  return clone(j);
}
