export interface AppInfo {
  name: string;
  version: string;
  platform: string;
  architecture: string;
  packaged: boolean;
}

export interface DesktopApi {
  get_app_info(): Promise<AppInfo>;
  get_settings(): Promise<Settings>;
  get_job(): Promise<JobState>;
  start_download(url: string): Promise<JobState>;
  cancel_download(): Promise<JobState>;
  choose_download_directory(): Promise<Settings>;
  open_download_folder(): Promise<{ ok: boolean }>;
  frontend_ready(payload: { version: string }): Promise<unknown>;
}

export interface BridgeHost {
  pywebview?: { api?: DesktopApi };
  addEventListener(type: string, listener: EventListener): void;
  removeEventListener(type: string, listener: EventListener): void;
}

declare global {
  interface Window {
    pywebview?: { api?: DesktopApi };
  }
}

/** The bridge may be injected before or after React mounts. Handle both orders. */
export function waitForDesktopApi(
  host: BridgeHost,
  timeoutMs = 5000,
): Promise<DesktopApi> {
  return new Promise((resolve, reject) => {
    const cleanup = () => {
      clearTimeout(timer);
      host.removeEventListener('pywebviewready', onReady);
    };

    const onReady: EventListener = () => {
      const api = host.pywebview?.api;
      if (typeof api?.get_app_info === 'function' && typeof api.frontend_ready === 'function') {
        cleanup();
        resolve(api);
      }
    };

    const timer = setTimeout(() => {
      cleanup();
      reject(new Error('Desktop connection unavailable.'));
    }, timeoutMs);

    host.addEventListener('pywebviewready', onReady);
    onReady(new Event('pywebviewready'));
  });
}

export class VersionMismatchError extends Error {
  constructor(frontendVersion: string, desktopVersion: string) {
    super(`App versions do not match (interface ${frontendVersion}, desktop ${desktopVersion}). Reinstall the app.`);
    this.name = 'VersionMismatchError';
  }
}

export async function handshakeDesktop(
  host: BridgeHost,
  frontendVersion: string,
  timeoutMs = 5000,
): Promise<AppInfo> {
  const api = await waitForDesktopApi(host, timeoutMs);
  const info = await api.get_app_info();
  if (info.version !== frontendVersion) {
    throw new VersionMismatchError(frontendVersion, info.version);
  }
  await api.frontend_ready({ version: frontendVersion });
  return info;
}

let desktopConnection: Promise<AppInfo> | undefined;

/** Share one handshake across React's development Strict Mode effect cycle. */
export function connectDesktop(): Promise<AppInfo> {
  desktopConnection ??= handshakeDesktop(window, __APP_VERSION__);
  return desktopConnection;
}

export interface Settings { download_directory: string; }
export type JobStatus = 'idle' | 'resolving' | 'downloading' | 'converting' | 'cancelling' | 'complete' | 'cancelled' | 'failed';
export interface JobState {
  job_id: string | null;
  status: JobStatus;
  busy: boolean;
  downloaded_bytes: number;
  total_bytes: number | null;
  fraction: number | null;
  directory: string | null;
  result: { path: string; title: string; video_id: string } | null;
  error: string | null;
}

// Track replies so the native window is not destroyed while Python is replying.
export class DesktopClient {
  private pending = new Set<Promise<unknown>>();
  private closing = false;
  private api: DesktopApi;
  constructor(api: DesktopApi) { this.api = api; }

  async call<T>(operation: (api: DesktopApi) => Promise<T>): Promise<T> {
    if (this.closing) throw new Error('The app is closing.');
    const request = Promise.resolve().then(() => operation(this.api));
    this.pending.add(request);
    try { return await request; }
    finally { this.pending.delete(request); }
  }

  async close(): Promise<void> {
    this.closing = true;
    while (this.pending.size) await Promise.allSettled([...this.pending]);
  }
}

export function progressLabel(job: JobState): string {
  switch (job.status) {
    case 'resolving': return 'Reading video information…';
    case 'downloading': return job.fraction === null ? 'Downloading audio…' : `Downloading audio · ${Math.round(job.fraction * 100)}%`;
    case 'converting': return 'Converting to MP3…';
    case 'cancelling': return 'Cancelling and cleaning up…';
    case 'complete': return 'Your MP3 is ready';
    case 'cancelled': return 'Download cancelled';
    case 'failed': return 'Could not finish this download';
    default: return 'Ready when you are';
  }
}
