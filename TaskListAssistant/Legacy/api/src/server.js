// server.js — bootstrap: seed the store and start listening.
import { createApp } from './app.js';
import { seedIfEmpty } from './store.js';

const PORT = process.env.PORT || 4000;

seedIfEmpty();

const app = createApp();
app.listen(PORT, '127.0.0.1', () => {
  console.log(`Legacy Task API listening on http://127.0.0.1:${PORT}`);
});
