import test from 'node:test';
import assert from 'node:assert/strict';
import { handshakeDesktop, VersionMismatchError, waitForDesktopApi } from '../src/desktop.ts';

function fakeHost() {
  const host = new EventTarget();
  return host;
}

const api = {
  async get_app_info() {
    return { name: 'YouTube Music Downloader', version: '0.1.0', platform: 'Darwin', architecture: 'arm64', packaged: true };
  },
  async frontend_ready() { return {}; },
};

test('connects when the bridge was ready before React mounted', async () => {
  const host = fakeHost();
  host.pywebview = { api };
  assert.equal(await waitForDesktopApi(host, 100), api);
});

test('waits for the desktop readiness event when the bridge is injected later', async () => {
  const host = fakeHost();
  const ready = waitForDesktopApi(host, 100);
  host.pywebview = { api };
  host.dispatchEvent(new Event('pywebviewready'));
  assert.equal(await ready, api);
});

test('does not claim a browser preview is connected', async () => {
  await assert.rejects(waitForDesktopApi(fakeHost(), 5), /Desktop connection unavailable/);
});

test('ignores a readiness event until the expected bridge methods exist', async () => {
  const host = fakeHost();
  const ready = waitForDesktopApi(host, 100);
  host.pywebview = { api: {} };
  host.dispatchEvent(new Event('pywebviewready'));
  host.pywebview = { api };
  host.dispatchEvent(new Event('pywebviewready'));
  assert.equal(await ready, api);
});

test('sends the interface build version in the readiness acknowledgement', async () => {
  const host = fakeHost();
  let acknowledgement;
  host.pywebview = {
    api: {
      ...api,
      async frontend_ready(payload) { acknowledgement = payload; },
    },
  };
  const info = await handshakeDesktop(host, '0.1.0', 100);
  assert.equal(info.version, '0.1.0');
  assert.deepEqual(acknowledgement, { version: '0.1.0' });
});

test('rejects stale interface files without acknowledging readiness', async () => {
  const host = fakeHost();
  let acknowledged = false;
  host.pywebview = {
    api: {
      ...api,
      async frontend_ready() { acknowledged = true; },
    },
  };
  await assert.rejects(handshakeDesktop(host, '0.0.9', 100), (error) => {
    assert.ok(error instanceof VersionMismatchError);
    assert.match(error.message, /interface 0\.0\.9, desktop 0\.1\.0/);
    assert.match(error.message, /Reinstall the app/);
    return true;
  });
  assert.equal(acknowledged, false);
});
