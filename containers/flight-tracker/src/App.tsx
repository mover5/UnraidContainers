import { NavLink, Route, Routes } from 'react-router-dom';
import { FlightsProvider } from './hooks/useFlights';
import Dashboard from './pages/Dashboard';
import Flights from './pages/Flights';
import FlightDetail from './pages/FlightDetail';
import AddFlight from './pages/AddFlight';
import { IconChart, IconList, IconPlus, IconPlane } from './components/icons';
import SyncBadge from './components/SyncBadge';

const nav = [
  { to: '/', label: 'Dashboard', icon: IconChart, end: true },
  { to: '/flights', label: 'Flights', icon: IconList, end: false },
  { to: '/add', label: 'Add', icon: IconPlus, end: false },
];

export default function App() {
  return (
    <FlightsProvider>
      <div className="min-h-full pb-20 md:pb-0 md:pl-56">
        {/* Sidebar (desktop) */}
        <aside className="hidden md:flex fixed inset-y-0 left-0 w-56 flex-col gap-1 border-r border-edge bg-panel p-4">
          <div className="flex items-center gap-2 px-2 pb-4 text-lg font-semibold">
            <IconPlane className="h-6 w-6 text-sky" />
            Flight Tracker
          </div>
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-xl px-3 py-2 text-sm font-medium ${
                  isActive ? 'bg-panel2 text-sky' : 'text-slate-300 hover:bg-panel2'
                }`
              }
            >
              <n.icon className="h-5 w-5" />
              {n.label}
            </NavLink>
          ))}
          <div className="mt-auto px-2 pt-4">
            <SyncBadge />
          </div>
        </aside>

        {/* Mobile top bar */}
        <header className="md:hidden sticky top-0 z-10 flex items-center justify-between border-b border-edge bg-panel/95 px-4 py-3 backdrop-blur">
          <div className="flex items-center gap-2 font-semibold">
            <IconPlane className="h-5 w-5 text-sky" />
            Flight Tracker
          </div>
          <SyncBadge compact />
        </header>

        <main className="mx-auto max-w-5xl px-4 py-5 md:py-8">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/flights" element={<Flights />} />
            <Route path="/flights/:id" element={<FlightDetail />} />
            <Route path="/add" element={<AddFlight />} />
          </Routes>
        </main>

        {/* Bottom nav (mobile) */}
        <nav className="md:hidden fixed inset-x-0 bottom-0 z-10 grid grid-cols-3 border-t border-edge bg-panel/95 backdrop-blur">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              end={n.end}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 py-2.5 text-[11px] ${
                  isActive ? 'text-sky' : 'text-slate-400'
                }`
              }
            >
              <n.icon className="h-5 w-5" />
              {n.label}
            </NavLink>
          ))}
        </nav>
      </div>
    </FlightsProvider>
  );
}
