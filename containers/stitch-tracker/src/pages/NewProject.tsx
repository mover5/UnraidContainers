import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import ProjectForm, { type FormValue } from '../components/ProjectForm';
import { createProject } from '../lib/store.ts';
import { IconBack } from '../components/icons';

export default function NewProject() {
  const nav = useNavigate();
  const [form, setForm] = useState<FormValue>({ name: '', description: '', notes: '', colors: [], steps: [] });

  const create = () => {
    const p = createProject({ ...form, name: form.name.trim() || 'Untitled project' });
    nav(`/p/${p.id}`, { replace: true });
  };

  return (
    <div className="space-y-4 pb-24">
      <div className="flex items-center gap-2">
        <Link to="/" className="btn-icon -ml-2" aria-label="Back">
          <IconBack className="h-5 w-5" />
        </Link>
        <h1 className="heading text-2xl">New project</h1>
      </div>

      <ProjectForm value={form} onChange={(patch) => setForm((f) => ({ ...f, ...patch }))} startWithPaste />

      <div className="fixed inset-x-0 bottom-0 z-10 border-t border-edge bg-ink/95 pb-[env(safe-area-inset-bottom)] backdrop-blur">
        <div className="mx-auto flex max-w-2xl gap-2 px-4 py-3">
          <Link to="/" className="btn-ghost">
            Cancel
          </Link>
          <button className="btn-primary flex-1" onClick={create} disabled={!form.name.trim()}>
            Create project
          </button>
        </div>
      </div>
    </div>
  );
}
