# YouTube Music Downloader

Download audio from a public YouTube or YouTube Music link as a 192 kbps MP3.
Use the desktop window or run downloads from your terminal.

- Convert one video or song at a time.
- Choose a download folder once and reuse it across the desktop and terminal apps.
- Save files as `Video Title.mp3`, with `Video Title (2).mp3`, `(3)`, and so on when names repeat.
- Follow download progress, cancel a download, and open the destination folder.
- See the video title, channel, duration, publication date/time, and thumbnail while downloading
  and converting. Exact publication time is shown when YouTube provides it; otherwise the date is used.
- Select **Convert another video** after completion to clear the link and start again.

Packaged apps include Python, FFmpeg/ffprobe, and Deno. You do not need to install these tools or Node.js
when using a packaged app. Internet access is required to download audio.

## Supported computers

| Platform | Requirements |
| --- | --- |
| macOS | Apple Silicon, macOS 13 or newer |
| Windows | x64, Windows 10 build 19041 or newer, .NET Framework 4.8, Microsoft WebView2 |

The Windows installer checks prerequisites and installs WebView2 if missing; this requires internet
access. Portable Windows users must provide the prerequisites themselves. Compatibility testing on
clean computers and the minimum OS versions remains open; see [validation notes](docs/validation.md).

## Install

Use an installer built for your operating system. Locally built packages are in `dist/`. Packages
produced by GitHub Actions are available in the corresponding run's artifacts on the repository's
[Actions page](https://github.com/rafli2412/youtube-music-downloader/actions).

### macOS

1. Open `youtube-music-downloader-0.1.0-macos-arm64.dmg`.
2. Drag **YouTube Music Downloader** into **Applications** or your user's Applications folder.
3. Launch the installed app.

To enable the terminal command, run **Install terminal command.command** from the disk image after
copying the app. It creates `~/.local/bin/ytmp3` and prints instructions if that directory needs to be
added to your PATH. It does not edit your shell profile or replace an unrelated command.

The Mac build is ad-hoc signed and is not notarized. macOS may block downloaded copies.

### Windows

1. Run `youtube-music-downloader-0.1.0-windows-x64-setup.exe`.
2. Follow setup and optionally enable the desktop shortcut and terminal PATH integration.
3. Open **YouTube Music Downloader** from the Start menu.

Setup installs for the current user under `%LOCALAPPDATA%/Programs/YouTube Music Downloader`.
Open a new terminal after setup to use `ytmp3` by name. The personal-use Windows installer is unsigned.

### Portable packages

Extract the entire archive and keep its contents together. Open the `.app` on Mac or
`ytmp3-desktop.exe` on Windows. To run the terminal launcher directly:

macOS:

```sh
"./YouTube Music Downloader.app/Contents/MacOS/ytmp3" --help
```

Windows PowerShell:

```powershell
& ".\YouTube Music Downloader\ytmp3.exe" --help
```

## Use the desktop app

1. Copy a video or song link from your browser and paste it into the app.
2. Select **Choose folder** to set your download destination. The app remembers it.
3. Select **Preview video** to load its title, channel, duration, publication date/time, and thumbnail.
4. Check that it is the correct video. Optionally enter a filename; leave it blank to use the video
   title. A conservative English/Indonesian cleanup suggests an editable name, removing clear video,
   lyrics, official, quality, subtitle, and promotional labels while preserving the artist and musical
   versions such as remix, cover, and radio edit. A leading artist is omitted when it matches the
   channel name (ignoring case, extra spaces, and common channel labels such as `- Topic`, `Official`, `VEVO` (including `HindiaVEVO`),
   `Music`, `Records`, or `Channel`).
   Other artist prefixes stay. The original YouTube
   title remains in the preview. Use **Restore original** beside the filename to undo the suggestion
   or your edits. Ambiguous song names such as “Lyrics” and “Video” are preserved, and running cleanup
   again leaves the suggestion unchanged. The app adds `.mp3` and numbers duplicate names automatically.
   Select **Download MP3**. Editing the link clears the preview
   and requires a new review. Previewing does not download the audio.
5. When finished, select **Open folder** to find the file, or **Convert another video** to clear the
   previous link and result while keeping your selected folder.

Use **Cancel** to stop a download. Closing the window during a job cancels it and waits for cleanup.
Existing files are preserved. On Mac, select an MP3 in Finder and press Space to preview it, or open
it with QuickTime Player.

## Use the terminal app

With `ytmp3` on your PATH:

```sh
# Download a video to your saved folder.
ytmp3 "https://www.youtube.com/watch?v=VIDEO_ID"

# YouTube Music links work too.
ytmp3 download "https://music.youtube.com/watch?v=VIDEO_ID"

# Save a default folder shared with the desktop app.
ytmp3 config set download-dir "~/Music/YouTube"
ytmp3 config show

# Use a different folder for this download only.
ytmp3 "https://youtu.be/VIDEO_ID" --directory "./my downloads"

# Other commands.
ytmp3           # Prompt for a link in an interactive terminal.
ytmp3 gui       # Open the desktop window.
ytmp3 doctor    # Check bundled tools with an offline conversion.
ytmp3 --help
```

Replace `VIDEO_ID` with the ID in your actual browser link, or paste the complete link. Quote URLs so
characters such as `&` are passed intact. Press **Ctrl+C** to cancel. Successful downloads print
`Saved: <path>`; progress goes to stderr.

## Run from source without packaging

Development requires Python 3.11–3.15 and Node.js 22.12 or newer. Python 3.13 is used in CI.
Run these commands from the project folder. Runtime tools are fetched once during setup.

macOS:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev,desktop,build]'
.venv/bin/python scripts/fetch_tools.py
npm ci --prefix frontend
npm run build --prefix frontend
.venv/bin/ytmp3 gui
```

Windows PowerShell:

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python -m pip install -e '.[dev,desktop,build]'
.venv\Scripts\python scripts/fetch_tools.py
npm ci --prefix frontend
npm run build --prefix frontend
.venv\Scripts\ytmp3 gui
```

For terminal downloads, replace `gui` with a quoted video URL. After editing React code, run
`npm run build --prefix frontend` again before launching. Packaging an installer is not required.

If you are using this workspace's existing packaging environment on Mac, launch directly with:

```sh
.python/build-env/bin/ytmp3 gui
```

### Live development updates

Run one command to start Vite and the desktop together:

```sh
# macOS, using an existing development environment:
.python/build-env/bin/python scripts/dev.py
# Or with the standard setup:
.venv/bin/python scripts/dev.py
```

Windows PowerShell:

```powershell
.venv\Scripts\python scripts/dev.py
```

React and CSS changes update immediately without rebuilding. Python and app-icon changes automatically
close the desktop safely and reopen it; active jobs are cancelled and cleaned up before the restart.
Python restarts reset the current preview and window state. Close the desktop window or press Ctrl+C
in the development terminal to stop both processes. Start this mode once instead of running a separate
Vite server; it uses port 5173.

## Build an installer

Build on the target operating system and architecture using an activated development environment:

```sh
python scripts/fetch_tools.py
npm run build --prefix frontend
python scripts/build_desktop.py
python scripts/build_installers.py
```

Outputs are written to `dist/`: a `.dmg` and portable `.tar.gz` for Mac, or a setup `.exe` and portable
`.zip` for Windows, with a `SHA256SUMS` file. Windows builds require Inno Setup 7 or 6.3+.
Mac builds require Python and compiled dependencies targeting macOS 13 or older; the build audits
bundled native binaries against the app's declared minimum OS.

## Troubleshooting and limitations

- Only single public videos or songs are supported. Playlist-only links, active livestreams, and
  account-restricted content are rejected. A video link containing playlist parameters downloads
  only that video.
- YouTube may request verification or deny a public video on some networks or in some regions.
  For a verification rejection, the app waits 10 seconds and retries once with a fresh guest session.
  Cancellation remains available during the wait. Persistent verification is reported as an error.
  Try another public link or retry later. The app does not support signing in or importing cookies.
- If a destination cannot be written, choose a local writable folder. Mac destinations must support
  hard links, such as an APFS volume.
- Run `ytmp3 doctor` to check runtime tools. This is an offline check and does not test YouTube access.

## Uninstall

On Mac, quit the app and move it to Trash. Run **Remove terminal command.command** from the disk image
if you installed the terminal helper. On Windows, uninstall through **Settings → Apps**. Removal keeps
settings and downloaded MP3s, preserves unrelated PATH entries, and leaves shared WebView2 installed.
