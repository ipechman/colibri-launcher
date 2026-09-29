"""Entry-point behavior without a GUI or an installed Colibri engine."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def run_without_dependencies(platform):
    # A clean child makes missing optional dependencies real import failures,
    # while an unrelated cwd prevents accidental imports from a Colibri tree.
    code = '''import importlib.abc, runpy, sys
sys.path.insert(0, sys.argv[1])
sys.platform = sys.argv[2]
class AbsentDependencies(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname.split('.')[0] in {'PySide6', 'colibri'}:
            raise ModuleNotFoundError('Unavailable dependency: ' + fullname, name=fullname)
sys.meta_path.insert(0, AbsentDependencies())
runpy.run_module('colibri_launcher', run_name='__main__')
'''
    with tempfile.TemporaryDirectory() as unrelated:
        return subprocess.run(
            [sys.executable, "-I", "-c", code, str(PROJECT_ROOT), platform],
            cwd=unrelated, capture_output=True, text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )


class ApplicationEntryTests(unittest.TestCase):
    def test_non_windows_entrypoint_explains_platform_before_loading_qt(self):
        for platform in ("linux", "darwin"):
            with self.subTest(platform=platform):
                result = run_without_dependencies(platform)
                self.assertEqual(result.returncode, 1, result.stderr)
                self.assertIn("Windows", result.stderr)
                self.assertNotIn("PySide6", result.stderr)
                self.assertNotIn("Traceback", result.stderr)

    def test_missing_qt_points_to_standalone_project_installation(self):
        result = run_without_dependencies("win32")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("PySide6", result.stderr)
        self.assertIn("Colibri Launcher checkout", result.stderr)
        self.assertIn('python -m pip install -e "."', result.stderr)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
