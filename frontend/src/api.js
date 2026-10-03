const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";
export const MOCK = import.meta.env.VITE_USE_MOCK !== "false";
export const imgUrl = (p) => (p ? BASE + p : null);
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/* ---------- mock data (same shape as the backend guide) ---------- */
const wheels = [
  { asset_id: "WH000001", status: "Monitor", inspection_count: 3, latest_inspection: "2026-10-03T13:17:24", train_id: null, coach_id: null },
  { asset_id: "WH000002", status: "Critical", inspection_count: 2, latest_inspection: "2026-10-02T09:40:10", train_id: null, coach_id: null },
  { asset_id: "WH000003", status: "Healthy", inspection_count: 1, latest_inspection: "2026-09-30T16:05:51", train_id: null, coach_id: null },
];
const history = (id) => [
  { inspection_date: "2026-10-03T13:17:24", label: "Shelling", severity: "Moderate", risk_score: 52, trend_status: "WORSENING", recommended_action: "Schedule maintenance" },
  { inspection_date: "2026-09-28T10:02:00", label: "Shelling", severity: "Mild", risk_score: 31, trend_status: "STABLE", recommended_action: "Monitor only" },
  { inspection_date: "2026-09-20T08:30:00", label: "Cracks-Scratches", severity: "Mild", risk_score: 24, trend_status: "FIRST_INSPECTION", recommended_action: "Monitor only" },
];
const mockDashboard = {
  total_wheels: 3, total_inspections: 6, healthy: 1, monitor: 1, critical: 1,
  severity_distribution: { Mild: 3, Moderate: 2, Severe: 1 },
  defect_distribution: { Shelling: 3, "Cracks-Scratches": 3 },
  recent_inspections: history().map((h, i) => ({ ...h, asset_id: wheels[i].asset_id })),
};
const mockInspect = (file, wheelId) => ({
  inspection_id: "INS-" + Date.now(), asset_id: wheelId || "WH000004", image_name: file.name,
  inspection_date: new Date().toISOString(), trend_status: "WORSENING", wheel_risk_score: 74,
  wheel_recommended_action: "Immediate inspection", total_defects_detected: 2, processing_time_seconds: 2.4,
  annotated_image_url: null, gradcam_image_url: null,
  defects: [
    { label: "Shelling", confidence: 0.91, severity: "Severe", mean_confidence: 0.88, std_deviation: 0.03, reliability: "HIGH", risk_score: 74, recommended_action: "Immediate inspection", trend_note: "Severity is above the historical average for Shelling on this wheel." },
    { label: "Cracks-Scratches", confidence: 0.72, severity: "Mild", mean_confidence: 0.64, std_deviation: 0.11, reliability: "MEDIUM", risk_score: 33, recommended_action: "Monitor only", trend_note: "First time this defect type was seen on this wheel." },
  ],
});

/* ---------- real calls ---------- */
async function get(path) {
  const r = await fetch(BASE + path);
  if (!r.ok) throw new Error(`Backend returned ${r.status} for ${path}`);
  return r.json();
}
export const getDashboard = async () => (MOCK ? (await sleep(300), mockDashboard) : get("/api/dashboard"));
export const getWheels = async () => (MOCK ? (await sleep(300), wheels) : get("/api/wheels"));
export const getHistory = async (id) => (MOCK ? (await sleep(250), history(id)) : get(`/api/wheels/${id}/history`));
export async function inspect(file, wheelId) {
  if (MOCK) { await sleep(3000); return mockInspect(file, wheelId); }
  const fd = new FormData();
  fd.append("image", file);
  if (wheelId) fd.append("wheel_id", wheelId);
  const r = await fetch(BASE + "/api/inspect", { method: "POST", body: fd });
  if (!r.ok) throw new Error(`Inspection failed (${r.status}). Check that the backend is running.`);
  return r.json();
}
