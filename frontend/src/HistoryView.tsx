import { useEffect, useState } from 'react';
import type { DesktopClient, HistoryEntry, HistoryPage } from './desktop';
import { historyTime } from './history-time';

export function HistoryView({ client, revision }: { client: DesktopClient; revision: string | null }) {
  const [page, setPage] = useState<HistoryPage>({ entries: [], next_cursor: null });
  const [busy, setBusy] = useState(true);
  const [error, setError] = useState('');
  const [clearPending, setClearPending] = useState(false);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let active = true;
    setBusy(true); setError('');
    client.call(api => api.get_history()).then(result => { if (active) setPage(result); }, failure => { if (active) setError(String(failure)); }).finally(() => { if (active) setBusy(false); });
    const timer = setInterval(() => setNow(new Date()), 60000);
    return () => { active = false; clearInterval(timer); };
  }, [client, revision]);
  const action = async (task: () => Promise<unknown>) => {
    setBusy(true); setError('');
    try { await task(); } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
    finally { setBusy(false); }
  };
  const remove = (entry: HistoryEntry) => action(async () => {
    await client.call(api => api.remove_history(entry.id));
    setPage(current => ({ ...current, entries: current.entries.filter(item => item.id !== entry.id) }));
  });
  return <section className="download-card history-view" aria-labelledby="history-heading" aria-busy={busy}>
    <div className="card-heading"><h2 id="history-heading">History</h2><div className="history-actions"><button className="secondary-button" type="button" disabled={busy} onClick={() => void action(async () => setPage(await client.call(api => api.get_history())))}>Refresh</button><button className="secondary-button" type="button" disabled={busy || !page.entries.length} onClick={() => setClearPending(true)}>Clear history</button></div></div>
    <p className="folder-hint">Successful downloads, newest first. Removing history keeps your MP3 files.</p>
    {clearPending && <div className="history-confirm"><p>Clear all download history? Your MP3 files will stay on your computer.</p><button className="secondary-button" disabled={busy} onClick={() => void action(async () => { await client.call(api => api.clear_history()); setPage({ entries: [], next_cursor: null }); setClearPending(false); })}>Clear records</button><button className="secondary-button" disabled={busy} onClick={() => setClearPending(false)}>Cancel</button></div>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {!page.entries.length && <p className="status-detail" role="status">{busy ? 'Loading history…' : error ? 'History could not be loaded.' : 'No downloads yet. Completed downloads will appear here.'}</p>}
    <ol className="history-list">{page.entries.map(entry => {
      const timestamp = historyTime(entry.downloaded_at, now);
      return <li className="history-entry" key={entry.id}>
        <h3>{entry.song_title || entry.filename}</h3>
        <p className="history-filename">{entry.filename}</p>
        <time className="history-time" dateTime={entry.downloaded_at} title={timestamp.full} aria-label={timestamp.full} tabIndex={0}>{timestamp.label}<span className="history-date-tooltip" role="tooltip">{timestamp.full}</span></time>
        <div className="history-actions"><button className="secondary-button" disabled={busy} onClick={() => void action(() => client.call(api => api.open_history_youtube(entry.id)))}>Open YouTube ↗</button><button className="secondary-button history-path" disabled={busy || !entry.available} title={entry.path} aria-label={`Show in folder: ${entry.path}`} onClick={() => void action(() => client.call(api => api.reveal_history_file(entry.id)))}>Show in folder ↗</button><button className="history-remove" disabled={busy} onClick={() => void remove(entry)}>Remove entry</button></div>
        <p className="result-path">{entry.path}</p>{!entry.available && <p className="folder-hint">File unavailable — it may have been moved or deleted.</p>}
      </li>;
    })}</ol>
    {page.next_cursor !== null && <button className="secondary-button" disabled={busy} onClick={() => void action(async () => { const next = await client.call(api => api.get_history(page.next_cursor)); setPage(current => ({ entries: [...current.entries, ...next.entries], next_cursor: next.next_cursor })); })}>{busy ? 'Loading…' : 'Load more'}</button>}
  </section>;
}
