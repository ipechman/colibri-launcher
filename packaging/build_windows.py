"""Build the Windows x64 folder package, portable ZIP, and SHA-256 sidecar.

Run with 64-bit Python 3.12 after installing this checkout with .[build].
Outputs are written to dist/; PyInstaller's temporary files go under build/.
"""

import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tomllib
import zipfile


ROOT = Path(__file__).resolve().parent.parent


def source_info():
    """Record provenance without copying Git's local paths into the package."""
    def git(*arguments):
        return subprocess.check_output(
            ["git", "-C", str(ROOT), *arguments], text=True,
        ).strip()

    if Path(git("rev-parse", "--show-toplevel")).resolve() != ROOT:
        raise RuntimeError("Build from the standalone colibri-launcher Git checkout")
    return {
        "repository": "https://github.com/ipechman/colibri-launcher",
        "commit": git("rev-parse", "HEAD"),
        "dirty": bool(git("status", "--porcelain")),
    }


def archive_package(package, release_version):
    archive = package.parent / f"ColibriLauncher-{release_version}-Windows-x64.zip"
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as bundle:
        for path in sorted(package.rglob("*")):
            if path.is_file():
                bundle.write(path, path.relative_to(package.parent))
    with zipfile.ZipFile(archive) as bundle:
        damaged = bundle.testzip()
        if damaged is not None:
            raise RuntimeError(f"ZIP integrity check failed: {damaged}")
    with archive.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    checksum = archive.with_suffix(archive.suffix + ".sha256")
    checksum.write_text(f"{digest}  {archive.name}\n", encoding="ascii")
    return archive, checksum


def main():
    if sys.platform != "win32" or sys.maxsize <= 2 ** 32 or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise RuntimeError("Build the launcher with 64-bit Windows x64 Python")
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("The supported release build uses Python 3.12")
    with (ROOT / "pyproject.toml").open("rb") as stream:
        release_version = tomllib.load(stream)["project"]["version"]
    provenance = source_info()
    subprocess.run([
        sys.executable, "-m", "PyInstaller", "--clean", "--noconfirm",
        "--distpath", str(ROOT / "dist"), "--workpath", str(ROOT / "build" / "pyinstaller"),
        str(ROOT / "packaging" / "launcher.spec"),
    ], cwd=ROOT, check=True)
    package = ROOT / "dist" / "ColibriLauncher"
    for name in ("README.md", "LICENSE", "NOTICE", "THIRD_PARTY_NOTICES.md", "CONTRIBUTING.md"):
        shutil.copy2(ROOT / name, package / name)
    shutil.copytree(ROOT / "docs", package / "docs", dirs_exist_ok=True)
    build_info = {
        "application": "Colibri Launcher",
        "version": release_version,
        "platform": "Windows-x64",
        "source": provenance,
        "runtime": {
            "python": platform.python_version(),
            "pyside6": version("PySide6"),
            "pyinstaller": version("PyInstaller"),
        },
        "requirements": "Separate Colibri installation, external Python, and local models.",
    }
    (package / "BUILD-INFO.json").write_text(json.dumps(build_info, indent=2) + "\n", encoding="utf-8")
    archive, checksum = archive_package(package, release_version)
    print(f"Created {archive.name} ({archive.stat().st_size:,} bytes)")
    print(checksum.read_text(encoding="ascii").strip())
    print("Run tests/launcher/packaged_smoke.py against an extracted copy before publishing.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
