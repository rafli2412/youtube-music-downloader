# YouTube Music Downloader

A terminal-first, personal-use YouTube / YouTube Music to MP3 app with a React desktop companion.

## Current status — phase 6 of 6

The shared Python engine now downloads one public YouTube / YouTube Music video and converts its audio
to a verified 192 kbps MP3. It supports progress callbacks, cancellation, saved folder settings, and
safe filenames without replacing existing files. Retrieval runs in an isolated spawned process.

The React desktop window now downloads audio through the shared engine. It includes a native folder
picker, persistent destination, progress, cancellation, readable errors, results, and an Open folder
action. Closing the window cancels active work and waits for cleanup before exiting.
The terminal interface now supports direct URL downloads, interactive prompting, saved default folders,
per-download folder overrides, progress, readable errors, and Ctrl+C cancellation. Native packages
include both a console launcher and the desktop launcher, sharing the same runtime dependencies.

Targets: **Windows x64** and **macOS Apple Silicon (arm64)**. Native builds and isolated installer
checks have passed on both targets. The Mac package declares macOS 13 or newer and its bundled native
code is checked against that minimum. Clean-machine, minimum-OS, and manual Windows desktop acceptance
checks remain; see the validation record below.

Local proof on 2026-11-12 (Apple Silicon, Python 3.11.18): engine integration tests use real spawned
workers and FFmpeg/ffprobe with synthetic audio. A separate live check downloaded and converted the
public "Me at the zoo" video. The old yt-dlp test clip was unavailable and failed cleanly.
Phase 3 verification adds terminal behavior tests, a real OS-level Ctrl+C test, and a live download
through the packaged console executable with development PATH entries removed. Both console and
desktop launchers pass the native Apple Silicon smoke checks. The current archive is approximately
128 MB compressed; dependency size optimization is still pending. These checks do not replace a
clean-machine installation test.

Phase 4 adds desktop job/bridge tests and manual native-window checks for folder selection, conversion,
results, Open folder, failure, cancellation, and quitting during a job. These use controlled audio
fixtures in an isolated session. A live GUI check encountered YouTube's verification requirement;
the CLI received the same response on this connection. The app does not import cookies or sign in.

Phase 6 repeats the local packaged CLI, offline conversion, native-window/bridge, DMG installation,
and checksum checks. All 77 Python tests and 9 frontend tests pass locally. Windows CI verifies the
installer, both installed launchers, PATH preservation, and removal. The Mac package is rebuilt with
a compatible Python 3.13 runtime; archive and DMG creation now reject bundled binaries requiring a
newer OS than the app declares.
Cancellation is checked before starting an audio tool, avoiding unnecessary converter launches and
temporary-file races when cancellation arrives as conversion begins.
See the [validation record](docs/validation.md) for evidence and the remaining clean-machine,
minimum-OS, Windows desktop, and live-network acceptance checks.

## Development setup

Use Python 3.11–3.15 and Node.js 22.12 or newer. CI uses Python 3.13 and Node 22; the initial local
packaging proof uses Python 3.11. These tools are needed for development, not by packaged app users.
For Mac packaging, use a Python distribution and compiled dependencies built for macOS 13 or older.
The final local package uses Python 3.13.18; the build audits every bundled native binary's deployment
target before producing an archive or DMG.

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

The Windows installer targets x64 Windows 10 build 19041 or newer (including Windows 11), checks for
.NET Framework 4.8, and installs Microsoft WebView2 if missing. The WebView2 bootstrapper needs
internet access in that case. Portable ZIP users must provide those system prerequisites themselves.

For React hot reload, run `npm run dev --prefix frontend` in one terminal, then
`ytmp3 gui --dev-url http://127.0.0.1:5173` from the activated Python environment in another.
Development URLs are restricted to loopback HTTP and disabled in packaged builds.

## Use the desktop app

Launch the packaged app normally, or run `ytmp3 gui` in the development environment. Paste one video
or song link, choose the download folder if desired, and select **Convert to MP3**. The selected folder
is remembered and shared with the terminal interface. Download progress shows a percentage when the
size is available; resolving and conversion remain indeterminate. Use **Cancel** to stop active work.

On completion, the title and full MP3 path appear with **Open folder**. Existing files are preserved.
The app keeps one active job and disables destination changes while it is running. Closing the window
or quitting cancels the job, waits for temporary-file/process cleanup, and then exits. A late cancel
after publication keeps the finished MP3.

If YouTube asks for verification, the app shows a readable message suggesting another public link or
retrying later. Public access does not guarantee YouTube will accept every request from every network.

For isolated manual QA without changing normal app preferences:

```sh
python scripts/check_desktop.py --directory build/desktop-check --offline
```

This opens the real React window with a real conversion engine and synthetic retrieval fixtures:
`https://youtu.be/BaW_jenozKc` succeeds, `https://youtu.be/abcdefghijk` fails, and
`https://youtu.be/jNQXAC9IVRw` waits for cancellation. Settings and files stay inside the supplied test
directory. Omit `--offline` to use real public links. This developer script does not automate UI input.

## Use the terminal app

From an activated development environment, or with the packaged `ytmp3` on your PATH:

```sh
# Download one video or song to the default folder.
ytmp3 "https://www.youtube.com/watch?v=jNQXAC9IVRw"
ytmp3 download "https://music.youtube.com/watch?v=VIDEO_ID"

# Save your default once; it also applies to the GUI download workflow.
ytmp3 config set download-dir "~/Music/YouTube"
ytmp3 config show

# Override the folder for this download without changing the saved default.
ytmp3 "https://youtu.be/jNQXAC9IVRw" --directory "./my downloads"

# Launch without arguments in a terminal to be prompted for one link.
ytmp3
ytmp3 gui
ytmp3 doctor
```

Replace `VIDEO_ID` with the real video ID from a browser link. Quote links so shell characters such as
`&` are passed intact. Only one item is downloaded, including when a video link contains playlist
parameters. With redirected/non-interactive input, a URL is required and the app never waits for a
prompt. EOF at the interactive prompt exits without starting a job.

Progress is written to stderr; the final `Saved: <path>` line is written to stdout. Interactive terminals
show download percentage/bytes when available and an indeterminate conversion stage. Redirected logs
get one line per stage without control sequences. Press Ctrl+C to cancel and clean up temporary files.
Exit codes: `0` success (or prompt EOF), `1` download/settings/runtime failure, `2` usage or invalid link,
`130` cancellation. An output already published before cancellation remains a successful download.

Packaged apps include Python and the tools, so they can be used from a terminal without installing
Python or Node. After extracting the archive, run the console launcher directly:

macOS:

```sh
"./YouTube Music Downloader.app/Contents/MacOS/ytmp3" --help
"./YouTube Music Downloader.app/Contents/MacOS/ytmp3" "https://youtu.be/jNQXAC9IVRw"
```

Windows PowerShell:

```powershell
& ".\YouTube Music Downloader\ytmp3.exe" --help
& ".\YouTube Music Downloader\ytmp3.exe" "https://youtu.be/jNQXAC9IVRw"
```

Keep the complete app/folder together; the launchers share its bundled resources. The Windows
installer offers user PATH integration; the Mac disk image includes an optional terminal helper.
Terminal downloads do not open a GUI window or initialize pywebview.

## Install the app

### Apple Silicon macOS

Open `youtube-music-downloader-0.1.0-macos-arm64.dmg`, drag the app to Applications, eject the image,
and launch the installed copy. Your user's Applications folder works too. No Python, Node, FFmpeg,
or Deno installation is needed. The image includes an Applications link and short install notes.

For the terminal interface, run **Install terminal command.command** from the image after copying
the app. It creates `~/.local/bin/ytmp3`; if that directory is not already on your PATH, the helper
prints the shell setup line. It does not edit shell profiles automatically or replace an unrelated
command. **Remove terminal command.command** removes only the matching link, even if the app has
already been deleted. Remove the GUI by quitting it and moving the app to Trash. Settings and MP3s
are preserved. The console executable inside the app can also be called directly without a helper.

This personal-use build is ad-hoc signed, not Developer ID signed or notarized. Downloaded copies
may be blocked by macOS. A public release requires appropriate signing/notarization; these scripts
do not bypass or change Gatekeeper settings. No signing identity is available on the build machine.

### Windows x64

Run `youtube-music-downloader-0.1.0-windows-x64-setup.exe` produced by the Windows build. It installs
for the current user under `%LOCALAPPDATA%/Programs/YouTube Music Downloader`, creates a Start menu
shortcut, offers a desktop shortcut, and offers to add the app folder to the user PATH. Open a new
terminal after installation to use `ytmp3` by name. The installer does not request administrator access.

Before copying app files, setup checks .NET Framework 4.8 and detects WebView2 in both user and machine
registry locations. If WebView2 is absent, it runs the bundled Microsoft bootstrapper and checks the
result. Network/policy failures stop installation with retry instructions; a required restart is
reported without forcing one. WebView2 is shared with other apps and remains after app removal.

Uninstall through Windows Settings > Apps. The uninstaller removes only the app-owned PATH entry,
preserving pre-existing entries and entries added later. Downloaded files and app settings remain.
This personal-use installer is unsigned; public distribution needs an appropriately signed build.
Windows CI compiles the installer and verifies isolated installation, both launchers, PATH ownership,
and removal. Manual Windows desktop and clean-machine checks remain open.

## Exercise the shared engine

From an activated environment with runtime tools fetched:

```sh
# Offline integration: spawned retrieval fixture, real conversion, validation, and publication.
python scripts/check_engine.py

# Live integration: a single public link, with an explicit destination.
python scripts/check_engine.py --url "https://www.youtube.com/watch?v=jNQXAC9IVRw" --directory build/live-engine-proof
```

The live check uses network access and saves a real MP3. Automated tests and the packaged `doctor`
probe use synthetic audio and do not contact YouTube. The script remains available for developer
integration checks; normal use goes through the terminal commands above.

The core API is `DownloadEngine(settings).download(url, directory=None, on_progress=None, cancel=None)`.
`cancel` is a `threading.Event`; callbacks receive a `DownloadProgress` with a stage and optional byte
progress. Conversion progress is indeterminate. The blocking call should run on a background thread
in the GUI. Only one job may run per engine instance. `DownloadResult` contains the final path, title,
and video ID. Failures are raised as exceptions; user cancellation raises `DownloadCancelled`.
Callers should catch `DownloadError`, `SettingsError`, and `InvalidYouTubeURL` for actionable failures.

Use `SettingsStore().set_download_directory(path)` to save a default, shared by CLI and GUI
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
python scripts/verify_bundle.py --cli --report build/reports/bundle-cli.json
python scripts/verify_bundle.py --headless --report build/reports/bundle-headless.json
python scripts/verify_bundle.py --gui --report build/reports/bundle-gui.json
python scripts/build_installers.py
```

If the development Python installation lacks CA roots, specify a trusted PEM bundle with
`fetch_tools.py --ca-bundle <path>` (for example `/etc/ssl/cert.pem` on macOS). TLS verification stays
enabled. Tool downloads happen at build time, never when a user starts the packaged app.

Output:

- macOS: `dist/YouTube Music Downloader.app` (console launcher at `Contents/MacOS/ytmp3`) and
  `dist/youtube-music-downloader-macos-arm64.tar.gz`.
- Windows: `dist/YouTube Music Downloader/ytmp3.exe`, `ytmp3-desktop.exe` in the same directory, and
  `dist/youtube-music-downloader-windows-x64.zip`. Keep the entire extracted directory together.
- Evidence: `build/reports/`, including package size and smoke-test results.
- Installers: a versioned `.dmg` on macOS or `*-windows-x64-setup.exe` on Windows, plus a target-specific
  `*.SHA256SUMS` file covering the installer and portable archive.

The archive contains Python, the React assets, yt-dlp and its EJS scripts, FFmpeg/ffprobe, and Deno.
The GUI is a native window using the system webview; its bundled assets are served by pywebview's
private local static-file server. React calls the Python bridge directly.

The headless check launches the packaged executable from a temporary working directory with Python
environment variables and development PATH entries removed. It verifies resources and package
imports, executes all runtime tools, and runs the shared engine through a spawned synthetic-audio
worker and real MP3 conversion/publication offline. The CLI check verifies the console launcher's
version/help output and runs `doctor` through that launcher, including frozen worker startup.
The GUI check additionally
waits for the actual React-to-Python round trip in a native window. These checks on a development
machine do **not** replace final testing on a clean computer without Python installed.

On Mac, both the archive build and DMG build audit all bundled Mach-O files against
`LSMinimumSystemVersion`. `build/reports/macos-compatibility.json` records the result. A Python runtime
compiled for a newer OS must be replaced with a compatible build; changing the app's plist alone
cannot make its dependencies work on older systems. This static audit complements minimum-OS testing.

On Windows, `build_installers.py` uses Inno Setup 7 or 6.3+ (the GitHub runner includes Inno Setup).
It locates `ISCC.exe` on PATH or in the standard Inno Setup folders; pass `--iscc <path>` to override.
The bootstrapper is downloaded from Microsoft at build time using the committed SHA-256 pin in
`packaging/prerequisites.json`, and its Microsoft Authenticode signature is checked before compilation.
Microsoft can update the download URL's bytes: a checksum mismatch intentionally stops the build and
requires review/repinning. App launch never downloads build dependencies.

Verify the installable artifact on its target OS:

```sh
# Mac: mount read-only, copy into an isolated directory, check both launchers and helpers.
python scripts/verify_macos_install.py
```

```powershell
# Windows: PowerShell 7, disposable user/CI account, guarded against replacing an existing install.
pwsh -NoProfile -File ./scripts/verify_windows_install.ps1 -Installer ./dist/youtube-music-downloader-0.1.0-windows-x64-setup.exe
```

The Mac check does not install into `/Applications`, modify shell profiles, or write normal app
preferences. It validates the image, copied code-signature integrity, frozen engines, terminal-link
setup/removal, and preservation of an unrelated command. The Windows check installs into a generated
test folder, runs both offline launchers with development PATH entries removed, tests PATH ownership
and uninstall preservation, then cleans up its test installation. It leaves shared WebView2 installed
if setup needed it. Neither check establishes clean-machine or public-release signing readiness.

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

The packaging workflow runs native Windows x64 and macOS arm64 builds and verifies both launchers.
The required headless check
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

1. Set up the project and prove desktop packaging — implemented; native CI proof passed on both targets.
2. Build the shared Python download engine — implemented.
3. Finish the terminal interface first — implemented.
4. Build the React desktop interface — implemented.
5. Produce installable packages — implemented; Mac image and Windows installer checks passed.
6. Verify the complete experience — automated checks passed; manual acceptance remains tracked in
   [the validation record](docs/validation.md).

The finished MVP accepts one public YouTube or YouTube Music link at a time, creates an MP3, and
shares a persistent default download folder between CLI and GUI. The engine uses safe
filenames, preserves existing files, and cleans up after cancellation or failure.
