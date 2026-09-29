# Build on Windows x64: python packaging/build_windows.py
from importlib.metadata import distribution
from pathlib import Path
import os
import runpy
import sys

from PySide6.QtCore import qVersion

root = Path(SPECPATH).parent
if sys.platform != "win32" or sys.maxsize <= 2 ** 32:
    raise RuntimeError("The launcher package requires 64-bit Windows Python")
if qVersion() != "6.11.2":
    raise RuntimeError("Packaged launcher notices target Qt 6.11.2; install PySide6==6.11.2 to build")
# Prefer Windows' own DLLs to unrelated tools on PATH (for example, Poppler's
# incompatible icuuc.dll). PyInstaller excludes system DLLs from the bundle.
system_directory = Path(os.environ["SystemRoot"]) / "System32"
os.environ["PATH"] = str(system_directory) + os.pathsep + os.environ.get("PATH", "")
data = [
    (str(root / "colibri_launcher/probe.py"), "colibri_launcher"),
    (str(root / "colibri_launcher/icons/*.svg"), "colibri_launcher/icons"),
    (str(root / "LICENSE"), "licenses/colibri-launcher"),
    (str(root / "NOTICE"), "licenses/colibri-launcher"),
    (str(root / "THIRD_PARTY_NOTICES.md"), "licenses/colibri-launcher"),
]
for name in ("GPL-3.0-only.txt", "LGPL-3.0-only.txt", "THIRD_PARTY_NOTICES.txt", "SOURCES.json", "README.md"):
    data.append((str(root / "packaging/licenses" / name), "licenses/qt"))
for name in ("PySide6", "PySide6_Essentials", "shiboken6"):
    package = distribution(name)
    for item in package.files or ():
        if "/licenses/" in str(item).replace("\\", "/"):
            data.append((str(package.locate_file(item)), f"licenses/{name}/{Path(item).parent.name}"))
        elif str(item).endswith(".dist-info/METADATA"):
            data.append((str(package.locate_file(item)), f"licenses/{name}"))

analysis = Analysis(
    [str(root / "packaging/entry.py")],
    pathex=[str(root)],
    binaries=[],
    datas=data,
    hiddenimports=[],
    hookspath=[str(root / "packaging/hooks")],
    runtime_hooks=[],
    excludes=["tkinter", "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets"],
    noarchive=False,
)
# Qt's generic hook also collects Mesa's optional software OpenGL renderer.
# This QWidget application has no OpenGL surfaces and does not use that DLL.
analysis.binaries = [item for item in analysis.binaries if Path(item[0]).name.lower() != "opengl32sw.dll"]
for name, _, _ in analysis.binaries:
    if "virtualkeyboard" in name.lower():
        raise RuntimeError(f"Unexpected GPL-only Virtual Keyboard runtime: {name}")
for name, _, _ in analysis.pure:
    if name == "colibri" or name.startswith("colibri."):
        raise RuntimeError(f"An upstream engine module was unexpectedly bundled: {name}")
collect_notices = runpy.run_path(str(root / "packaging/licenses/collect.py"))["collect_notices"]
for source, destination in collect_notices(analysis.binaries, workpath):
    analysis.datas.append((f"{destination}/{Path(source).name}", source, "DATA"))
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="ColibriLauncher",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(root / "assets/colibri.ico"),
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="ColibriLauncher",
)
