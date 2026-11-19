import { Link, Route, Routes } from 'react-router-dom';
import { SyncBadge } from './components/ui';
import Projects from './pages/Projects';
import Knit from './pages/Knit';
import EditProject from './pages/EditProject';
import NewProject from './pages/NewProject';

export default function App() {
  return (
    <div className="min-h-screen pb-[env(safe-area-inset-bottom)]">
      <header className="sticky top-0 z-20 border-b border-edge bg-ink/90 pt-[env(safe-area-inset-top)] backdrop-blur">
        <div className="mx-auto flex max-w-2xl items-center justify-between px-4 py-3">
          <Link to="/" className="flex items-center gap-2">
            <img src="/favicon.svg" alt="" className="h-7 w-7" />
            <span className="heading text-lg">Stitch Tracker</span>
          </Link>
          <SyncBadge />
        </div>
      </header>
      <main className="mx-auto max-w-2xl px-4 py-5">
        <Routes>
          <Route path="/" element={<Projects />} />
          <Route path="/new" element={<NewProject />} />
          <Route path="/p/:id" element={<Knit />} />
          <Route path="/p/:id/edit" element={<EditProject />} />
          <Route path="*" element={<Projects />} />
        </Routes>
      </main>
    </div>
  );
}
