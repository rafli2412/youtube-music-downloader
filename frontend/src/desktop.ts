export interface AppInfo {
  name: string;
  version: string;
  platform: string;
  architecture: string;
  packaged: boolean;
}

export interface DesktopApi {
  get_app_info(): Promise<AppInfo>;
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
