// app.js — Express app implementing the REST contract from the legacy design doc.
import express from 'express';
import cors from 'cors';
import * as store from './store.js';

export function createApp() {
  const app = express();
  app.use(cors());
  app.use(express.json());

  app.get('/api/health', (_req, res) => res.json({ ok: true }));

  // List (with optional filters + sort)
  app.get('/api/tasks', (req, res) => {
    const { status, priority, category, sort } = req.query;
    res.json(store.listTasks({ status, priority, category, sort }));
  });

  // Get one
  app.get('/api/tasks/:id', (req, res) => {
    const task = store.getTask(req.params.id);
    if (!task) return res.status(404).json({ error: 'not found' });
    res.json(task);
  });

  // Create
  app.post('/api/tasks', (req, res) => {
    try {
      res.status(201).json(store.createTask(req.body));
    } catch (e) {
      if (e instanceof store.ValidationError) return res.status(400).json({ error: e.message });
      throw e;
    }
  });

  // Update (partial)
  app.patch('/api/tasks/:id', (req, res) => {
    try {
      const updated = store.updateTask(req.params.id, req.body);
      if (!updated) return res.status(404).json({ error: 'not found' });
      res.json(updated);
    } catch (e) {
      if (e instanceof store.ValidationError) return res.status(400).json({ error: e.message });
      throw e;
    }
  });

  // Complete
  app.post('/api/tasks/:id/complete', (req, res) => {
    const t = store.completeTask(req.params.id);
    if (!t) return res.status(404).json({ error: 'not found' });
    res.json(t);
  });

  // Reopen
  app.post('/api/tasks/:id/reopen', (req, res) => {
    const t = store.reopenTask(req.params.id);
    if (!t) return res.status(404).json({ error: 'not found' });
    res.json(t);
  });

  // Delete
  app.delete('/api/tasks/:id', (req, res) => {
    const ok = store.deleteTask(req.params.id);
    if (!ok) return res.status(404).json({ error: 'not found' });
    res.status(204).end();
  });

  return app;
}
