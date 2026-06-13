import { useEffect, useState } from 'react';
import { subscribeStatus, type SyncStatus } from '../lib/sync';

export function useSyncStatus(): SyncStatus {
  const [status, setStatus] = useState<SyncStatus>({
    remote: false,
    online: true,
    pending: 0,
    syncing: false,
    lastError: null,
    lastSyncedAt: null,
  });
  useEffect(() => subscribeStatus(setStatus), []);
  return status;
}
