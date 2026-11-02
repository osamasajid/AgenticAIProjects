// store.js — SQLite persistence for the Legacy Task Manager.
// Tasks are the system of record; the agentic app reads/writes them via the REST API.
import Database from 'better-sqlite3';
import { randomUUID } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const __dirname = dirname(fileURLToPath(import.meta.url));
const DB_PATH = process.env.LEGACY_DB_PATH || join(__dirname, '..', 'tasks.db');

const VALID_PRIORITY = new Set(['high', 'medium', 'low']);
const VALID_STATUS = new Set(['open', 'done']);
const VALID_CATEGORY = new Set(['financial', 'routine', 'general', null]);

const db = new Database(DB_PATH);
db.pragma('journal_mode = WAL');

db.exec(`
  CREATE TABLE IF NOT EXISTS tasks (
    id          TEXT PRIMARY KEY,
    title       TEXT NOT NULL,
    description TEXT,
    priority    TEXT NOT NULL DEFAULT 'medium',
    dueDate     TEXT,
    category    TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    notes       TEXT,
    createdAt   TEXT NOT NULL,
    completedAt TEXT
  );
`);

// Lightweight migration: add `description` to a pre-existing DB that lacks it.
const cols = db.prepare(`PRAGMA table_info(tasks)`).all().map((c) => c.name);
if (!cols.includes('description')) {
  db.exec(`ALTER TABLE tasks ADD COLUMN description TEXT`);
}

// ---- Seed data: the four life-admin tasks shared with the agentic demo ----
function isoDaysFromNow(days) {
  const d = new Date();
  d.setDate(d.getDate() + days);
  return d.toISOString().slice(0, 10);
}

const SEED = [
  { title: 'Make payment to lawn-mower', description: 'Pay Ortega $150 for the September lawn service.', priority: 'high', dueDate: isoDaysFromNow(1), category: 'financial' },
  { title: 'Book appointment with childcare nanny for next Saturday', description: 'Call Maria to book Saturday 9am–1pm. Bookings fill up fast.', priority: 'high', dueDate: isoDaysFromNow(7), category: 'routine' },
  { title: 'See if electricity bill is available, pay it', description: 'Check the utility portal for this month\'s bill; pay if available.', priority: 'medium', dueDate: null, category: 'financial' },
  { title: 'Send bank statement to CPA for tax filing', description: 'Send last 3 months of statements to the CPA for the tax return.', priority: 'medium', dueDate: isoDaysFromNow(14), category: 'financial' },
];

export function seedIfEmpty() {
  const count = db.prepare('SELECT COUNT(*) AS n FROM tasks').get().n;
  if (count > 0) return;
  const now = new Date().toISOString();
  const insert = db.prepare(`
    INSERT INTO tasks (id, title, description, priority, dueDate, category, status, notes, createdAt, completedAt)
    VALUES (@id, @title, @description, @priority, @dueDate, @category, 'open', NULL, @createdAt, NULL)
  `);
  const tx = db.transaction((rows) => {
    for (const r of rows) {
      insert.run({ id: randomUUID(), createdAt: now, notes: null, ...r });
    }
  });
  tx(SEED);
}

// ---- Validation ----
export class ValidationError extends Error {}

function validateForCreate(body) {
  if (!body || typeof body.title !== 'string' || body.title.trim() === '') {
    throw new ValidationError('title is required');
  }
  if (body.priority !== undefined && !VALID_PRIORITY.has(body.priority)) {
    throw new ValidationError(`priority must be one of ${[...VALID_PRIORITY].join(', ')}`);
  }
  if (body.category !== undefined && !VALID_CATEGORY.has(body.category)) {
    throw new ValidationError(`category must be one of financial, routine, general, or null`);
  }
}

function validateForUpdate(body) {
  if (body.priority !== undefined && !VALID_PRIORITY.has(body.priority)) {
    throw new ValidationError(`priority must be one of ${[...VALID_PRIORITY].join(', ')}`);
  }
  if (body.status !== undefined && !VALID_STATUS.has(body.status)) {
    throw new ValidationError(`status must be one of ${[...VALID_STATUS].join(', ')}`);
  }
  if (body.category !== undefined && !VALID_CATEGORY.has(body.category)) {
    throw new ValidationError(`category must be one of financial, routine, general, or null`);
  }
}

// ---- CRUD ----
export function listTasks({ status, priority, category, sort } = {}) {
  let sql = 'SELECT * FROM tasks';
  const where = [];
  const params = {};
  if (status) { where.push('status = @status'); params.status = status; }
  if (priority) { where.push('priority = @priority'); params.priority = priority; }
  if (category) { where.push('category = @category'); params.category = category; }
  if (where.length) sql += ' WHERE ' + where.join(' AND ');

  const sortMap = {
    dueDate: 'dueDate IS NULL, dueDate ASC',
    priority: `CASE priority WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END ASC`,
    status: 'status ASC',
    createdAt: 'createdAt DESC',
  };
  sql += ' ORDER BY ' + (sortMap[sort] || 'createdAt DESC');
  return db.prepare(sql).all(params);
}

export function getTask(id) {
  return db.prepare('SELECT * FROM tasks WHERE id = ?').get(id) || null;
}

export function createTask(body) {
  validateForCreate(body);
  const task = {
    id: randomUUID(),
    title: body.title.trim(),
    description: body.description ?? null,
    priority: body.priority || 'medium',
    dueDate: body.dueDate || null,
    category: body.category ?? null,
    status: 'open',
    notes: body.notes ?? null,
    createdAt: new Date().toISOString(),
    completedAt: null,
  };
  db.prepare(`
    INSERT INTO tasks (id, title, description, priority, dueDate, category, status, notes, createdAt, completedAt)
    VALUES (@id, @title, @description, @priority, @dueDate, @category, @status, @notes, @createdAt, @completedAt)
  `).run(task);
  return task;
}

export function updateTask(id, body) {
  const existing = getTask(id);
  if (!existing) return null;
  validateForUpdate(body);
  const fields = ['title', 'description', 'priority', 'dueDate', 'category', 'status', 'notes'];
  const next = { ...existing };
  for (const f of fields) {
    if (body[f] !== undefined) next[f] = body[f];
  }
  // keep completedAt consistent with status
  if (body.status === 'done' && !existing.completedAt) next.completedAt = new Date().toISOString();
  if (body.status === 'open') next.completedAt = null;
  db.prepare(`
    UPDATE tasks SET title=@title, description=@description, priority=@priority, dueDate=@dueDate,
      category=@category, status=@status, notes=@notes, completedAt=@completedAt
    WHERE id=@id
  `).run(next);
  return getTask(id);
}

export function completeTask(id) {
  const existing = getTask(id);
  if (!existing) return null;
  db.prepare('UPDATE tasks SET status=?, completedAt=? WHERE id=?')
    .run('done', new Date().toISOString(), id);
  return getTask(id);
}

export function reopenTask(id) {
  const existing = getTask(id);
  if (!existing) return null;
  db.prepare('UPDATE tasks SET status=?, completedAt=NULL WHERE id=?').run('open', id);
  return getTask(id);
}

export function deleteTask(id) {
  const info = db.prepare('DELETE FROM tasks WHERE id = ?').run(id);
  return info.changes > 0;
}

export function _resetForTests() {
  db.exec('DELETE FROM tasks');
}

export default db;
