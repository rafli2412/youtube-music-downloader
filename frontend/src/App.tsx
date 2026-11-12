import { useEffect, useState } from 'react';
import { connectDesktop, VersionMismatchError } from './desktop';
import type { AppInfo } from './desktop';

function MusicIcon({ className = '' }: { className?: string }) {
  return (
    <svg className={className} viewBox="0 0 24 24" fill="none" aria-hidden="true">
      <path d="M9 17V6l11-2v11" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      <path d="M9 9l11-2" stroke="currentColor" strokeWidth="1.8" />
      <ellipse cx="6" cy="17.5" rx="3" ry="2.5" fill="currentColor" />
      <ellipse cx="17" cy="15.5" rx="3" ry="2.5" fill="currentColor" />
    </svg>
  );
}

export function App() {
  const [appInfo, setAppInfo] = useState<AppInfo | null>(null);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [url, setUrl] = useState('');

  useEffect(() => {
    let active = true;
    connectDesktop().then(
      (info) => { if (active) setAppInfo(info); },
      (error: unknown) => {
        if (active) {
          setConnectionError(error instanceof VersionMismatchError
            ? error.message
            : 'Open the desktop app to connect');
        }
      },
    );
    return () => { active = false; };
  }, []);

  const connectionLabel = appInfo
    ? 'Desktop ready'
    : connectionError
      ? connectionError
      : 'Connecting to desktop…';

  return (
    <div className="app-shell" data-desktop-state={appInfo ? 'ready' : 'connecting'}>
      <header className="app-header">
        <div className="brand">
          <div className="brand-icon"><MusicIcon /></div>
          <span>YouTube Music Downloader</span>
        </div>
        <span className="preview-badge">Desktop preview</span>
      </header>

      <main>
        <div className="intro">
          <span className="eyebrow">A little more listening</span>
          <h1>Your music,<br />a link away.</h1>
          <p>A simple place to save audio from YouTube<br className="wide-break" /> and YouTube Music as MP3.</p>
        </div>

        <section className="download-card" aria-labelledby="download-heading">
          <div className="card-heading">
            <h2 id="download-heading">Start with a link</h2>
            <span className="format-label">MP3</span>
          </div>
          <form onSubmit={(event) => event.preventDefault()}>
            <label htmlFor="video-url">Video or song link</label>
            <div className="url-field">
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M10 13a4.5 4.5 0 006.4 0l3-3A4.5 4.5 0 0013 3.6l-1.7 1.7M14 11a4.5 4.5 0 00-6.4 0l-3 3A4.5 4.5 0 0011 20.4l1.7-1.7" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
              </svg>
              <input
                id="video-url"
                type="url"
                value={url}
                onChange={(event) => setUrl(event.target.value)}
                placeholder="Paste a YouTube or YouTube Music link"
                autoComplete="off"
                spellCheck={false}
                aria-describedby="download-note"
              />
            </div>
            <button className="convert-button" type="submit" disabled aria-describedby="download-note">
              Convert to MP3
              <svg viewBox="0 0 24 24" fill="none" aria-hidden="true">
                <path d="M12 4v12m-5-5l5 5 5-5M5 18v3h14v-3" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
              </svg>
            </button>
            <p className="download-note" id="download-note">Downloads will be available in the next update.</p>
          </form>
        </section>

        <div className="quiet-details" aria-label="App features">
          <span>One link at a time</span>
          <span className="detail-dot" aria-hidden="true" />
          <span>Just the audio</span>
          <span className="detail-dot" aria-hidden="true" />
          <span>On your computer</span>
        </div>
      </main>

      <footer className="app-footer">
        <div className={`connection-status ${appInfo ? 'connected' : ''}`} role="status" aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          <span>{connectionLabel}</span>
        </div>
        {appInfo && <span className="app-version">v{appInfo.version}</span>}
      </footer>
    </div>
  );
}
