# YouTube Music Downloader

A terminal-first, personal-use YouTube / YouTube Music to MP3 app with a React desktop companion.

## Current status — phase 2 of 6

The shared Python engine now downloads one public YouTube / YouTube Music video and converts its audio
to a verified 192 kbps MP3. It supports progress callbacks, cancellation, saved folder settings, and
safe filenames without replacing existing files. Retrieval runs in an isolated spawned process.

The React window remains a **desktop foundation preview**: conversion controls are wired in phase 4.
The CLI still offers `gui`, `doctor`, and `--version`; user-facing download/config commands arrive in
phase 3. The developer check below can exercise the engine now.

Targets: **Windows x64** and **macOS Apple Silicon (arm64)**. Local Apple Silicon packaging is checked
with the scripts below; Windows packaging is prepared in GitHub Actions and must pass there before
being considered verified. Initial macOS target is macOS 13 or newer; a packaged build must also be
tested on its intended minimum OS version.

Local proof on 2026-11-12 (Apple Silicon, Python 3.11.18): engine integration tests use real spawned
workers and FFmpeg/ffprobe with synthetic audio. A separate live check downloaded and converted the
public "Me at the zoo" video. The old yt-dlp test clip was unavailable and failed cleanly.
The initial archive is approximately 115.6 MB compressed (110.3 MiB); dependency size optimization
is still pending. This is not yet a clean-machine installation test.

## Development setup

Use Python 3.11–3.15 and Node.js 22.12 or newer. CI uses Python 3.13 and Node 22; the initial local
packaging proof uses Python 3.11. These tools are needed for development, not by packaged app users.

macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,desktop,build]'
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/ytmp3 gui
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev,desktop,build]'
npm ci --prefix frontend
npm run build --prefix frontend
.venv\Scripts\ytmp3 gui
```

The Windows desktop UI requires Microsoft's WebView2 runtime and .NET Framework 4.6.2 or newer.
Modern Windows generally provides these; this phase produces a portable application folder, not an
installer that provisions prerequisites. WebView2 installation handling belongs to phase 5.

For React hot reload, run `npm run dev --prefix frontend` in one terminal, then
`ytmp3 gui --dev-url http://127.0.0.1:5173` from the activated Python environment in another.
Development URLs are restricted to loopback HTTP and disabled in packaged builds.

## Exercise the shared engine

From an activated environment with runtime tools fetched:

```sh
# Offline integration: spawned retrieval fixture, real conversion, validation, and publication.
python scripts/check_engine.py

# Live integration: a single public link, with an explicit destination.
python scripts/check_engine.py --url "https://www.youtube.com/watch?v=jNQXAC9IVRw" --directory build/live-engine-proof
```

The live check uses network access and saves a real MP3. Automated tests and the packaged `doctor`
probe use synthetic audio and do not contact YouTube. The script is a development tool; the regular
terminal download workflow is implemented in phase 3.

The core API is `DownloadEngine(settings).download(url, directory=None, on_progress=None, cancel=None)`.
`cancel` is a `threading.Event`; callbacks receive a `DownloadProgress` with a stage and optional byte
progress. Conversion progress is indeterminate. The blocking call should run on a background thread
in the GUI. Only one job may run per engine instance. `DownloadResult` contains the final path, title,
and video ID. Failures are raised as exceptions; user cancellation raises `DownloadCancelled`.
Callers should catch `DownloadError`, `SettingsError`, and `InvalidYouTubeURL` for actionable failures.

Use `SettingsStore().set_download_directory(path)` to save a default, shared by future CLI and GUI
commands. Settings are written atomically to:

- macOS: `~/Library/Application Support/YouTube Music Downloader/settings.json`.
- Windows: `%APPDATA%/YouTube Music Downloader/settings.json`.

Without saved settings, the default is `~/Downloads`. A per-job directory override does not change
the saved default. Invalid settings and unwritable destinations produce readable errors.

Supported links include normal watch links, YouTube Music links, `youtu.be`, Shorts, embed links, and
finished live-video links. Playlist/tracking parameters on a video are removed; playlist-only links,
active/upcoming streams, and account-restricted content are rejected. YouTube may still deny a public
video because it is unavailable in a region or because it requires verification.

Files are named `Title [video-id].mp3`, with numbered suffixes for collisions. Temporary downloads and
conversion outputs are cleaned after success, failure, or cancellation. Completed output is published
without overwriting another file; once published, a late cancellation does not delete it. On macOS,
safe atomic publication requires a filesystem supporting hard links (such as APFS); unsupported
destinations get an error requesting a local folder. Existing files are always preserved.

## Package a native desktop app

Build on the target OS and architecture. Windows cannot be packaged from macOS.
From an activated virtual environment:

```sh
python scripts/fetch_tools.py
npm run build --prefix frontend
python scripts/build_desktop.py
python scripts/verify_bundle.py --headless --report build/reports/bundle-headless.json
python scripts/verify_bundle.py --gui --report build/reports/bundle-gui.json
```

If the development Python installation lacks CA roots, specify a trusted PEM bundle with
`fetch_tools.py --ca-bundle <path>` (for example `/etc/ssl/cert.pem` on macOS). TLS verification stays
enabled. Tool downloads happen at build time, never when a user starts the packaged app.

Output:

- macOS: `dist/YouTube Music Downloader.app` and `dist/youtube-music-downloader-macos-arm64.tar.gz`.
- Windows: `dist/YouTube Music Downloader/ytmp3-desktop.exe` and
  `dist/youtube-music-downloader-windows-x64.zip`. Keep the entire extracted directory together.
- Evidence: `build/reports/`, including package size and smoke-test results.

The archive contains Python, the React assets, yt-dlp and its EJS scripts, FFmpeg/ffprobe, and Deno.
The GUI is a native window using the system webview; its bundled assets are served by pywebview's
private local static-file server. React calls the Python bridge directly.

The headless check launches the packaged executable from a temporary working directory with Python
environment variables and development PATH entries removed. It verifies resources and package
imports, executes all runtime tools, and runs the shared engine through a spawned synthetic-audio
worker and real MP3 conversion/publication offline. The GUI check additionally
waits for the actual React-to-Python round trip in a native window. These checks on a development
machine do **not** replace final testing on a clean computer without Python installed.

macOS builds are ad-hoc signed by the bundler, not Developer ID signed or notarized. Phase 1 does not
provide a public release installer, automatic updates, or a packaged terminal launcher.

### Pinned runtime tools

`packaging/tool-manifest.json` records fixed URLs, SHA-256 values, source/build links, and attribution.
`scripts/fetch_tools.py --verify` checks the existing vendor files without using the network.

| Target | FFmpeg / ffprobe | JavaScript runtime |
| --- | --- | --- |
| macOS arm64 | 9.0.2, Martin Riedl native build | Deno 2.9.8 |
| Windows x64 | 6.1.1, eugeneware static build | Deno 2.9.8 |

These FFmpeg builds include the MP3 encoder. Each package carries tool provenance, build details,
and license files. Generated binaries and dependency caches are ignored by Git.

## Checks

```sh
python scripts/fetch_tools.py
python -m unittest discover -s tests -v
python -m ruff check .
python -m ruff format --check .
npm test --prefix frontend
npm run build --prefix frontend
```

The packaging workflow runs native Windows x64 and macOS arm64 builds. The required headless check
does not claim that a window rendered. Use the workflow's `run_gui_smoke` manual input on a runner
with an interactive desktop to request the native-window check. Download the generated archives
rather than uploading the application directory directly, so executable permissions and symlinks survive.

## Project layout

```text
src/ytmp3/            Shared Python package, source CLI, desktop bridge, diagnostics
frontend/            React + TypeScript + Vite UI and bridge tests
packaging/           PyInstaller specification and pinned tool manifest
scripts/             Tool acquisition, native build, packaged-app verification
tests/               Python foundation and acquisition checks
.github/workflows/   Native packaging matrix
```

## Development steps

1. Set up the project and prove desktop packaging — implemented; Windows proof remains pending CI.
2. Build the shared Python download engine — current.
3. Finish the terminal interface first.
4. Build the React desktop interface.
5. Produce installable packages.
6. Verify the complete experience.

The finished MVP accepts one public YouTube or YouTube Music link at a time, creates an MP3, and
shares a persistent default download folder between CLI and GUI. The planned engine will use safe
filenames, preserve existing files, and clean up after cancellation or failure.
