# Colibri Launcher for Windows

An unofficial Windows desktop launcher for an existing [Colibri](https://github.com/JustVugg/colibri)
installation. This project is maintained independently of Colibri.

**Windows x64 only.** Choose a model and how to run it, check readiness, and start
or stop it from one window.

## Download and run

1. Download the Windows ZIP from [Releases](https://github.com/ipechman/colibri-launcher/releases).
2. Extract the complete `ColibriLauncher` folder **inside your Colibri folder**.
3. Open `ColibriLauncher.exe`, add your model folder, and choose Web Chat or API Server.

Keep the accompanying `_internal` folder. The launcher finds Colibri beside it
automatically. You need an existing Colibri installation, a working external
Python 3.10 or newer, and local model files. The launcher does not install engines,
download models, or change GPU drivers.

## Features

- Saved model library with names and per-model settings.
- Web Chat and API Server; the browser opens when Web Chat is ready.
- Automatic, CPU-only, and NVIDIA CUDA modes, with named GPU selection.
- Optional RAM, VRAM, context, output-length, and port settings.
- Start/Stop, readiness checks, loading status, logs, and a copyable command.
- Light and dark themes, including readable controls and dialogs.
- Automatic local Colibri/Python discovery and an optional Python picker.
- Commands and argument support discovered from your installed Colibri.

Models stay on disk when removed from the library. Closing a running launcher
offers to stop its model process tree. The app always opens with inference stopped.
Existing users retain their library, theme, and options in
`%LOCALAPPDATA%\Colibri\launcher.json`.

See the [user guide](docs/launcher.md) for setup, CUDA limitations, and troubleshooting.

## Development

Use 64-bit Windows and Python 3.12 to build a distributable package:

```powershell
git clone https://github.com/ipechman/colibri-launcher.git
Set-Location colibri-launcher
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m unittest discover -s tests/launcher -v
.\.venv\Scripts\python.exe packaging/build_windows.py
```

The [build guide](docs/building.md) covers the separate upstream checkout used by
integration checks, the extracted-package smoke test, and running from source.
Tests use simulated servers and models; they do not start real inference.

## Scope and maintenance

This repository contains the launcher, its tests, and Windows packaging. It does
not contain Colibri's engine, model weights, Tauri application, or repository history.
Compatibility is tested against Colibri **v1.11.0 and v1.12.1**. The launcher reads
the installed CLI's argument definitions and model registry instead of selecting
flags by version number. Unsupported settings are explained before launch.
Future changes to diagnostic schemas, engine behavior, or registry interfaces
can still require a launcher update; discovery cannot guarantee all future releases.

The original upstream proposal included roughly 3,000 lines of launcher Python,
3,000 lines of tests and fixtures, and 13,500 lines of third-party notices. Required
notices remain readable under `packaging/licenses`; they are not application code.
Windows-only support removes the separate Linux build and process-management paths.

Bug reports and focused contributions are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md).
The launcher source is Apache-2.0; bundled dependencies retain their own licenses.
See [NOTICE](NOTICE) and [third-party notices](THIRD_PARTY_NOTICES.md).
