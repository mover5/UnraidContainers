import { useState } from 'react';
import { Link } from 'react-router-dom';
import { useProjects } from '../hooks/useStore';
import { colorById, position } from '../lib/pattern.ts';
import { updatedAt } from '../lib/merge.ts';
import type { Project } from '../lib/types.ts';
import { ColorPill, EmptyState, StripeBar, Swatch } from '../components/ui';
import { IconPlus } from '../components/icons';

export default function Projects() {
  const projects = useProjects();
  const [showFinished, setShowFinished] = useState(false);
  const byRecent = (a: Project, b: Project) => updatedAt(b) - updatedAt(a);
  const active = projects.filter((p) => p.status === 'active').sort(byRecent);
  const finished = projects.filter((p) => p.status === 'finished').sort(byRecent);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <h1 className="heading text-2xl">Projects</h1>
        <Link to="/new" className="btn-primary">
          <IconPlus className="h-4 w-4" /> New project
        </Link>
      </div>

      {projects.length === 0 && (
        <EmptyState
          title="Nothing on the needles yet"
          hint="Add a project, paste in your pattern, and tap through it a row at a time."
        >
          <Link to="/new" className="btn-primary">
            Start a project
          </Link>
        </EmptyState>
      )}

      {active.length > 0 && (
        <div className="space-y-3">
          {active.map((p) => (
            <ProjectCard key={p.id} project={p} />
          ))}
        </div>
      )}

      {active.length === 0 && finished.length > 0 && (
        <p className="text-sm text-muted">No projects in progress.</p>
      )}

      {finished.length > 0 && (
        <div>
          <button className="text-sm font-medium text-muted hover:text-cream" onClick={() => setShowFinished((v) => !v)}>
            {showFinished ? '▾' : '▸'} Finished ({finished.length})
          </button>
          {showFinished && (
            <div className="mt-3 space-y-3">
              {finished.map((p) => (
                <ProjectCard key={p.id} project={p} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ProjectCard({ project: p }: { project: Project }) {
  const pos = position(p);
  const color = colorById(p.colors, pos.step?.color_id ?? null);
  const pct = pos.total ? Math.round((Math.min(p.rows_done, pos.total) / pos.total) * 100) : null;
  return (
    <Link to={`/p/${p.id}`} className="card block p-4 transition hover:border-wool/60 active:scale-[0.99]">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <div className="heading truncate text-lg">{p.name || 'Untitled project'}</div>
          {p.description && <div className="mt-0.5 line-clamp-2 text-sm text-muted">{p.description}</div>}
        </div>
        {p.status === 'finished' ? (
          <span className="shrink-0 rounded-full bg-sage/15 px-2.5 py-1 text-xs font-medium text-sage">Finished</span>
        ) : (
          color && <ColorPill color={color} className="shrink-0 !px-2.5 !py-0.5 !text-xs" />
        )}
      </div>
      <div className="mt-3">
        <StripeBar project={p} />
      </div>
      <div className="mt-2 flex items-center justify-between text-xs text-muted">
        <span className="tabular-nums">
          {pos.total
            ? `${Math.min(p.rows_done, pos.total)} / ${pos.total} rows · ${pct}%`
            : `${p.rows_done} rows knitted`}
        </span>
        {p.colors.length > 0 && (
          <span className="flex -space-x-1">
            {p.colors.slice(0, 8).map((c) => (
              <Swatch key={c.id} color={c} size="sm" />
            ))}
          </span>
        )}
      </div>
    </Link>
  );
}
