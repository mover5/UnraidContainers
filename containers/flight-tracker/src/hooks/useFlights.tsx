import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from 'react';
import { store, subscribe } from '../lib/store';
import type { Flight } from '../lib/types';

interface FlightsCtx {
  flights: Flight[];
  loading: boolean;
  error: string | null;
  reload: () => Promise<void>;
}

const Ctx = createContext<FlightsCtx | null>(null);

export function FlightsProvider({ children }: { children: ReactNode }) {
  const [flights, setFlights] = useState<Flight[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setError(null);
      const data = await store.listFlights();
      setFlights(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load flights');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    // Refresh whenever the cache changes (local writes or a background pull).
    return subscribe(reload);
  }, [reload]);

  return <Ctx.Provider value={{ flights, loading, error, reload }}>{children}</Ctx.Provider>;
}

export function useFlights() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useFlights must be used within FlightsProvider');
  return ctx;
}
