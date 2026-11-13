# MVP validation record

Validation dates: 2026-11-12–13 (Asia/Jakarta). App version: 0.1.0.

Phase 6 verifies the terminal and desktop flows, packaged dependencies, and installation/removal.
The application behavior comes from phase 5 (`e3c4b64`). Phase 6 corrects a Windows test that counted
the `taskkill` cleanup helper as another converter.
It also checks cancellation before launching FFmpeg/ffprobe: a Windows integration run exposed a
temporary-file lock when conversion was started after cancellation had already been requested.
The regression test proves that this case starts no converter and creates no temporary files.
The final local artifacts include the application fix at `5823632` and use the project-local
`.python/build-env` packaging environment.
It also makes the Windows installer verifier explicitly wait for the windowed desktop executable,
capture its exit code/output, and stop it on timeout before attempting removal. PowerShell can return
from a direct GUI executable invocation before it exits; see the
[PowerShell team's process guidance](https://devblogs.microsoft.com/powershell/managing-processes-in-powershell/).
The verifier also waits for Inno's final uninstaller-file removal and uses the installation registry
entry when deciding whether cleanup needs another uninstall attempt.

The initial local Mac package bundled Python and libraries requiring macOS 27 despite declaring
macOS 13. That package was moved to `build/rejected-macos-phase5` and replaced. Archive and DMG builds
now reject native binaries whose deployment target exceeds the app's plist minimum. The replacement
uses CPython 3.13.18 from [python-build-standalone's 20261110 release](https://github.com/astral-sh/python-build-standalone/releases/tag/20261110),
with the download verified against the release asset's SHA-256:
`1afd3983237c2a10277345f235be730e9cb49a123e0574ed252dbf3a841a24e4`.

## Automated results

The local machine is Apple Silicon running macOS 27.2, Python 3.13.18, and Node 26.13.0. CI uses
native macOS arm64 and Windows x64 hosts with Python 3.13 and Node 22.

| Check | Result | Evidence |
| --- | --- | --- |
| Python tests | 77 passed locally | `build/reports/tests-phase6.txt` |
| Python lint, formatting, dependency consistency | Passed | `ruff check`, `ruff format --check`, `pip check` |
| Frontend bridge tests | 9 passed | `npm test --prefix frontend` |
| TypeScript and production React build | Passed | `npm run build --prefix frontend` |
| Packaged Mac CLI: version, help, offline engine | Passed | `build/reports/phase6-cli.json` |
| Packaged Mac desktop dependencies and offline engine | Passed | `build/reports/phase6-headless.json` |
| Packaged Mac native window and React/Python round trip | Passed | `build/reports/phase6-gui.json` |
| Mac native deployment targets | 59 binaries passed; all within the declared macOS 13 minimum | `build/reports/macos-compatibility.json` |
| Mac DMG integrity, isolated install, both launchers, terminal helper/removal | 8 checks passed | `build/reports/phase6-install-macos.json` |
| Mac DMG and portable archive SHA-256 | Matched | `dist/youtube-music-downloader-0.1.0-macos-arm64.SHA256SUMS` |
| Native Mac CI build and installer checks | Passed | [Mac CI job](https://github.com/rafli2412/youtube-music-downloader/actions/runs/43262108002/job/131335858066) |
| Native Windows CI build, installed launchers, PATH preservation, uninstall/download preservation | 4 installation checks passed | [Windows CI job](https://github.com/rafli2412/youtube-music-downloader/actions/runs/43264082919/job/131342965379) |

Those linked jobs record the earlier native packaging/installer proofs. Subsequent phase 6 fixes and
the final documentation are checked in the [validation branch's CI runs](https://github.com/rafli2412/youtube-music-downloader/actions?query=branch%3Avalidation%2Fphase-6).

The packaged checks remove development PATH entries and Python environment variables, use a temporary
working directory, and exercise spawned workers plus real FFmpeg/ffprobe conversion. They demonstrate
that bundled dependencies work on these hosts. They do not establish clean-machine compatibility.
Reports and generated binaries are intentionally ignored by Git; CI uploads its reports and packages
as workflow artifacts with 14-day retention.

## Behavior covered

Automated tests cover supported single-video URL forms, rejection of invalid and restricted inputs,
persistent shared folder settings, paths containing spaces/Unicode, safe filenames, collision handling,
real MP3 conversion, worker errors/crashes, cancellation and process cleanup, recovery after failure,
and preservation of existing output/settings. The CLI tests cover interactive and redirected input,
progress, errors, exit codes, and cancellation. A real OS-level SIGINT test runs on macOS; Windows
process cleanup uses `taskkill` and is exercised by the native Windows integration test.

The phase 4 manual Mac GUI session verified the native folder picker, remembered destination, successful
conversion, Open folder, readable failure, disabled controls during work, cancellation, recovery, and
quitting during a download without leaving temporary files or processes. Controlled retrieval fixtures
were used with the real conversion engine. The phase 6 packaged native-window check verifies startup
and the bridge; it does not repeat every manual click path.

A live public-video download succeeded earlier through the shared engine and packaged CLI. Later live
GUI and CLI checks both received YouTube's verification requirement on this network. Live availability
therefore remains dependent on YouTube and the connection; offline success does not prove a particular
public link can currently be retrieved. Login, cookie import, and verification bypasses are outside scope.

## Before calling the MVP fully verified

Complete these on disposable Windows x64 and Apple Silicon macOS accounts or machines with no Python,
Node, FFmpeg, or Deno installed. Record the OS version, artifact checksum, result, and any error text.

- Install the native package, launch the GUI, and run `ytmp3 --version` and `ytmp3 doctor` from a new
  terminal. On Windows, also test first installation when WebView2 is missing and failure/retry when
  its download is unavailable. Existing CI runtimes do not establish those prerequisite paths.
- Set a folder containing spaces and Unicode, restart, and confirm that both the GUI and
  `ytmp3 config show` remember it. Download a permitted public video through each interface, play the
  MP3, and repeat a download to confirm the original file is preserved.
- Check an invalid link, an unavailable public video, and a destination that cannot be written. Confirm
  a readable error, no partial output, and that a subsequent valid download succeeds.
- Cancel from the GUI and with Ctrl+C in a real Windows terminal. Quit the GUI during active work;
  confirm its workers stop and temporary files disappear. Relaunch and download again.
- Remove the app/terminal integration and confirm existing MP3s, settings, unrelated commands, and
  unrelated PATH entries remain. The automated installer checks cover isolated removal; also exercise
  the actual desktop install/uninstall flow.
- Test on the intended minimum versions: macOS 13 and Windows 10 build 19041 with .NET Framework 4.8.
  Successful checks on newer hosts do not establish those minimums.

These manual acceptance checks remain open. Windows native GUI interaction has not yet been observed.
The personal-use packages are unsigned on Windows and ad-hoc signed on Mac; distribution signing and
Mac notarization are not part of this proof.

## Artifacts

The local Mac DMG is approximately 130 MiB; the portable archive is approximately 122 MiB. The checked
Windows CI build produced an approximately 102 MiB installer and 130 MiB portable ZIP. Keep the
whole bundle together. All runtime tools and Python are bundled; Node is only a development dependency.
Size reduction remains a possible follow-up, rather than a completed optimization.

Local DMG SHA-256:

```text
fda9f992b649bae789ae96bbfa550a23ea7365f4341f33c7ad18875a2289df72
```

Checksums apply to specific generated files. A fresh build can have different bytes; use its accompanying
`SHA256SUMS` file rather than assuming it matches this local artifact.
