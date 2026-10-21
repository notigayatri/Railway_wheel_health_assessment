# Wheel Health Assessment - Frontend

React + Vite dashboard for the Train-Wise Wheel Health Monitoring and Intelligent Maintenance Scheduling backend (v2.0).

## Run it (Windows)

You need Node.js LTS (nodejs.org) and the backend running.

1. Start the backend from the project root:

       venv\Scripts\activate
       python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

2. In a second terminal:

       cd frontend
       copy .env.example .env
       npm install
       npm run dev

3. Open http://localhost:5173

## Settings (.env)

- VITE_API_URL: where the backend runs (default http://127.0.0.1:8000)
- VITE_USE_MOCK: true shows simulated demo data without a backend (registering trains, inspecting and planning all work in memory); false uses the real API

Restart `npm run dev` after changing .env.

## Pages

- Dashboard: fleet totals, health bar, train health, upcoming maintenance, schedule conflicts, critical wheels
- Trains: register trains, coaches and wheels; schedule and availability lanes for the next 7 days
- New inspection: pick Train, Coach, Wheel, upload an image; YOLO, severity, reliability and Grad-CAM results, then generate a maintenance plan
- Maintenance planner: priority queue, suggested windows, conflict and operational-hold flags, confirm and lifecycle actions
- Wheel history: per-wheel risk trend, inspection timeline and maintenance history

All fleet data is simulated and all maintenance dates are rule-based recommendations, not certified railway safety decisions.
