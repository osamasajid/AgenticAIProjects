// api.js — thin client for the Legacy Task API (proxied at /api in dev).
const base = '/api';

async function req(path, opts) {
  const res = await fetch(base + path, opts);
  if (res.status === 204) return null;
  if (!res.ok) {
    const err = await res.json().catch(() => ({ error: res.statusText }));
    throw new Error(err.error || 'request failed');
  }
  return res.json();
}

const jsonBody = (body) => ({
  method: body._method || 'POST',
  headers: { 'content-type': 'application/json' },
  body: JSON.stringify(body),
});

export const listTasks = (params = {}) => {
  const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v)).toString();
  return req(`/tasks${q ? `?${q}` : ''}`);
};
export const createTask = (task) => req('/tasks', jsonBody(task));
export const updateTask = (id, patch) =>
  req(`/tasks/${id}`, { method: 'PATCH', headers: { 'content-type': 'application/json' }, body: JSON.stringify(patch) });
export const completeTask = (id) => req(`/tasks/${id}/complete`, { method: 'POST' });
export const reopenTask = (id) => req(`/tasks/${id}/reopen`, { method: 'POST' });
export const deleteTask = (id) => req(`/tasks/${id}`, { method: 'DELETE' });
