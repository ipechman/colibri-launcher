"""Contracts with a separate, real Colibri checkout; never start an engine."""

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.launcher.test_adapter import upstream_support


class UpstreamCompatibilityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.support = upstream_support()

    def capture_cli(self):
        # A child keeps the installed registry and argparse modules separate
        # from fixture modules used by the other launcher tests.
        code = """import json, runpy, sys
from pathlib import Path
from unittest.mock import patch
from colibri_launcher.probe import _capture_cli
support = Path(sys.argv[1])
sys.path.insert(0, str(support))
with patch('subprocess.Popen', side_effect=AssertionError('CLI discovery started a process')):
    namespace = runpy.run_path(str(support / 'coli'), run_name='_test_installed_cli')
    capabilities = _capture_cli(namespace, support / 'coli')
print(json.dumps(capabilities))
"""
        result = subprocess.run(
            [sys.executable, "-B", "-c", code, str(self.support)],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        capabilities = json.loads(result.stdout)
        self.assertNotIn("error", capabilities)
        self.assertEqual(capabilities["schema_version"], 1)
        return capabilities

    def test_installed_parser_exposes_launch_and_diagnostic_options(self):
        commands = self.capture_cli()["commands"]
        for name in ("web", "serve", "doctor"):
            with self.subTest(command=name):
                options = commands[name]["options"]
                for flag in ("--model", "--gpu", "--ram", "--ctx", "--vram"):
                    self.assertIsNone(options[flag]["nargs"])
                self.assertEqual(options["--auto-tier"]["nargs"], 0)
                self.assertEqual(options["--policy"]["choices"],
                                 ["quality", "balanced", "experimental-fast"])
        for name in ("web", "serve"):
            self.assertIsNone(commands[name]["options"]["--port"]["nargs"])
        self.assertEqual(commands["web"]["options"]["--no-browser"]["nargs"], 0)
        self.assertNotIn("--no-browser", commands["serve"]["options"])
        self.assertEqual(commands["doctor"]["options"]["--json"]["nargs"], 0)
        self.assertEqual(commands["doctor"]["options"]["--deep"]["nargs"], 0)

    def test_discovery_tracks_the_installed_chat_options(self):
        # --stats was added after 1.11.0. Compare with the actual installation's
        # public help instead of branching on a hardcoded version string.
        options = self.capture_cli()["commands"]["chat"]["options"]
        result = subprocess.run(
            [sys.executable, "-B", str(self.support / "coli"), "chat", "--help"],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual("--stats" in options, "--stats" in result.stdout)
        if "--stats" in options:
            self.assertEqual(options["--stats"]["choices"], ["full", "compact", "off"])
        self.assertEqual(options["--attach"]["nargs"], "?")

    def test_doctor_json_is_accepted_without_loading_model_weights(self):
        from colibri_launcher.backend import _run_doctor
        from colibri_launcher.domain import Installation, LaunchOptions

        installation = Installation(
            self.support.parent, self.support / "coli", Path(sys.executable), self.support,
        )
        with tempfile.TemporaryDirectory() as temporary:
            model = Path(temporary) / "minimal model 鸟"
            model.mkdir()
            (model / "config.json").write_text('{"model_type":"glm"}', encoding="utf-8")
            (model / "tokenizer.json").write_text("{}", encoding="utf-8")
            report = _run_doctor(
                installation, model, LaunchOptions(compute="cpu"), "none",
                {"family": "glm", "resource_env": [], "cli": self.capture_cli()},
            )

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["status"], "error")
        checks = {check["id"]: check for check in report["checks"]}
        for name in ("model.path", "model.config", "model.family", "model.tokenizer"):
            self.assertEqual(checks[name]["status"], "pass", checks[name])
        self.assertEqual(checks["accelerator.gpu"]["status"], "skip")
        self.assertEqual(checks["model.shards"]["status"], "fail")
        self.assertIsNone(report["plan"])

    def test_installed_kimi_cuda_probe_accepts_its_own_backend_marker(self):
        # Current Colibri recognizes Kimi's backend basename without the GLM
        # banner. Feed the real upstream predicate inert bytes, never an engine.
        code = """import json, runpy, sys
from pathlib import Path
from unittest.mock import patch
from colibri_launcher.probe import _cuda_support
support, engine = Path(sys.argv[1]), Path(sys.argv[2])
sys.path.insert(0, str(support))
namespace = runpy.run_path(str(support / 'coli'), run_name='_test_installed_cli')
import doctor
if not callable(getattr(doctor, 'windows_backend_dll', None)):
    print(json.dumps({'available': False}))
else:
    with patch('subprocess.Popen', side_effect=AssertionError('CUDA inspection started a process')):
        upstream = namespace['cuda_binary'](str(engine))
        supported, reason = _cuda_support(namespace, engine, 'kimi')
    print(json.dumps({'available': True, 'upstream': upstream,
                      'supported': supported, 'reason': reason}))
"""
        with tempfile.TemporaryDirectory() as temporary:
            engine = Path(temporary) / "kimi_k3.exe"
            engine.write_bytes(b"[K3-CUDA]\0coli_cuda.dll")
            (engine.parent / "coli_cuda.dll").write_bytes(b"inert test backend")
            result = subprocess.run(
                [sys.executable, "-B", "-c", code, str(self.support), str(engine)],
                capture_output=True, text=True, encoding="utf-8", timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        if not payload["available"]:
            self.skipTest("This Colibri predates the Kimi backend marker helper")
        self.assertTrue(payload["upstream"])
        self.assertTrue(payload["supported"], payload["reason"])


if __name__ == "__main__":
    unittest.main()
