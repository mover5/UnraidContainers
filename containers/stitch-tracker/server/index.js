import { fileURLToPath } from 'node:url';
import { createApp, openDb } from './app.js';

const PORT = Number(process.env.PORT || 8080);
const DB_PATH = process.env.DB_PATH || '/data/stitch.db';
const PUBLIC_DIR = process.env.PUBLIC_DIR || fileURLToPath(new URL('./public', import.meta.url));

const db = openDb(DB_PATH);
createApp(db, PUBLIC_DIR).listen(PORT, () => {
  console.log(`Stitch Tracker listening on :${PORT} (db: ${DB_PATH})`);
});

for (const sig of ['SIGINT', 'SIGTERM']) {
  process.on(sig, () => {
    db.close();
    process.exit(0);
  });
}
