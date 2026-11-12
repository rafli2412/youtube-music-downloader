"""PyInstaller entry point, kept outside the importable application package."""

from ytmp3.desktop import main

if __name__ == "__main__":
    raise SystemExit(main())
