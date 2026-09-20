'use client';

import { FormEvent, useEffect, useState } from 'react';
import type { components } from './api.generated';

type Run = components['schemas']['RunRead'];
type Status = components['schemas']['RunStatus'];
type Create = components['schemas']['RunCreate'];
type Update = components['schemas']['RunUpdate'];
const statuses: Status[] = ['planned', 'running', 'passed', 'failed'];

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch('/api' + path, { ...init, headers: { 'Content-Type': 'application/json' } });
  if (!response.ok) {
    if (response.status === 409) throw new Error('This run changed elsewhere. Refresh and try again.');
    throw new Error('The change could not be saved. Check the input and try again.');
  }
  return response.json() as Promise<T>;
}

export default function Home() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [title, setTitle] = useState('');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [loaded, setLoaded] = useState(false);

  async function refresh() {
    try { setRuns(await request<Run[]>('/runs')); setError(''); }
    catch (err) { setError((err as Error).message); }
    finally { setLoaded(true); }
  }
  useEffect(() => { void refresh(); }, []);

  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError('');
    const body: Create = { title: title.trim() };
    try {
      const item = await request<Run>('/runs', { method: 'POST', body: JSON.stringify(body) });
      setRuns(items => [item, ...items]); setTitle('');
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  async function update(item: Run, status: Status) {
    setBusy(true); setError('');
    const body: Update = { status, expected_revision: item.revision };
    try {
      const updated = await request<Run>('/runs/' + item.id, { method: 'PATCH', body: JSON.stringify(body) });
      setRuns(items => items.map(run => run.id === updated.id ? updated : run));
    } catch (err) { setError((err as Error).message); }
    finally { setBusy(false); }
  }

  return <main>
    <header><span className="eyebrow">Engineering workspace</span><h1>Run ledger</h1>
      <p>Keep a clear record of what ran, what changed and what passed.</p></header>
    <section aria-labelledby="create-heading" className="panel">
      <h2 id="create-heading">Start a record</h2>
      <form onSubmit={create}>
        <label htmlFor="title">Run title</label>
        <div className="entry"><input id="title" value={title} onChange={event => setTitle(event.target.value)}
          required maxLength={120} placeholder="For example, verify the release candidate" />
          <button disabled={busy || !title.trim()}>Create run</button></div>
      </form>
    </section>
    {error && <p role="alert" className="error">{error}</p>}
    <section aria-labelledby="runs-heading" className="panel">
      <div className="section-heading"><h2 id="runs-heading">Recorded runs</h2>
        <button className="secondary" disabled={busy} onClick={() => void refresh()}>Refresh</button></div>
      {!loaded ? <p role="status">Loading runs…</p> : runs.length === 0 ? <p>No runs yet. Create your first record above.</p> :
        <ul>{runs.map(item => <li key={item.id} data-testid="run-row">
          <div><h3>{item.title}</h3><p className="meta">Revision {item.revision} · {item.event_count} recorded changes</p></div>
          <label className="status-label">Status for {item.title}
            <select aria-label={'Status for ' + item.title} value={item.status} disabled={busy}
              onChange={event => void update(item, event.target.value as Status)}>
              {statuses.map(status => <option key={status} value={status}>{status}</option>)}
            </select></label>
        </li>)}</ul>}
    </section>
    <footer>Local engineering records · status reflects the entered result, not independent test verification.</footer>
  </main>;
}
