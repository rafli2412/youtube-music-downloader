import { useEffect, useState } from 'react';
import type { DesktopClient, HistoryEntry, HistoryPage } from './desktop';
import { HistoryIconButton } from './HistoryIconButton';
import { historyTime } from './history-time';

export function HistoryView({ client, revision }: { client: DesktopClient; revision: string | null }) {
  const [page, setPage] = useState<HistoryPage>({ entries: [], next_cursor: null });
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [mutating, setMutating] = useState(false);
  const busy = loading || mutating;
  const [error, setError] = useState('');
  const [clearPending, setClearPending] = useState(false);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let active = true;
    setSelected(new Set());
    setLoading(true); setError(''); setPage({ entries: [], next_cursor: null });
    const delay = setTimeout(() => {
      client.call(api => api.get_history(null, query)).then(result => { if (active) setPage(result); }, failure => { if (active) setError(String(failure)); }).finally(() => { if (active) setLoading(false); });
    }, query ? 250 : 0);
    return () => { active = false; clearTimeout(delay); };
  }, [client, revision, query]);
  useEffect(() => { const timer = setInterval(() => setNow(new Date()), 60000); return () => clearInterval(timer); }, []);
  const action = async (task: () => Promise<unknown>) => {
    setMutating(true); setError('');
    try { await task(); } catch (failure) { setError(failure instanceof Error ? failure.message : String(failure)); }
    finally { setMutating(false); }
  };
  const remove = (entry: HistoryEntry) => action(async () => {
    await client.call(api => api.remove_history(entry.id));
    setPage(current => ({ ...current, entries: current.entries.filter(item => item.id !== entry.id) }));
    setSelected(current => { const next = new Set(current); next.delete(entry.id); return next; });
  });
  const removeSelected = () => action(async () => {
    const identities = new Set(selected);
    await client.call(api => api.remove_history_many([...identities]));
    setPage(current => ({ ...current, entries: current.entries.filter(entry => !identities.has(entry.id)) }));
    setSelected(new Set());
  });
  const allLoadedSelected = page.entries.length > 0 && page.entries.every(entry => selected.has(entry.id));
  return <section className="download-card history-view" aria-labelledby="history-heading" aria-busy={busy}>
    <div className="card-heading"><h2 id="history-heading">History</h2><div className="history-actions"><HistoryIconButton icon="refresh" label="Refresh" disabled={busy} onClick={() => void action(async () => { setPage(await client.call(api => api.get_history(null, query))); setSelected(new Set()); })} /><button className="secondary-button" type="button" disabled={busy || !page.entries.length} onClick={() => setClearPending(true)}>Clear history</button></div></div>
    <p className="folder-hint">Successful downloads, newest first. Removing history keeps your MP3 files.</p>
    <div className="history-search"><label htmlFor="history-search">Search history</label><div className="history-search-controls"><input id="history-search" type="search" value={query} maxLength={500} disabled={mutating} placeholder="Search song title or filename" onChange={event => { setQuery(event.target.value); setClearPending(false); }} autoComplete="off" />{query && <button className="secondary-button" type="button" disabled={mutating} onClick={() => setQuery('')}>Clear search</button>}</div></div>
    {clearPending && <div className="history-confirm"><p>Clear all download history? Your MP3 files will stay on your computer.</p><button className="secondary-button" disabled={busy} onClick={() => void action(async () => { await client.call(api => api.clear_history()); setPage({ entries: [], next_cursor: null }); setSelected(new Set()); setClearPending(false); })}>Clear records</button><button className="secondary-button" disabled={busy} onClick={() => setClearPending(false)}>Cancel</button></div>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {!page.entries.length && <p className="status-detail" role="status">{busy ? 'Loading history…' : error ? 'History could not be loaded.' : query.trim() ? 'No downloads match your search.' : 'No downloads yet. Completed downloads will appear here.'}</p>}
    {page.entries.length > 0 && <div className="history-selection"><label className="history-select-all"><input type="checkbox" checked={allLoadedSelected} ref={node => { if (node) node.indeterminate = selected.size > 0 && !allLoadedSelected; }} disabled={busy} onChange={event => setSelected(event.target.checked ? new Set(page.entries.map(entry => entry.id)) : new Set())} />Select loaded entries</label><span role="status">{selected.size} selected</span><HistoryIconButton icon="remove-selected" label="Remove selected" disabled={busy || selected.size === 0} onClick={() => void removeSelected()} />{selected.size > 0 && <HistoryIconButton icon="clear-selection" label="Clear selection" disabled={busy} onClick={() => setSelected(new Set())} />}</div>}
    <ol className="history-list">{page.entries.map(entry => {
      const timestamp = historyTime(entry.downloaded_at, now);
      return <li className={`history-entry${selected.has(entry.id) ? ' selected' : ''}`} key={entry.id}>
        <div className="history-entry-heading"><input className="history-select-entry" type="checkbox" aria-label={`Select ${entry.song_title || entry.filename}`} checked={selected.has(entry.id)} disabled={busy} onChange={event => { const checked = event.target.checked; setSelected(current => { const next = new Set(current); if (checked) next.add(entry.id); else next.delete(entry.id); return next; }); }} /><h3>{entry.song_title || entry.filename}</h3><div className="history-entry-actions"><HistoryIconButton icon="youtube" label="Open YouTube" disabled={busy} onClick={() => void action(() => client.call(api => api.open_history_youtube(entry.id)))} /><HistoryIconButton icon="folder" label="Show in folder" hint={entry.path} className="history-path" disabled={busy || !entry.available} onClick={() => void action(() => client.call(api => api.reveal_history_file(entry.id)))} /><HistoryIconButton icon="remove" label="Remove entry" className="history-remove-icon" disabled={busy} onClick={() => void remove(entry)} /></div></div>
        <p className="history-filename">{entry.filename}</p>
        <time className="history-time" dateTime={entry.downloaded_at} title={timestamp.full} aria-label={timestamp.full} tabIndex={0}>{timestamp.label}<span className="history-date-tooltip" role="tooltip">{timestamp.full}</span></time>
        {!entry.available && <p className="folder-hint">File unavailable — it may have been moved or deleted.</p>}
      </li>;
    })}</ol>
    {page.next_cursor !== null && <button className="secondary-button" disabled={busy} onClick={() => void action(async () => { const next = await client.call(api => api.get_history(page.next_cursor, query)); setPage(current => ({ entries: [...current.entries, ...next.entries], next_cursor: next.next_cursor })); })}>{busy ? 'Loading…' : 'Load more'}</button>}
  </section>;
}
