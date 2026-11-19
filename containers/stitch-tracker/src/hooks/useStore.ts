import { useEffect, useRef, useState, useSyncExternalStore } from 'react';
import * as store from '../lib/store.ts';
import { getStatus, subscribeStatus } from '../lib/sync.ts';

export const useProjects = () => useSyncExternalStore(store.subscribe, store.getProjects);

export function useProject(id: string | undefined) {
  const projects = useProjects();
  return projects.find((p) => p.id === id) ?? null;
}

export const useSyncStatus = () => useSyncExternalStore(subscribeStatus, getStatus);

/** Keep the screen on while `enabled` (re-acquired when the tab becomes visible again). */
export function useWakeLock(enabled: boolean) {
  const supported = typeof navigator !== 'undefined' && 'wakeLock' in navigator;
  const [active, setActive] = useState(false);
  const lock = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!supported || !enabled) return;
    let cancelled = false;
    const acquire = async () => {
      try {
        const l = await navigator.wakeLock.request('screen');
        if (cancelled) return void l.release();
        lock.current = l;
        setActive(true);
        l.addEventListener('release', () => setActive(false));
      } catch {
        setActive(false); // denied (e.g. battery saver) — not fatal
      }
    };
    const onVisible = () => document.visibilityState === 'visible' && void acquire();
    void acquire();
    document.addEventListener('visibilitychange', onVisible);
    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisible);
      void lock.current?.release();
      lock.current = null;
      setActive(false);
    };
  }, [enabled, supported]);

  return { supported, active };
}
