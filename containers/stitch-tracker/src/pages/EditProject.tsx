import { Link, useNavigate, useParams } from 'react-router-dom';
import { useProject } from '../hooks/useStore';
import ProjectForm from '../components/ProjectForm';
import { deleteProject, updateProject } from '../lib/store.ts';
import { totalRows } from '../lib/pattern.ts';
import { EmptyState, NumberField } from '../components/ui';
import { IconBack, IconTrash } from '../components/icons';

export default function EditProject() {
  const { id } = useParams();
  const nav = useNavigate();
  const p = useProject(id);
  if (!p) {
    return (
      <EmptyState title="Project not found">
        <Link to="/" className="btn-ghost">
          Back to projects
        </Link>
      </EmptyState>
    );
  }
  const total = totalRows(p);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-2">
        <Link to={`/p/${p.id}`} className="btn-icon -ml-2" aria-label="Back to knitting">
          <IconBack className="h-5 w-5" />
        </Link>
        <h1 className="heading flex-1 text-2xl">Edit project</h1>
        <Link to={`/p/${p.id}`} className="btn-primary !py-1.5">
          Done
        </Link>
      </div>
      <p className="-mt-2 text-xs text-muted">Changes save automatically, even offline.</p>

      <ProjectForm value={p} onChange={(patch) => updateProject(p.id, patch)} />

      <section className="card space-y-4 p-4">
        <h2 className="heading">Progress</h2>
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted">Rows completed</span>
          <NumberField
            className="input w-24 !py-1.5 text-center tabular-nums"
            value={p.rows_done}
            onChange={(n) => updateProject(p.id, { rows_done: n })}
            aria-label="Rows completed"
          />
          {total > 0 && <span className="text-muted">of {total}</span>}
        </div>
        <div className="flex gap-2">
          {(['active', 'finished'] as const).map((s) => (
            <button
              key={s}
              className={p.status === s ? 'btn-primary flex-1' : 'btn-ghost flex-1'}
              onClick={() => updateProject(p.id, { status: s })}
            >
              {s === 'active' ? 'In progress' : 'Finished'}
            </button>
          ))}
        </div>
      </section>

      <button
        className="btn w-full text-bad hover:bg-bad/10"
        onClick={() => {
          if (confirm(`Delete “${p.name}”? This removes it from every device.`)) {
            deleteProject(p.id);
            nav('/', { replace: true });
          }
        }}
      >
        <IconTrash className="h-4 w-4" /> Delete project
      </button>
    </div>
  );
}
