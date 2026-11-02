// tasks.test.js — integration tests for the legacy Task API (node:test + supertest-free via fetch).
import { test, before, after, beforeEach } from 'node:test';
import assert from 'node:assert/strict';
import { createApp } from '../src/app.js';
import { _resetForTests, seedIfEmpty } from '../src/store.js';

let server;
let base;

before(async () => {
  const app = createApp();
  await new Promise((resolve) => {
    server = app.listen(0, '127.0.0.1', resolve);
  });
  const { port } = server.address();
  base = `http://127.0.0.1:${port}`;
});

after(() => server && server.close());

beforeEach(() => {
  _resetForTests();
  seedIfEmpty();
});

const api = (path, opts) => fetch(base + path, opts);
const json = (body) => ({ headers: { 'content-type': 'application/json' }, body: JSON.stringify(body) });

test('health returns ok', async () => {
  const r = await api('/api/health');
  assert.equal(r.status, 200);
  assert.deepEqual(await r.json(), { ok: true });
});

test('seed produces the 4 life-admin tasks', async () => {
  const tasks = await (await api('/api/tasks')).json();
  assert.equal(tasks.length, 4);
  const titles = tasks.map((t) => t.title);
  assert.ok(titles.some((t) => t.includes('lawn-mower')));
  assert.ok(titles.some((t) => t.includes('CPA')));
});

test('create a task', async () => {
  const r = await api('/api/tasks', { method: 'POST', ...json({ title: 'Renew passport', priority: 'low' }) });
  assert.equal(r.status, 201);
  const t = await r.json();
  assert.equal(t.title, 'Renew passport');
  assert.equal(t.priority, 'low');
  assert.equal(t.status, 'open');
  assert.ok(t.id);
});

test('create rejects missing title', async () => {
  const r = await api('/api/tasks', { method: 'POST', ...json({ priority: 'low' }) });
  assert.equal(r.status, 400);
});

test('create rejects bad priority', async () => {
  const r = await api('/api/tasks', { method: 'POST', ...json({ title: 'x', priority: 'urgent' }) });
  assert.equal(r.status, 400);
});

test('complete then reopen a task keeps completedAt consistent', async () => {
  const list = await (await api('/api/tasks')).json();
  const id = list[0].id;

  const done = await (await api(`/api/tasks/${id}/complete`, { method: 'POST' })).json();
  assert.equal(done.status, 'done');
  assert.ok(done.completedAt);

  const open = await (await api(`/api/tasks/${id}/reopen`, { method: 'POST' })).json();
  assert.equal(open.status, 'open');
  assert.equal(open.completedAt, null);
});

test('patch updates fields', async () => {
  const list = await (await api('/api/tasks')).json();
  const id = list[0].id;
  const r = await api(`/api/tasks/${id}`, { method: 'PATCH', ...json({ priority: 'low', notes: 'later' }) });
  const t = await r.json();
  assert.equal(t.priority, 'low');
  assert.equal(t.notes, 'later');
});

test('delete removes a task', async () => {
  const list = await (await api('/api/tasks')).json();
  const id = list[0].id;
  const del = await api(`/api/tasks/${id}`, { method: 'DELETE' });
  assert.equal(del.status, 204);
  const after = await api(`/api/tasks/${id}`);
  assert.equal(after.status, 404);
});

test('seed tasks carry descriptions', async () => {
  const tasks = await (await api('/api/tasks')).json();
  const lawn = tasks.find((t) => t.title.includes('lawn-mower'));
  assert.ok(lawn.description && lawn.description.includes('Ortega'));
});

test('create and patch a task description', async () => {
  const r = await api('/api/tasks', {
    method: 'POST',
    ...json({ title: 'Pay gardener', description: 'Pay Ortega $150' }),
  });
  const t = await r.json();
  assert.equal(t.description, 'Pay Ortega $150');

  const upd = await (await api(`/api/tasks/${t.id}`, {
    method: 'PATCH',
    ...json({ description: 'Pay Ortega $175 (rate went up)' }),
  })).json();
  assert.equal(upd.description, 'Pay Ortega $175 (rate went up)');
});

test('404 for unknown id', async () => {
  const r = await api('/api/tasks/does-not-exist');
  assert.equal(r.status, 404);
});
