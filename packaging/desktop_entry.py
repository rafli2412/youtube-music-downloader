"""PyInstaller entry point, kept outside the importable application package."""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from ytmp3.desktop import main

    raise SystemExit(main())
