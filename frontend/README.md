# Wheel Health Assessment - Frontend

React + Vite dashboard for the Railway Wheel Health Assessment backend.

## Run it (Windows)

You need Node.js LTS (nodejs.org) and the backend running.

1. Start the backend from the project root (see the main README):

       venv\Scripts\activate
       python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

2. In a second terminal:

       cd frontend
       copy .env.example .env
       npm install
       npm run dev

3. Open http://localhost:5173

## Settings (.env)

- VITE_API_URL: where the backend runs (default http://localhost:8000)
- VITE_USE_MOCK: true shows demo data without a backend; false uses the real API

Restart `npm run dev` after changing .env.

## Pages

Dashboard, New inspection (upload an image, optional Wheel ID), Wheels (list and history).
