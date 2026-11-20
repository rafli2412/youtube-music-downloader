import { useEffect, useState } from 'react';
import type { DesktopClient, HistoryPage } from './desktop';
import { TooltipButton } from './TooltipButton';
import { HistoryIconButton } from './HistoryIconButton';
import { historyTime } from './history-time';

export function HistoryView({ client, revision }: { client: DesktopClient; revision: string | null }) {
  const [page, setPage] = useState<HistoryPage>({ entries: [], next_cursor: null, total: 0 });
  const [selected, setSelected] = useState<Set<number>>(() => new Set());
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [mutating, setMutating] = useState(false);
  const busy = loading || mutating;
  const [error, setError] = useState('');
  const [clearPending, setClearPending] = useState(false);
  const [undo, setUndo] = useState<{ token: string; count: number; expires: number } | null>(null);
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    let active = true;
    setSelected(new Set());
    setLoading(true); setError(''); setPage({ entries: [], next_cursor: null, total: 0 });
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
  useEffect(() => {
    if (!undo) return;
    const timer = setTimeout(() => setUndo(null), Math.max(0, undo.expires - Date.now()));
    return () => clearTimeout(timer);
  }, [undo]);
  const reloadVisible = async () => {
    const desired = Math.max(100, page.entries.length);
    let refreshed = await client.call(api => api.get_history(null, query));
    while (refreshed.entries.length < desired && refreshed.next_cursor !== null) {
      const cursor = refreshed.next_cursor;
      const next = await client.call(api => api.get_history(cursor, query));
      refreshed = { entries: [...refreshed.entries, ...next.entries], next_cursor: next.next_cursor, total: next.total };
    }
    setPage(refreshed);
    const visible = new Set(refreshed.entries.map(entry => entry.id));
    setSelected(current => new Set([...current].filter(id => visible.has(id))));
  };
  const removeEntries = (identities: number[]) => action(async () => {
    const result = await client.call(api => api.remove_history_undoable(identities));
    const removed = new Set(identities);
    setPage(current => ({ ...current, total: Math.max(0, current.total - result.removed), entries: current.entries.filter(entry => !removed.has(entry.id)) }));
    setSelected(current => new Set([...current].filter(id => !removed.has(id))));
    if (result.undo_token && result.removed) setUndo({ token: result.undo_token, count: result.removed, expires: Date.now() + result.undo_seconds * 1000 });
    await reloadVisible();
  });
  const undoRemoval = () => action(async () => {
    if (!undo) return;
    await client.call(api => api.undo_history_removal(undo.token));
    setUndo(null);
    await reloadVisible();
  });
  const allLoadedSelected = page.entries.length > 0 && page.entries.every(entry => selected.has(entry.id));
  return <section className="download-card history-view" aria-labelledby="history-heading" aria-busy={busy}>
    <div className="card-heading"><h2 id="history-heading">History</h2><div className="history-actions"><HistoryIconButton icon="refresh" label="Refresh" disabled={busy} onClick={() => void action(async () => { setPage(await client.call(api => api.get_history(null, query))); setSelected(new Set()); })} /><TooltipButton tooltip="Remove all history records after confirmation. MP3 files are kept." className="secondary-button" type="button" disabled={busy || !page.entries.length} onClick={() => setClearPending(true)}>Clear history</TooltipButton></div></div>
    <p className="folder-hint">Successful downloads, newest first. Removing history keeps your MP3 files.</p>
    <div className="history-search"><label htmlFor="history-search">Search history</label><div className="history-search-controls"><input id="history-search" type="search" value={query} maxLength={500} disabled={mutating} placeholder="Search song title or filename" onChange={event => { setQuery(event.target.value); setClearPending(false); }} autoComplete="off" />{query && <TooltipButton tooltip="Clear the search and show all history records again." className="secondary-button" type="button" disabled={mutating} onClick={() => setQuery('')}>Clear search</TooltipButton>}</div></div>
    <p className="history-count" role="status">{loading ? 'Counting…' : query.trim() ? `${page.total} ${page.total === 1 ? 'match' : 'matches'}` : `${page.total} ${page.total === 1 ? 'download' : 'downloads'}`}</p>
    {undo && <div className="history-undo" role="status"><span>{undo.count} {undo.count === 1 ? 'entry' : 'entries'} removed. MP3 files kept.</span><TooltipButton tooltip="Restore the last removed history entries. Undo is available for 30 seconds in this view." className="secondary-button" disabled={busy} onClick={() => void undoRemoval()}>Undo</TooltipButton></div>}
    {clearPending && <div className="history-confirm"><p>Clear all download history? Your MP3 files will stay on your computer.</p><TooltipButton tooltip="Confirm removal of every history record. Your MP3 files stay on your computer." className="secondary-button" disabled={busy} onClick={() => void action(async () => { await client.call(api => api.clear_history()); setPage({ entries: [], next_cursor: null, total: 0 }); setSelected(new Set()); setClearPending(false); setUndo(null); })}>Clear records</TooltipButton><TooltipButton tooltip="Keep your history and close this confirmation." className="secondary-button" disabled={busy} onClick={() => setClearPending(false)}>Cancel</TooltipButton></div>}
    {error && <p className="error-message" role="alert">{error}</p>}
    {!page.entries.length && <p className="status-detail" role="status">{busy ? 'Loading history…' : error ? 'History could not be loaded.' : query.trim() ? 'No downloads match your search.' : 'No downloads yet. Completed downloads will appear here.'}</p>}
    {page.entries.length > 0 && <div className="history-selection"><label className="history-select-all"><input type="checkbox" checked={allLoadedSelected} ref={node => { if (node) node.indeterminate = selected.size > 0 && !allLoadedSelected; }} disabled={busy} onChange={event => setSelected(event.target.checked ? new Set(page.entries.map(entry => entry.id)) : new Set())} />Select loaded entries</label><span role="status">{selected.size} selected</span><HistoryIconButton icon="remove-selected" label="Remove selected" disabled={busy || selected.size === 0} onClick={() => void removeEntries([...selected])} />{selected.size > 0 && <HistoryIconButton icon="clear-selection" label="Clear selection" disabled={busy} onClick={() => setSelected(new Set())} />}</div>}
    <ol className="history-list">{page.entries.map(entry => {
      const timestamp = historyTime(entry.downloaded_at, now);
      return <li className={`history-entry${selected.has(entry.id) ? ' selected' : ''}`} key={entry.id}>
        <div className="history-entry-heading"><input className="history-select-entry" type="checkbox" aria-label={`Select ${entry.song_title || entry.filename}`} checked={selected.has(entry.id)} disabled={busy} onChange={event => { const checked = event.target.checked; setSelected(current => { const next = new Set(current); if (checked) next.add(entry.id); else next.delete(entry.id); return next; }); }} /><h3>{entry.song_title || entry.filename}</h3><div className="history-entry-actions"><HistoryIconButton icon="youtube" label="Open YouTube" disabled={busy} onClick={() => void action(() => client.call(api => api.open_history_youtube(entry.id)))} /><HistoryIconButton icon="folder" label="Show in folder" hint={entry.path} className="history-path" disabled={busy || !entry.available} onClick={() => void action(() => client.call(api => api.reveal_history_file(entry.id)))} /><HistoryIconButton icon="remove" label="Remove entry" className="history-remove-icon" disabled={busy} onClick={() => void removeEntries([entry.id])} /></div></div>
        <p className="history-filename">{entry.filename}</p>
        <time className="history-time" dateTime={entry.downloaded_at} title={timestamp.full} aria-label={timestamp.full} tabIndex={0}>{timestamp.label}<span className="history-date-tooltip" role="tooltip">{timestamp.full}</span></time>
        {!entry.available && <p className="folder-hint">File unavailable — it may have been moved or deleted.</p>}
      </li>;
    })}</ol>
    {page.next_cursor !== null && <TooltipButton tooltip="Load the next page of history entries matching the current search." className="secondary-button" disabled={busy} onClick={() => void action(async () => { const next = await client.call(api => api.get_history(page.next_cursor, query)); setPage(current => ({ entries: [...current.entries, ...next.entries], next_cursor: next.next_cursor, total: next.total })); })}>{busy ? 'Loading…' : 'Load more'}</TooltipButton>}
  </section>;
}
