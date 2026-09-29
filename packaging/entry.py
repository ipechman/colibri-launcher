"""PyInstaller entry point for the standalone Windows launcher."""

from colibri_launcher.app import main

if __name__ == "__main__":
    raise SystemExit(main())
