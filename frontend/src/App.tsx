import { VideoDetails } from './VideoDetails';
import { useEffect, useRef, useState } from 'react';
import { connectDesktop, DesktopClient, progressLabel, VersionMismatchError } from './desktop';
import type { AppInfo, JobState } from './desktop';

const emptyJob: JobState = { job_id: null, status: 'idle', busy: false, downloaded_bytes: 0, total_bytes: null, fraction: null, directory: null, result: null, error: null };
const message = (error: unknown) => error instanceof Error ? error.message : String(error);

function MusicIcon() {
  return <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"><path d="M9 17V6l11-2v11M9 9l11-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" /><ellipse cx="6" cy="17.5" rx="3" ry="2.5" fill="currentColor" /><ellipse cx="17" cy="15.5" rx="3" ry="2.5" fill="currentColor" /></svg>;
}

export function App() {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [url, setUrl] = useState('');
  const [filename, setFilename] = useState('');
  const [directory, setDirectory] = useState<string | null>(null);
  const [job, setJob] = useState<JobState>(emptyJob);
  const [pending, setPending] = useState(false);
  const [closing, setClosing] = useState(false);
  const [initialized, setInitialized] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const client = useRef<DesktopClient | null>(null);
  const closingRef = useRef(false);
  const epoch = useRef(0);
  const polling = useRef<ReturnType<typeof setTimeout> | null>(null);
  const urlInput = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    let active = true;
    const connection = connectDesktop();
    connection.then(async info => {
      if (!active || closingRef.current) return;
      client.current ??= new DesktopClient(window.pywebview!.api!);
      setAppInfo(info);
      try {
        const settings = await client.current.call(api => api.get_settings());
        const state = await client.current.call(api => api.get_job());
        if (active && !closingRef.current) { setDirectory(settings.download_directory); setJob(state); }
      } catch (failure) { if (active && !closingRef.current) setError(message(failure)); }
      finally { if (active && !closingRef.current) setInitialized(true); }
    }, failure => {
      if (active && !closingRef.current) setConnectionError(failure instanceof VersionMismatchError ? failure.message : 'Open the desktop app to connect');
    });
    const onClosing = () => {
      closingRef.current = true;
      setClosing(true);
      if (polling.current) clearTimeout(polling.current);
      void (async () => {
        await connection.catch(() => undefined);
        await client.current?.close();
        document.documentElement.dataset.desktopClosing = 'ready';
      })();
    };
    window.addEventListener('desktopclosing', onClosing);
    return () => { active = false; window.removeEventListener('desktopclosing', onClosing); };
  }, []);

  useEffect(() => {
    if (!job.busy || closing || !client.current) return;
    let active = true;
    const poll = async () => {
      const requestEpoch = epoch.current;
      try {
        const state = await client.current!.call(api => api.get_job());
        if (active && !closingRef.current && requestEpoch === epoch.current) setJob(state);
      } catch (failure) {
        if (active && !closingRef.current) setError(`Could not refresh progress: ${message(failure)}`);
      }
      if (active && !closingRef.current) polling.current = setTimeout(poll, 300);
    };
    polling.current = setTimeout(poll, 100);
    return () => { active = false; if (polling.current) clearTimeout(polling.current); };
  }, [job.busy, closing]);

  const start = async () => {
    if (!client.current || pending || job.busy || closingRef.current) return;
    ++epoch.current;
    const previewJobId = job.status === 'ready' ? job.job_id : null;
    setPending(true); setError(null);
    if (!previewJobId) { setJob(emptyJob); setFilename(''); }
    try {
      const state = await client.current.call(api => previewJobId ? api.start_download(url, previewJobId, filename.trim()) : api.preview_video(url));
      if (!closingRef.current) { setJob(state); if (state.directory) setDirectory(state.directory); }
    } catch (failure) { if (!closingRef.current) setError(message(failure)); }
    finally { if (!closingRef.current) setPending(false); }
  };
  const cancel = async () => {
    if (!client.current || closingRef.current) return;
    ++epoch.current;
    setPending(true); setError(null);
    try { const state = await client.current.call(api => api.cancel_download()); if (!closingRef.current) setJob(state); }
    catch (failure) { if (!closingRef.current) setError(message(failure)); }
    finally { if (!closingRef.current) setPending(false); }
  };
  const chooseFolder = async () => {
    if (!client.current || pending || job.busy || closingRef.current) return;
    setPending(true); setError(null);
    try { const settings = await client.current.call(api => api.choose_download_directory()); if (!closingRef.current) setDirectory(settings.download_directory); }
    catch (failure) { if (!closingRef.current) setError(message(failure)); }
    finally { if (!closingRef.current) setPending(false); }
  };
  const openFolder = async () => {
    if (!client.current || closingRef.current) return;
    setPending(true); setError(null);
    try { await client.current.call(api => api.open_download_folder()); }
    catch (failure) { if (!closingRef.current) setError(message(failure)); }
    finally { if (!closingRef.current) setPending(false); }
  };
  const convertAnother = () => {
    if (pending || job.busy || closingRef.current) return;
    ++epoch.current;
    if (polling.current) clearTimeout(polling.current);
    setUrl('');
    setFilename('');
    setJob(emptyJob);
    setError(null);
    urlInput.current?.focus();
  };
  const disabled = !appInfo || !initialized || pending || closing;
  const fraction = job.status === 'downloading' ? job.fraction : null;
  const status = closing ? 'Closing after cleaning up…' : progressLabel(job);

  return <div className="app-shell" data-desktop-state={appInfo && initialized ? 'ready' : 'connecting'} data-job-status={job.status}>
    <header className="app-header">
      <div className="brand"><div className="brand-icon"><MusicIcon /></div><span>YouTube Music Downloader</span></div>
      <span className="preview-badge">One link. One MP3.</span>
    </header>
    <main>
      <div className="intro"><span className="eyebrow">A little more listening</span><h1>Your music,<br />a link away.</h1><p>Save audio from YouTube and YouTube Music<br className="wide-break" /> to a folder on your computer.</p></div>
      <section className="download-card" aria-labelledby="download-heading" aria-busy={job.busy || pending}>
        <div className="card-heading"><h2 id="download-heading">Start with a link</h2><span className="format-label">MP3</span></div>
        <form onSubmit={event => { event.preventDefault(); void start(); }}>
          <label htmlFor="video-url">Video or song link</label>
          <div className="url-field"><span className="link-symbol" aria-hidden="true">↗</span><input ref={urlInput} id="video-url" type="url" required value={url} onChange={event => { ++epoch.current; setUrl(event.target.value); setFilename(''); setJob(emptyJob); setError(null); }} disabled={disabled || job.busy} placeholder="Paste a YouTube or YouTube Music link" autoComplete="off" spellCheck={false} /></div>
          <div className="folder-row"><div className="folder-copy"><span className="folder-label">Save to</span><span id="download-directory" className="folder-path" title={directory ?? ''}>{directory ?? 'Your default download folder'}</span></div><button id="choose-folder" className="secondary-button" type="button" onClick={() => void chooseFolder()} disabled={disabled || job.busy}>Choose folder</button></div>
          <p className="folder-hint">Remembered for future downloads, including the terminal app.</p>
          {job.status === 'ready' && job.metadata && <div className="video-preview"><p className="status-heading">Is this the video you want?</p><VideoDetails video={job.metadata} /><label htmlFor="download-filename">Filename (optional)</label><div className="url-field"><input id="download-filename" type="text" value={filename} onChange={event => setFilename(event.target.value)} placeholder={job.metadata.title ?? 'Video title'} disabled={disabled} autoComplete="off" /><span className="filename-extension">.mp3</span></div><p className="folder-hint">Leave blank to use the video title. Duplicate names get a number.</p><p className="status-detail">No audio has been downloaded. Review the details before continuing.</p></div>}
          <div className="action-row"><button id="convert" className="convert-button" type="submit" disabled={disabled || job.busy || !directory || !url.trim()}>{pending && !job.busy ? 'Please wait…' : job.status === 'ready' ? 'Download MP3' : 'Preview video'}</button>{job.busy && <button id="cancel" type="button" className="secondary-button" onClick={() => void cancel()} disabled={disabled || job.status === 'cancelling'}>Cancel</button>}</div>
        </form>
        {((job.status !== 'idle' && job.status !== 'ready') || closing) && <div className={`job-status ${job.status}`} data-testid="job-status">
          <p className="status-heading" role="status" aria-live="polite">{status}</p>
          {job.metadata && <VideoDetails video={job.metadata} />}
          {job.busy && <progress max={1} value={fraction ?? undefined} aria-label={status} />}
          {job.result && job.status === 'complete' && <div className="result"><p className="result-title">{job.result.title}</p><p className="result-path">{job.result.path}</p><button id="open-folder" type="button" className="secondary-button" onClick={() => void openFolder()} disabled={disabled}>Open folder</button><button id="convert-another" type="button" className="secondary-button" onClick={convertAnother} disabled={disabled}>Convert another video</button></div>}
          {job.status === 'cancelled' && <p className="status-detail">Temporary files have been removed. Paste another link to try again.</p>}
          {job.error && <p className="error-message" role="alert">{job.error}</p>}
        </div>}
        {error && <p className="error-message" role="alert">{error}</p>}
      </section>
      <div className="quiet-details"><span>One link at a time</span><span className="detail-dot" aria-hidden="true" /><span>Just the audio</span><span className="detail-dot" aria-hidden="true" /><span>On your computer</span></div>
    </main>
    <footer className="app-footer"><div className={`connection-status ${appInfo ? 'connected' : ''}`} role="status"><span className="status-dot" aria-hidden="true" /><span>{appInfo ? 'Ready on your desktop' : connectionError ?? 'Connecting to desktop…'}</span></div>{appInfo && <span className="app-version">v{appInfo.version}</span>}</footer>
  </div>;
}
