"""Terminal behavior without network access or writes to the user's settings."""

from __future__ import annotations

import io
import signal
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from ytmp3 import cli
from ytmp3.engine import DownloadCancelled, DownloadError, DownloadProgress, DownloadResult
from ytmp3.settings import SettingsError, SettingsStore

URL = "https://youtu.be/jNQXAC9IVRw"


class TerminalStream(io.StringIO):
    def __init__(self, *, tty: bool = False):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


class CliTests(unittest.TestCase):
    def setUp(self):
        workspace = tempfile.TemporaryDirectory(prefix="ytmp3-cli-tests-")
        self.addCleanup(workspace.cleanup)
        self.root = Path(workspace.name).resolve()
        self.store = SettingsStore(self.root / "config" / "settings.json")
        self.result = DownloadResult(
            self.root / "Example [jNQXAC9IVRw].mp3", "Example", "jNQXAC9IVRw"
        )

    def invoke(self, arguments, *, tty=False, answer=URL):
        stdout, stderr = TerminalStream(tty=tty), TerminalStream(tty=tty)
        with (
            patch.object(cli.sys, "stdin", TerminalStream(tty=tty)),
            patch.object(cli.sys, "stdout", stdout),
            patch.object(cli.sys, "stderr", stderr),
            patch(
                "builtins.input",
                **(
                    {"side_effect": answer}
                    if isinstance(answer, BaseException)
                    else {"return_value": answer}
                ),
            ) as prompt,
            patch.object(cli, "SettingsStore", return_value=self.store),
        ):
            try:
                code = cli.main(arguments)
            except SystemExit as error:
                code = error.code
        return code, stdout.getvalue(), stderr.getvalue(), prompt

    def test_url_shortcut_and_explicit_download_both_report_saved_path(self):
        for arguments in ([URL], ["download", URL]):
            with self.subTest(arguments=arguments), patch.object(cli, "DownloadEngine") as factory:
                factory.return_value.download.return_value = self.result
                code, stdout, stderr, prompt = self.invoke(arguments)
                self.assertEqual(code, 0, stderr)
                self.assertIn(str(self.result.path), stdout)
                self.assertIn("saved", stdout.lower())
                self.assertEqual(factory.return_value.download.call_count, 1)
                prompt.assert_not_called()
                self.assertNotIn("Traceback", stderr)

    def test_directory_override_is_per_job_and_does_not_save_settings(self):
        destination = self.root / "one job 音楽"
        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.return_value = self.result
            code, _, stderr, _ = self.invoke(["download", URL, "--directory", str(destination)])
            self.assertEqual(code, 0, stderr)
            call = factory.return_value.download.call_args
            override = call.args[1] if len(call.args) > 1 else call.kwargs.get("directory")
            self.assertEqual(Path(override), destination)
            self.assertFalse(self.store.path.exists())

    def test_no_arguments_in_a_terminal_prompts_for_one_url(self):
        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.return_value = self.result
            code, stdout, stderr, prompt = self.invoke([], tty=True)
            self.assertEqual(code, 0, stderr)
            prompt.assert_called_once()
            factory.return_value.download.assert_called_once()
            self.assertIn(str(self.result.path), stdout)

    def test_missing_url_without_terminal_returns_usage_error_without_prompting(self):
        for arguments in ([], ["download"]):
            with self.subTest(arguments=arguments), patch.object(cli, "DownloadEngine") as factory:
                code, stdout, stderr, prompt = self.invoke(arguments)
                self.assertEqual(code, 2)
                self.assertTrue(stdout or stderr)
                prompt.assert_not_called()
                factory.assert_not_called()

    def test_invalid_url_is_rejected_before_starting_an_engine(self):
        with patch.object(cli, "DownloadEngine") as factory:
            code, stdout, stderr, _ = self.invoke(["download", "https://example.com/video"])
            self.assertEqual(code, 2)
            self.assertTrue(stderr.strip())
            self.assertNotIn("Traceback", stderr)
            self.assertNotIn("saved", stdout.lower())
            factory.assert_not_called()

    def test_configured_folder_persists_and_show_displays_it(self):
        destination = self.root / "Saved 音楽 folder"
        code, _, stderr, _ = self.invoke(["config", "set", "download-dir", str(destination)])
        self.assertEqual(code, 0, stderr)
        self.assertEqual(SettingsStore(self.store.path).get_download_directory(), destination)
        code, stdout, stderr, _ = self.invoke(["config", "show"])
        self.assertEqual(code, 0, stderr)
        self.assertIn(str(destination), stdout)
        self.assertIn(str(self.store.path), stdout)

    def test_bad_settings_print_an_actionable_error_without_overwriting_them(self):
        self.store.path.parent.mkdir(parents=True)
        self.store.path.write_text("broken settings", encoding="utf-8")
        code, _, stderr, _ = self.invoke(["config", "show"])
        self.assertEqual(code, 1)
        self.assertIn("settings", stderr.lower())
        self.assertNotIn("Traceback", stderr)
        self.assertEqual(self.store.path.read_text(), "broken settings")

    def test_runtime_failures_are_readable_and_do_not_report_success(self):
        for failure in (
            DownloadError("Video unavailable"),
            SettingsError("Folder is not writable"),
            OSError("Disk full"),
        ):
            with (
                self.subTest(failure=type(failure).__name__),
                patch.object(cli, "DownloadEngine") as factory,
            ):
                factory.return_value.download.side_effect = failure
                code, stdout, stderr, _ = self.invoke([URL])
                self.assertEqual(code, 1)
                self.assertIn(str(failure), stderr)
                self.assertNotIn("Traceback", stderr)
                self.assertNotIn("saved", stdout.lower())

    def test_cancellation_returns_130_and_restores_the_original_signal_handler(self):
        original = signal.getsignal(signal.SIGINT)

        def interrupted_download(*args, **kwargs):
            handler = signal.getsignal(signal.SIGINT)
            self.assertTrue(callable(handler))
            self.assertIsNot(handler, original, "Download did not install a cancellation handler")
            handler(signal.SIGINT, None)
            self.assertTrue(kwargs["cancel"].is_set())
            raise DownloadCancelled("Download cancelled.")

        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = interrupted_download
            code, stdout, stderr, _ = self.invoke([URL])
        self.assertEqual(code, 130)
        self.assertIn("cancel", stderr.lower())
        self.assertNotIn("saved", stdout.lower())
        self.assertIs(signal.getsignal(signal.SIGINT), original)

    def test_keyboard_interrupt_has_no_traceback_and_restores_signal_handler(self):
        original = signal.getsignal(signal.SIGINT)
        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = KeyboardInterrupt
            code, stdout, stderr, _ = self.invoke([URL])
        self.assertEqual(code, 130)
        self.assertNotIn("Traceback", stderr)
        self.assertNotIn("saved", stdout.lower())
        self.assertIs(signal.getsignal(signal.SIGINT), original)

    def test_eof_at_interactive_prompt_exits_without_starting_a_download(self):
        with patch.object(cli, "DownloadEngine") as factory:
            code, stdout, stderr, prompt = self.invoke([], tty=True, answer=EOFError())
        self.assertEqual(code, 0, stderr)
        prompt.assert_called_once()
        factory.assert_not_called()
        self.assertNotIn("saved", stdout.lower())
        self.assertNotIn("Traceback", stderr)

    def test_download_failure_after_cancellation_is_reported_as_cancelled(self):
        original = signal.getsignal(signal.SIGINT)

        def racing_download(*args, **kwargs):
            kwargs["cancel"].set()
            raise DownloadError("The worker stopped while cancellation was requested")

        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = racing_download
            code, stdout, stderr, _ = self.invoke([URL])
        self.assertEqual(code, 130)
        self.assertIn("cancel", stderr.lower())
        self.assertNotIn("saved", stdout.lower())
        self.assertNotIn("Error:", stderr)
        self.assertIs(signal.getsignal(signal.SIGINT), original)

    def test_remote_errors_and_saved_paths_cannot_inject_terminal_controls(self):
        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = DownloadError(
                "\x1b[31mUnavailable\x1b[0m\nforged line\rreplacement\x07"
            )
            code, _, stderr, _ = self.invoke([URL])
        self.assertEqual(code, 1)
        self.assertIn("Unavailable", stderr)
        self.assertEqual(len(stderr.splitlines()), 1)
        self.assertNotIn("\x1b", stderr)
        self.assertNotIn("\x07", stderr)
        self.assertNotIn("\r", stderr)

        result = DownloadResult(Path("music\x1b[2J\nforged.mp3"), "Example", "jNQXAC9IVRw")
        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.return_value = result
            code, stdout, _, _ = self.invoke([URL])
        self.assertEqual(code, 0)
        self.assertIn("music", stdout)
        self.assertEqual(len(stdout.splitlines()), 1)
        self.assertNotIn("\x1b", stdout)

    def test_terminal_progress_shows_download_percentage_and_indeterminate_conversion(self):
        def download(*args, **kwargs):
            kwargs["on_progress"](DownloadProgress("downloading", 25, 100))
            kwargs["on_progress"](DownloadProgress("converting"))
            kwargs["on_progress"](DownloadProgress("complete"))
            return self.result

        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = download
            code, _, stderr, _ = self.invoke([URL], tty=True)
        self.assertEqual(code, 0, stderr)
        self.assertIn("25%", stderr)
        conversion_lines = [line for line in stderr.splitlines() if "converting" in line.lower()]
        self.assertTrue(conversion_lines)
        self.assertTrue(all("%" not in line for line in conversion_lines))

    def test_redirected_progress_uses_stages_without_carriage_returns_or_fake_conversion_percent(
        self,
    ):
        def download(*args, **kwargs):
            for event in (
                DownloadProgress("resolving"),
                DownloadProgress("downloading", 10, 100),
                DownloadProgress("downloading", 50, 100),
                DownloadProgress("downloading", 100, 100),
                DownloadProgress("converting"),
                DownloadProgress("complete"),
            ):
                kwargs["on_progress"](event)
            return self.result

        with patch.object(cli, "DownloadEngine") as factory:
            factory.return_value.download.side_effect = download
            code, stdout, stderr, _ = self.invoke([URL])
        self.assertEqual(code, 0, stderr)
        self.assertNotIn("\r", stdout + stderr)
        self.assertIn("resolving", stderr.lower())
        self.assertIn("downloading", stderr.lower())
        conversion_lines = [line for line in stderr.splitlines() if "converting" in line.lower()]
        self.assertTrue(conversion_lines)
        self.assertTrue(all("%" not in line for line in conversion_lines))
        self.assertLessEqual(stderr.lower().count("downloading"), 2)


if __name__ == "__main__":
    unittest.main()
