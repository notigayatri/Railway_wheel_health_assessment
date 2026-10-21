import { NavLink, Route, Routes, useLocation } from "react-router-dom";
import Dashboard from "./pages/Dashboard.jsx";
import Trains from "./pages/Trains.jsx";
import Inspect from "./pages/Inspect.jsx";
import Planner from "./pages/Planner.jsx";
import Wheels from "./pages/Wheels.jsx";
import { MOCK } from "./api.js";

export default function App() {
  const loc = useLocation();
  return (
    <div className="shell">
      <aside className="side">
        <div className="brand">
          <svg viewBox="0 0 40 40" width="42" height="42" aria-hidden="true">
            <defs><linearGradient id="lg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#3C948C" /><stop offset="1" stopColor="#1F5F63" /></linearGradient></defs>
            <rect width="40" height="40" rx="12" fill="url(#lg)" />
            <circle cx="20" cy="20" r="11" fill="none" stroke="#fff" strokeWidth="3" />
            <path className="pulse" d="M5 21h9l3-8 4 15 3-9h11" fill="none" stroke="#F3E3B0" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <span>Wheel Health<small>Fleet maintenance system</small></span>
        </div>
        <nav>
          <NavLink to="/" end>Dashboard</NavLink>
          <NavLink to="/trains">Trains</NavLink>
          <NavLink to="/inspect">New inspection</NavLink>
          <NavLink to="/planner">Maintenance planner</NavLink>
          <NavLink to="/wheels">Wheel history</NavLink>
        </nav>
        <div className="mock">
          {MOCK && <p>Demo mode. Connect the backend by setting VITE_USE_MOCK=false.</p>}
          <p>Simulated fleet data. Maintenance dates are rule-based recommendations, not certified safety decisions.</p>
        </div>
      </aside>
      <main key={loc.pathname} className="page">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/trains" element={<Trains />} />
          <Route path="/inspect" element={<Inspect />} />
          <Route path="/planner" element={<Planner />} />
          <Route path="/wheels" element={<Wheels />} />
        </Routes>
      </main>
    </div>
  );
}
