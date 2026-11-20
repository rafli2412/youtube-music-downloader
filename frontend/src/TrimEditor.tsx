import { useEffect, useId, useRef, useState } from 'react';
import type { AudioTrim, DesktopClient } from './desktop';

const format = (seconds: number) => {
  const tenths = Math.round(seconds * 10);
  return `${Math.floor(tenths / 600)}:${String(Math.floor(tenths / 10) % 60).padStart(2, '0')}.${tenths % 10}`;
};

export function TrimEditor({ client, previewId, trim, videoDuration, onChange, disabled, onLoading }: {
  client: DesktopClient; previewId: string; trim: AudioTrim | null;
  videoDuration: number | null;
  onChange: (trim: AudioTrim | null) => void; disabled: boolean; onLoading: (value: boolean) => void;
}) {
  const audio = useRef<HTMLAudioElement>(null);
  const stopAt = useRef<number | null>(null);
  const objectUrl = useRef('');
  const mounted = useRef(false);
  const [source, setSource] = useState('');
  const [expanded, setExpanded] = useState(false);
  const panelId = useId();
  const [duration, setDuration] = useState(0);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; if (objectUrl.current) URL.revokeObjectURL(objectUrl.current); };
  }, []);

  const load = async () => {
    setLoading(true);
    onLoading(true);
    setError('');
    try {
      const size = await client.call(api => api.load_audio_preview(previewId));
      const chunks: Uint8Array<ArrayBuffer>[] = [];
      let offset = 0;
      while (offset < size && mounted.current) {
        const data = await client.call(api => api.read_audio_preview(previewId, offset));
        const bytes = Uint8Array.from(atob(data), char => char.charCodeAt(0));
        if (!bytes.length || offset + bytes.length > size) throw new Error('The audio preview was incomplete.');
        chunks.push(bytes);
        offset += bytes.length;
      }
      if (!mounted.current) return;
      if (objectUrl.current) URL.revokeObjectURL(objectUrl.current);
      objectUrl.current = URL.createObjectURL(new Blob(chunks, { type: 'audio/mpeg' }));
      setSource(objectUrl.current);
      setExpanded(true);
    } catch (failure) {
      if (mounted.current) setError(failure instanceof Error ? failure.message : String(failure));
    } finally {
      if (mounted.current) setLoading(false);
      onLoading(false);
    }
  };

  const start = trim?.start ?? 0;
  const end = trim?.end ?? duration;
  const keptEnd = trim?.end ?? (duration || videoDuration);
  const hasTrim = start > 0 || trim?.end != null;
  const update = (boundary: 'start' | 'end', value: number) => {
    const nextStart = boundary === 'start' ? value : start;
    const nextEnd = boundary === 'end' ? value : end;
    if (!Number.isFinite(value) || nextStart < 0 || nextEnd > duration || nextEnd <= nextStart) {
      setError('Enter a time within the track. End must be after start.');
      return;
    }
    audio.current?.pause();
    stopAt.current = null;
    setError('');
    const endPoint = nextEnd >= duration ? null : nextEnd;
    onChange(nextStart > 0 || endPoint !== null ? { start: nextStart, end: endPoint } : null);
  };
  const setFromPlayhead = (boundary: 'start' | 'end') => {
    if (audio.current) update(boundary, audio.current.currentTime);
  };
  const play = async (from: number, to: number) => {
    if (!audio.current) return;
    audio.current.currentTime = from;
    stopAt.current = to;
    try { await audio.current.play(); }
    catch { setError('Could not play this audio preview.'); }
  };
  const checkCut = (cut: number) => play(Math.max(0, cut - 3), Math.min(duration, cut + 3));

  return <section className="trim-editor" aria-label="Listen and trim">
    <button type="button" className="secondary-button" disabled={disabled || loading}
      aria-expanded={expanded} aria-controls={panelId} onClick={() => {
        if (!source) {
          void load();
          return;
        }
        if (expanded) {
          audio.current?.pause();
          stopAt.current = null;
        }
        setExpanded(!expanded);
      }}>
      {expanded ? 'Close Listen & trim' : loading ? 'Loading audio…' : !source && error ? 'Retry audio preview' : 'Listen & trim'}
    </button>
    <div id={panelId} className="trim-panel" hidden={!expanded}>
    {source && <audio ref={audio} controls src={source} onLoadedMetadata={event => {
      const seconds = event.currentTarget.duration;
      if (Number.isFinite(seconds)) setDuration(seconds);
    }} onError={() => setError('Could not play this audio preview.')} onTimeUpdate={event => {
      if (stopAt.current !== null && event.currentTarget.currentTime >= stopAt.current) {
        event.currentTarget.pause();
        stopAt.current = null;
      }
    }} />}
    {duration > 0 && <fieldset disabled={disabled}>
      <legend>Keep this part of the song</legend>
      <div className="trim-track" aria-hidden="true">
        <div style={{ left: `${Math.min(100, start / duration * 100)}%`, right: `${Math.max(0, 100 - end / duration * 100)}%` }} />
      </div>
      {(['start', 'end'] as const).map(boundary => {
        const value = boundary === 'start' ? start : end;
        return <div className="trim-boundary" key={boundary}>
          <label htmlFor={`trim-${boundary}`}>{boundary === 'start' ? 'Start' : 'End'}</label>
          <input aria-label={`Adjust ${boundary} on timeline`} type="range" min="0" max={duration} step="0.1" value={value}
            onChange={event => update(boundary, Number(event.target.value))} />
          <input id={`trim-${boundary}`} type="text" key={value} defaultValue={format(value)}
            onBlur={event => {
              if (event.target.value === format(value)) return;
              const parts = event.target.value.trim().split(':');
              const valid = parts.length <= 2 && parts.every(part => /^\d+(\.\d+)?$/.test(part));
              update(boundary, valid ? parts.reduce((total, part) => total * 60 + Number(part), 0) : NaN);
              event.target.value = format(value);
            }} onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); event.currentTarget.blur(); } }} />
        </div>;
      })}
      <p className="folder-hint">Keeping {format(Math.max(0, end - start))} of {format(duration)}</p>
      <div className="trim-actions trim-playhead-actions">
        <button type="button" className="secondary-button" onClick={() => setFromPlayhead('start')}>Set start here</button>
        <button type="button" className="secondary-button" onClick={() => setFromPlayhead('end')}>Set end here</button>
      </div>
      <div className="trim-actions">
        <button type="button" className="secondary-button" onClick={() => void play(start, end)}>Play selection</button>
        <button type="button" className="secondary-button" onClick={() => void checkCut(start)}>Check start</button>
        <button type="button" className="secondary-button" onClick={() => void checkCut(end)}>Check end</button>
        <button type="button" className="secondary-button" disabled={!hasTrim} onClick={() => {
          audio.current?.pause();
          stopAt.current = null;
          setError('');
          onChange(null);
        }}>Reset trim</button>
      </div>
    </fieldset>}
    </div>
    {!expanded && hasTrim && <div className="trim-actions">
      <p className="folder-hint">Keeping {format(start)}–{keptEnd === null ? 'end' : format(keptEnd)}
        {keptEnd !== null && ` · ${format(Math.max(0, keptEnd - start))}`}
      </p>
      <button type="button" className="secondary-button" disabled={disabled} onClick={() => onChange(null)}>Reset trim</button>
    </div>}
    {error && (expanded || !source) && <p className="error-message" role="alert">{error}</p>}
  </section>;
}
