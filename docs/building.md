# Build and verify on Windows

Builds require 64-bit Windows, Python 3.12, and the dependencies declared in
`pyproject.toml`. PySide6 is pinned to 6.11.2 to match the runtime notices.
No compiler or model weights are needed for launcher development.

```powershell
git clone https://github.com/ipechman/colibri-launcher.git
Set-Location colibri-launcher
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[build]"
.\.venv\Scripts\python.exe -m unittest discover -s tests/launcher -v
```

Most tests are self-contained. CLI contract tests use a separate upstream
checkout and report a skip when it is not configured. CI runs them against
Colibri v1.11.0 at the immutable revision below:

```powershell
git clone https://github.com/JustVugg/colibri.git .upstream
git -C .upstream checkout 3a70acbf6e7054f6edcf4b7d3b1e679793eb8e48
$env:COLIBRI_TEST_ROOT = (Resolve-Path .upstream).Path
.\.venv\Scripts\python.exe -m unittest discover -s tests/launcher -v
```

The upstream checkout is ignored by Git and never enters the launcher wheel or
ZIP. Tests read CLI functions without executing an inference engine. Process
tests use a small local fixture server.

## Run from source

Install as above, then start with your actual Colibri folder as the working
directory. Adapt these example paths:

```powershell
Set-Location C:\path\to\Colibri
& C:\path\to\colibri-launcher\.venv\Scripts\pythonw.exe -m colibri_launcher
```

Source launches use the current Colibri folder. Packaged launches instead use
the executable folder or immediate parent.

## Build a portable package

```powershell
.\.venv\Scripts\python.exe packaging/build_windows.py
```

`dist` contains `ColibriLauncher/`, a versioned Windows x64 ZIP, and a SHA-256
checksum. Build metadata records the source revision, dirty state, and dependency
versions without local user paths. Build release archives from a clean commit.
The portable build helper requires a Git checkout with a commit so that it can
record the source revision.

Extract into a fresh directory and check that exact extracted application:

```powershell
Expand-Archive dist\ColibriLauncher-0.1.0-Windows-x64.zip build\archive-check
.\.venv\Scripts\python.exe tests/launcher/packaged_smoke.py build/archive-check/ColibriLauncher/ColibriLauncher.exe .upstream
```

This verifies notices, arrows, both folder layouts, external Python discovery,
the bundled model probe, and saved settings. It uses temporary settings and never
starts inference. The GitHub workflow runs the same checks.

To build the installable source package separately:

```powershell
.\.venv\Scripts\python.exe -m build
```

The portable package keeps shared libraries and notices under `_internal`.
See [runtime notices](https://github.com/ipechman/colibri-launcher/blob/main/packaging/licenses/README.md) before changing dependency
versions or using another Python distribution. Packages are unsigned.
