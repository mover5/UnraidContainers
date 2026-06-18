import { useState, type KeyboardEvent } from 'react';

// Chip editor for the list of people on a flight. Type a name + Enter/comma to
// add, tap × to remove, or tap a suggestion chip. Names are de-duplicated
// case-insensitively so "mark" and "Mark" don't both stick.
export default function PassengerEditor({
  value,
  onChange,
  suggestions = [],
  placeholder = 'Add person…',
}: {
  value: string[];
  onChange: (next: string[]) => void;
  suggestions?: string[];
  placeholder?: string;
}) {
  const [draft, setDraft] = useState('');

  const has = (name: string) => value.some((p) => p.toLowerCase() === name.toLowerCase());

  const add = (raw: string) => {
    const name = raw.trim();
    setDraft('');
    if (name && !has(name)) onChange([...value, name]);
  };
  const remove = (name: string) => onChange(value.filter((p) => p !== name));

  const onKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter' || e.key === ',') {
      e.preventDefault();
      add(draft);
    } else if (e.key === 'Backspace' && !draft && value.length) {
      remove(value[value.length - 1]);
    }
  };

  const remaining = suggestions.filter((s) => !has(s));

  return (
    <div>
      <div className="flex flex-wrap items-center gap-1.5 rounded-xl border border-edge bg-ink p-2 focus-within:border-sky">
        {value.map((p) => (
          <span key={p} className="chip gap-1 bg-panel2 text-slate-200">
            {p}
            <button
              type="button"
              onClick={() => remove(p)}
              className="text-base leading-none text-muted hover:text-bad"
              aria-label={`Remove ${p}`}
            >
              ×
            </button>
          </span>
        ))}
        <input
          className="min-w-[8ch] flex-1 bg-transparent px-1 py-0.5 text-sm text-slate-100 placeholder:text-slate-500 focus:outline-none"
          list="ft-people-suggestions"
          value={draft}
          placeholder={value.length ? '' : placeholder}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => add(draft)}
        />
        <datalist id="ft-people-suggestions">
          {remaining.map((s) => (
            <option key={s} value={s} />
          ))}
        </datalist>
      </div>
      {remaining.length > 0 && (
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {remaining.map((s) => (
            <button
              key={s}
              type="button"
              onClick={() => add(s)}
              className="chip border border-edge text-muted hover:border-sky hover:text-sky"
            >
              + {s}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
