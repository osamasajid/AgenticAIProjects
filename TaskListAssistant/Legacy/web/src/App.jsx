import { useEffect, useState, useCallback } from 'react';
import * as api from './api.js';

const PRIORITIES = ['high', 'medium', 'low'];
const CATEGORIES = ['financial', 'routine', 'general'];

function priorityRank(p) {
  return { high: 0, medium: 1, low: 2 }[p] ?? 3;
}

export default function App() {
  const [tasks, setTasks] = useState([]);
  const [error, setError] = useState(null);
  const [statusFilter, setStatusFilter] = useState('all');
  const [sort, setSort] = useState('priority');

  // Add-form state
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [priority, setPriority] = useState('medium');
  const [dueDate, setDueDate] = useState('');
  const [category, setCategory] = useState('');

  const load = useCallback(async () => {
    try {
      const data = await api.listTasks(statusFilter === 'all' ? {} : { status: statusFilter });
      setTasks(data);
      setError(null);
    } catch (e) {
      setError(e.message);
    }
  }, [statusFilter]);

  // Poll so agent-made changes appear in this legacy UI too (demo beat).
  useEffect(() => {
    load();
    const id = setInterval(load, 3000);
    return () => clearInterval(id);
  }, [load]);

  const sorted = [...tasks].sort((a, b) => {
    if (sort === 'priority') return priorityRank(a.priority) - priorityRank(b.priority);
    if (sort === 'dueDate') return (a.dueDate || '9999').localeCompare(b.dueDate || '9999');
    if (sort === 'status') return a.status.localeCompare(b.status);
    return b.createdAt.localeCompare(a.createdAt);
  });

  async function onAdd(e) {
    e.preventDefault();
    if (!title.trim()) return;
    try {
      await api.createTask({
        title: title.trim(),
        description: description.trim() || null,
        priority,
        dueDate: dueDate || null,
        category: category || null,
      });
      setTitle(''); setDescription(''); setPriority('medium'); setDueDate(''); setCategory('');
      load();
    } catch (e) { setError(e.message); }
  }

  async function toggle(t) {
    try {
      t.status === 'done' ? await api.reopenTask(t.id) : await api.completeTask(t.id);
      load();
    } catch (e) { setError(e.message); }
  }

  async function remove(id) {
    try { await api.deleteTask(id); load(); } catch (e) { setError(e.message); }
  }

  const openCount = tasks.filter((t) => t.status === 'open').length;

  return (
    <div className="app">
      <header>
        <h1>Task Manager</h1>
        <p className="sub">{openCount} open · {tasks.length} total</p>
      </header>

      {error && <div className="error">Error: {error}</div>}

      <form className="add" onSubmit={onAdd}>
        <input
          type="text"
          placeholder="New task…"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          aria-label="Task title"
        />
        <select value={priority} onChange={(e) => setPriority(e.target.value)} aria-label="Priority">
          {PRIORITIES.map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <select value={category} onChange={(e) => setCategory(e.target.value)} aria-label="Category">
          <option value="">(no category)</option>
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} aria-label="Due date" />
        <button type="submit">Add</button>
        <textarea
          className="desc-input"
          placeholder="Description / details (e.g. Pay Ortega $150)"
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          aria-label="Task description"
          rows={2}
        />
      </form>

      <div className="controls">
        <label>Show:&nbsp;
          <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
            <option value="all">All</option>
            <option value="open">Open</option>
            <option value="done">Done</option>
          </select>
        </label>
        <label>Sort by:&nbsp;
          <select value={sort} onChange={(e) => setSort(e.target.value)}>
            <option value="priority">Priority</option>
            <option value="dueDate">Due date</option>
            <option value="status">Status</option>
            <option value="createdAt">Newest</option>
          </select>
        </label>
      </div>

      <ul className="tasks">
        {sorted.map((t) => (
          <li key={t.id} className={`task ${t.status}`}>
            <input
              type="checkbox"
              checked={t.status === 'done'}
              onChange={() => toggle(t)}
              aria-label={`Complete ${t.title}`}
            />
            <div className="body">
              <span className="title">{t.title}</span>
              {t.description && <span className="desc">{t.description}</span>}
              <span className="meta">
                <span className={`badge p-${t.priority}`}>{t.priority}</span>
                {t.category && <span className="badge cat">{t.category}</span>}
                {t.dueDate && <span className="due">due {t.dueDate}</span>}
              </span>
            </div>
            <button className="del" onClick={() => remove(t.id)} aria-label={`Delete ${t.title}`}>✕</button>
          </li>
        ))}
        {sorted.length === 0 && <li className="empty">No tasks.</li>}
      </ul>

      <footer>Legacy Task Manager — the classic click-through experience.</footer>
    </div>
  );
}
