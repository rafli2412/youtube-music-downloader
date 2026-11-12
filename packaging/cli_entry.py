"""Console entry point sharing the desktop distribution's bundled resources."""

from multiprocessing import freeze_support

if __name__ == "__main__":
    freeze_support()
    from ytmp3.cli import main

    raise SystemExit(main())
