"""Per-user settings shared by the terminal and desktop interfaces."""

from __future__ import annotations

import json
import os
import platform
import tempfile
from pathlib import Path

from ytmp3 import APP_NAME


class SettingsError(RuntimeError):
    """Settings or the chosen destination could not be read or written."""


def default_settings_path() -> Path:
    home = Path.home()
    if platform.system() == "Darwin":
        directory = home / "Library" / "Application Support"
    elif platform.system() == "Windows":
        directory = Path(os.environ.get("APPDATA") or home / "AppData" / "Roaming")
    else:
        directory = Path(os.environ.get("XDG_CONFIG_HOME") or home / ".config")
    return directory / APP_NAME / "settings.json"


def prepare_download_directory(path: str | Path) -> Path:
    """Create and test a destination using a real write, including missing drives."""
    try:
        if not str(path).strip():
            raise ValueError("Choose a download folder.")
        directory = Path(path).expanduser().resolve()
        directory.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryFile(prefix=".ytmp3-write-check-", dir=directory) as probe:
            probe.write(b"writable")
            probe.flush()
        return directory
    except (OSError, ValueError, RuntimeError) as error:
        raise SettingsError(f"Cannot use download folder {path!s}: {error}") from error


class SettingsStore:
    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else default_settings_path()

    def get_download_directory(self) -> Path:
        try:
            with self.path.open(encoding="utf-8") as source:
                settings = json.load(source)
        except FileNotFoundError:
            return Path.home() / "Downloads"
        except (OSError, ValueError) as error:
            raise SettingsError(f"Cannot read settings at {self.path}: {error}") from error
        if (
            not isinstance(settings, dict)
            or type(settings.get("version")) is not int
            or settings["version"] != 1
            or not isinstance(settings.get("download_directory"), str)
            or not settings["download_directory"].strip()
        ):
            raise SettingsError(
                f"Invalid settings at {self.path}; expected version 1 and a folder."
            )
        try:
            folder = Path(settings["download_directory"])
            if not folder.is_absolute() or "\x00" in str(folder):
                raise ValueError("The saved download folder must be an absolute path.")
        except (TypeError, ValueError) as error:
            raise SettingsError(f"Invalid download folder in {self.path}: {error}") from error
        # A disconnected drive is handled when the engine prepares the destination.
        return folder

    def set_download_directory(self, path: str | Path) -> Path:
        # Do not silently replace an existing corrupt or future-version configuration.
        self.get_download_directory()
        directory = prepare_download_directory(path)
        temporary: Path | None = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", dir=self.path.parent, prefix="settings-", delete=False
            ) as output:
                temporary = Path(output.name)
                json.dump({"version": 1, "download_directory": str(directory)}, output, indent=2)
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary, self.path)
        except (OSError, ValueError) as error:
            raise SettingsError(f"Cannot save settings at {self.path}: {error}") from error
        finally:
            if temporary is not None:
                try:
                    temporary.unlink(missing_ok=True)
                except OSError:
                    # A permission change can also prevent cleanup. Preserve the
                    # original save error rather than replacing it with raw OSError.
                    pass
        return directory
