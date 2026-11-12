# YouTube Music Downloader

A terminal-first, personal-use YouTube / YouTube Music to MP3 app with a React desktop companion.

## Current status — phase 1 of 6

This is a **desktop foundation preview**, not a working downloader yet. The React window connects to
Python through pywebview. Conversion is deliberately disabled in the interface until the shared engine
is implemented in phase 2. The CLI currently offers `gui`, `doctor`, and `--version`.

Targets: **Windows x64** and **macOS Apple Silicon (arm64)**. Local Apple Silicon packaging is checked
with the scripts below; Windows packaging is prepared in GitHub Actions and must pass there before
being considered verified. Initial macOS target is macOS 13 or newer; a packaged build must also be
tested on its intended minimum OS version.

Local proof on 2026-11-12 (Apple Silicon, Python 3.11.18): 11 Python tests and 6 frontend tests passed;
production React build, typecheck, lint, and formatting passed. The packaged `.app` passed both the
offline dependency/MP3/JavaScript checks and the native React bridge check, then exited normally.
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
imports, executes all runtime tools, and creates/probes a short MP3 offline. The GUI check additionally
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

1. Set up the project and prove desktop packaging — current.
2. Build the shared Python download engine.
3. Finish the terminal interface first.
4. Build the React desktop interface.
5. Produce installable packages.
6. Verify the complete experience.

The finished MVP accepts one public YouTube or YouTube Music link at a time, creates an MP3, and
shares a persistent default download folder between CLI and GUI. The planned engine will use safe
filenames, preserve existing files, and clean up after cancellation or failure.
