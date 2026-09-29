"""Installed CLI grammar must gate commands without changing user intent."""

import argparse
import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from colibri_launcher import probe
from colibri_launcher.backend import build_launch, inspect_model
from colibri_launcher.domain import LaunchOptions, LauncherError
from colibri_launcher.installation import find_installation
from tests.launcher.test_adapter import make_model, make_release, PYTHON


class ParserDiscoveryTests(unittest.TestCase):
    def test_unmodeled_root_requirements_and_command_groups_fail_closed(self):
        for constraint in ("root", "group"):
            def main():
                parser = argparse.ArgumentParser()
                if constraint == "root":
                    parser.add_argument("--new-global-setting", required=True)
                command = parser.add_subparsers().add_parser("serve")
                if constraint == "group":
                    group = command.add_mutually_exclusive_group(required=True)
                    group.add_argument("--first")
                    group.add_argument("--second")
                parser.parse_args()
            with self.subTest(constraint=constraint):
                result = probe._capture_cli({"main": main}, Path("coli"))
                self.assertIn("error", result)

    def test_discovery_captures_actual_options_without_dispatching_handlers(self):
        self.assertTrue(callable(getattr(probe, "_capture_cli", None)), "CLI discovery is missing")
        dispatched = []

        def main():
            parser = argparse.ArgumentParser(description="--pretend is only prose")
            command = parser.add_subparsers(dest="command").add_parser("web")
            command.add_argument("--host")
            command.add_argument("--switch", action="store_true")
            command.add_argument("--choice", choices=("first", "second"))
            command.add_argument("--needed", required=True)
            command.add_argument("model")
            parser.parse_args()
            dispatched.append(True)

        old_parse = argparse.ArgumentParser.parse_args
        old_known = argparse.ArgumentParser.parse_known_args
        old_argv = sys.argv
        cli = probe._capture_cli({"main": main}, Path("coli"))
        self.assertEqual(dispatched, [])
        self.assertIs(argparse.ArgumentParser.parse_args, old_parse)
        self.assertIs(argparse.ArgumentParser.parse_known_args, old_known)
        self.assertIs(sys.argv, old_argv)
        options = cli["commands"]["web"]["options"]
        self.assertNotIn("--pretend", options)
        self.assertIsNone(options["--host"]["nargs"])
        self.assertEqual(options["--switch"]["nargs"], 0)
        self.assertEqual(options["--choice"]["choices"], ["first", "second"])
        self.assertTrue(options["--needed"]["required"])
        self.assertEqual(cli["commands"]["web"]["positionals"][0]["name"], "model")

    def test_discovery_failure_restores_process_state_and_reports_error(self):
        self.assertTrue(callable(getattr(probe, "_capture_cli", None)), "CLI discovery is missing")
        old_parse, old_argv = argparse.ArgumentParser.parse_args, sys.argv

        def main():
            raise ValueError("fixture parser failure")

        result = probe._capture_cli({"main": main}, Path("coli"))
        self.assertIn("fixture parser failure", result["error"])
        self.assertIs(argparse.ArgumentParser.parse_args, old_parse)
        self.assertIs(sys.argv, old_argv)


class DynamicCliTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = make_release(Path(temporary.name) / "install")
        self.model = make_model(temporary.name)
        self.installation = find_installation(self.root, PYTHON)

    def configure(self, **values):
        (self.root / "fixture_cli.json").write_text(json.dumps(values), encoding="utf-8")
        (self.root / "doctor-called").unlink(missing_ok=True)

    def inspect(self, **values):
        options = LaunchOptions(mode="serve", compute="cpu", **values)
        return options, inspect_model(self.installation, self.model, options)

    def assert_cli_blocked(self, result, fragment):
        self.assertFalse(result.can_start)
        self.assertIn("cli", result.plan)
        messages = " ".join(check.message for check in result.checks if check.level == "fail")
        self.assertIn(fragment, messages)
        self.assertFalse((self.root / "doctor-called").exists(), "unsupported diagnostic was executed")

    def test_absent_optional_flag_allows_automatic_but_blocks_explicit_value(self):
        for command in ("doctor", "serve"):
            with self.subTest(command=command):
                self.configure(omit={command: ["--vram"]})
                options, automatic = self.inspect()
                self.assertTrue(automatic.can_start)
                self.assertNotIn("--vram", build_launch(self.installation, automatic, options).argv)
                (self.root / "doctor-called").unlink()
                _, explicit = self.inspect(vram_gb=4.0)
                self.assert_cli_blocked(explicit, "--vram")

    def test_missing_required_command_and_local_binding_are_blocking(self):
        for config, fragment in (({"commands": ["doctor", "web"]}, "serve"),
                                 ({"omit": {"serve": ["--host"]}}, "--host"),
                                 ({"omit": {"doctor": ["--json"]}}, "--json")):
            with self.subTest(config=config):
                self.configure(**config)
                _, result = self.inspect()
                self.assert_cli_blocked(result, fragment)

    def test_incompatible_arity_choices_and_new_required_arguments_are_blocking(self):
        cases = (({"alter": {"serve": {"--host": {"nargs": 2}}}}, "--host"),
                 ({"alter": {"doctor": {"--gpu": {"choices": ["auto", "0"]}}}}, "none"),
                 ({"required": {"serve": ["--new-setting"]}}, "--new-setting"),
                 ({"positionals": {"serve": ["new_input"]}}, "new_input"))
        for config, fragment in cases:
            with self.subTest(config=config):
                self.configure(**config)
                _, result = self.inspect()
                self.assert_cli_blocked(result, fragment)

    def test_auto_tier_support_is_specific_to_selected_command(self):
        self.configure(omit={"serve": ["--auto-tier"]})
        options, result = self.inspect()
        self.assertTrue(result.can_start)
        self.assertNotIn("--auto-tier", build_launch(self.installation, result, options).argv)
        web_options = LaunchOptions(mode="web", compute="cpu")
        web = inspect_model(self.installation, self.model, web_options)
        self.assertIn("--auto-tier", build_launch(self.installation, web, web_options).argv)

    def test_each_preflight_rediscovers_parser_and_build_rechecks_current_request(self):
        options, before = self.inspect()
        self.assertTrue(before.can_start)
        self.configure(omit={"serve": ["--ngen"]})
        _, after = self.inspect()
        self.assertTrue(after.can_start)
        with self.assertRaisesRegex(LauncherError, "--ngen"):
            build_launch(self.installation, after, LaunchOptions(mode="serve", compute="cpu", max_tokens=50))

    def test_automatic_cpu_fallback_keeps_capabilities_when_cpu_choice_is_unsupported(self):
        gpu = [{"index": 0, "name": "NVIDIA Fixture", "total_bytes": 8 << 30}]
        config_path = self.model / "config.json"
        config = json.loads(config_path.read_text())
        config["gpu_runtime_missing"] = True
        config_path.write_text(json.dumps(config))
        for command in ("doctor", "serve"):
            with self.subTest(command=command), patch.dict(os.environ, {"FAKE_GPU_DATA": json.dumps(gpu)}):
                self.configure(alter={command: {"--gpu": {"choices": ["auto", "0"]}}})
                result = inspect_model(self.installation, self.model, LaunchOptions(mode="serve"))
                self.assertFalse(result.can_start)
                self.assertIn("cli", result.plan)
                self.assertIn("none", " ".join(check.message for check in result.checks if check.level == "fail"))
