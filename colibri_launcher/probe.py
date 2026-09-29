#!/usr/bin/env python3
"""Isolated, standard-library metadata bridge for an installed Colibri.

This file is executed by the user's external Python. It must remain free of
imports from the launcher package and print exactly one bounded JSON object.
"""

import argparse
import contextlib
import io
import inspect
import json
import runpy
import sys
from pathlib import Path


class _ParserCaptured(BaseException):
    """Abort before the installed CLI can dispatch a command handler."""


def _capture_cli(namespace, launcher):
    result = {"schema_version": 1, "commands": {}}
    original_parse = argparse.ArgumentParser.parse_args
    original_known = argparse.ArgumentParser.parse_known_args
    original_argv = sys.argv
    captured = []

    def capture(parser, *_args, **_kwargs):
        captured.append(parser)
        raise _ParserCaptured()

    try:
        main = namespace.get("main")
        if not callable(main):
            raise ValueError("this Colibri CLI does not expose its command parser")
        argparse.ArgumentParser.parse_args = capture
        argparse.ArgumentParser.parse_known_args = capture
        # --help also prevents dispatch if a future main handles it without argparse.
        sys.argv = [str(launcher), "--help"]
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            try:
                main()
            except _ParserCaptured:
                pass
        if len(captured) != 1:
            raise ValueError("this Colibri CLI did not expose an argparse command parser")
        root = captured[0]
        if root._mutually_exclusive_groups or any(
                action.required and not isinstance(action, argparse._SubParsersAction)
                for action in root._actions):
            raise ValueError("the installed CLI requires unsupported global argument constraints")
        commands = {}
        for action in root._actions:
            if isinstance(action, argparse._SubParsersAction):
                commands.update(action.choices)
        if not commands or len(commands) > 128:
            raise ValueError("the installed command parser has an unsupported command list")
        for name, parser in commands.items():
            if name in {"doctor", "web", "serve"} and parser._mutually_exclusive_groups:
                raise ValueError(f"Colibri {name} has unsupported mutually exclusive argument groups")
            if len(parser._actions) > 256:
                raise ValueError("the installed command parser has too many arguments")
            options, positionals = {}, []
            for action in parser._actions:
                if isinstance(action, argparse._SubParsersAction):
                    positionals.append({"name": action.dest, "nargs": action.nargs,
                                        "required": action.required})
                    continue
                if not action.option_strings:
                    positionals.append({"name": action.dest, "nargs": action.nargs,
                                        "required": action.nargs not in ("?", "*")})
                    continue
                choices = None
                if action.choices is not None:
                    if not hasattr(action.choices, "__len__") or len(action.choices) > 256:
                        raise ValueError("the installed command parser has unsupported choices")
                    choices = list(action.choices)
                    if any(not isinstance(item, (str, int, float, bool, type(None))) for item in choices):
                        raise ValueError("the installed command parser has non-scalar choices")
                for option in action.option_strings:
                    options[option] = {"nargs": action.nargs, "required": action.required,
                                       "choices": choices, "aliases": list(action.option_strings),
                                       "type": "int" if action.type is int else
                                               "float" if action.type is float else "str"}
            result["commands"][name] = {"options": options, "positionals": positionals}
        if len(json.dumps(result, allow_nan=False).encode("utf-8")) > 196_608:
            raise ValueError("the installed command parser is too large")
    except (Exception, SystemExit) as error:
        # This bridge is a process boundary: expose failures, never guess support.
        result = {"schema_version": 1, "commands": {},
                  "error": (str(error) or type(error).__name__)[:2000]}
    finally:
        argparse.ArgumentParser.parse_args = original_parse
        argparse.ArgumentParser.parse_known_args = original_known
        sys.argv = original_argv
    return result


def _nvidia_devices():
    try:
        from resource_plan import discover_gpus
        found = discover_gpus()
    except (ImportError, OSError, ValueError, TypeError):
        return []
    devices = []
    for value in found if isinstance(found, list) else []:
        if not isinstance(value, dict):
            continue
        name = value.get("name")
        index = value.get("index")
        if not isinstance(name, str) or isinstance(index, bool) or not isinstance(index, int):
            continue
        lowered = name.lower()
        markers = ("nvidia", "geforce", "quadro", "tesla", " rtx", "a100", "h100", "h200")
        if not any(marker in lowered for marker in markers):
            continue
        total = value.get("total_bytes", 0)
        if isinstance(total, bool) or not isinstance(total, (int, float)) or total < 0:
            total = 0
        devices.append({"index": index, "name": name, "memory_gb": round(total / (1024 ** 3), 2)})
    return devices


def _nvidia_runtime(engine, family_id):
    """Disambiguate the installed CLI's CUDA-or-HIP capability predicate."""
    try:
        image = engine.read_bytes()
    except OSError:
        return False, "The selected engine could not be inspected for NVIDIA CUDA support."
    if b"coli_hip.dll" in image:
        return False, "The selected engine uses AMD HIP, which this launcher does not support."
    if family_id == "deepseek_v4":
        built = b"[DSV4 CUDA]" in image
        runtime_names = ("coli_cuda_dsv4_dg.dll", "coli_cuda_dsv4.dll")
    else:
        try:
            import doctor
        except ModuleNotFoundError as error:
            if error.name != "doctor":
                return False, f"The installed CUDA classifier could not be loaded: {error}."
            classifier = None
        else:
            classifier = getattr(doctor, "windows_backend_dll", None)
        if classifier is not None:
            if not callable(classifier):
                return False, "The installed CUDA classifier is unsupported."
            try:
                expected = classifier(image)
            except Exception as error:
                return False, f"The installed CUDA classifier failed: {error}."
            if expected == "coli_hip.dll":
                return False, "The selected engine uses AMD HIP, which this launcher does not support."
            if expected not in (None, "coli_cuda.dll"):
                return False, "The installed CUDA classifier returned an unsupported backend."
            built = expected == "coli_cuda.dll"
        else:
            built = b"[CUDA] mode: routed experts" in image and b"coli_cuda.dll" in image
        runtime_names = ("coli_cuda.dll",)
    if not built:
        return False, "The selected engine has no verified NVIDIA CUDA support."
    if not any((engine.parent / name).is_file() for name in runtime_names):
        names = " or ".join(runtime_names)
        return False, f"A required CUDA DLL is missing beside the selected engine: {names}."
    return True, "The selected engine has verified NVIDIA CUDA runtime evidence."


def _cuda_support(namespace, engine, family_id, model=None):
    dedicated = family_id == "deepseek_v4"
    function = namespace.get("dsv4_cuda_available" if dedicated else "cuda_binary")
    if not callable(function):
        return False, "This Colibri version cannot verify CUDA for the selected engine."
    try:
        signature = inspect.signature(function)
    except (TypeError, ValueError):
        return False, "This Colibri version exposes an unsupported CUDA probe."
    try:
        argument = str(model) if dedicated else str(engine)
        signature.bind(argument)
    except TypeError:
        if dedicated:
            return False, "This Colibri version can only verify CUDA for its default engine."
        try:
            signature.bind()
        except TypeError:
            return False, "This Colibri version exposes an unsupported CUDA probe."
        if family_id != "glm":
            # Older CLIs inspect their default GLM binary even when launching
            # another family. Both the selected engine and that CLI gate must
            # pass; a GPU diagnostic alone cannot prove the CLI will launch.
            runtime_supported, runtime_reason = _nvidia_runtime(engine, family_id)
            if not runtime_supported:
                return False, runtime_reason
            try:
                legacy_supported = bool(function())
            except (OSError, ValueError, TypeError):
                legacy_supported = False
            if not legacy_supported:
                return False, ("This older Colibri CLI cannot launch CUDA for the selected engine. "
                               "Update Colibri to a version with model-specific CUDA checks.")
            return True, runtime_reason
        try:
            supported = bool(function())
        except (OSError, ValueError, TypeError):
            supported = False
    else:
        try:
            supported = bool(function(argument))
        except (OSError, ValueError, TypeError):
            supported = False
    if not supported:
        runtime_supported, runtime_reason = _nvidia_runtime(engine, family_id)
        if not runtime_supported:
            return False, runtime_reason
        return False, "The selected engine is CPU-only or its CUDA runtime is unavailable."
    return _nvidia_runtime(engine, family_id)


def _resource_environment(descriptor):
    """Inputs consumed by resource_request and the selected family's launcher."""
    names = [getattr(descriptor.limits, "context_env", "")]
    names.extend({"glm53": ("GLM53_EXPERT_GB",),
                  "kimi": ("K3_EXPERT_GB", "K3_MMAP"),
                  "deepseek_v4": ("V4_MTP_GB",)}.get(descriptor.id, ()))
    return [name for name in names if name]


def collect(support_dir, launcher, model):
    support = Path(support_dir).resolve()
    launcher_path = Path(launcher).resolve()
    model_path = Path(model).resolve()
    sys.path.insert(0, str(support))
    namespace = runpy.run_path(str(launcher_path), run_name="_colibri_desktop_probe")
    cli = _capture_cli(namespace, launcher_path)
    try:
        import family_registry
        resolve_model = family_registry.resolve_model
    except (ImportError, AttributeError) as error:
        raise ValueError("the installed Colibri family registry could not be loaded") from error

    resolved = resolve_model(model_path)
    descriptor = resolved.descriptor
    engine_for = namespace.get("engine_for")
    if not callable(engine_for):
        raise ValueError("this Colibri version cannot resolve a model-specific engine")
    engine = Path(engine_for(str(model_path))).resolve()
    limits = descriptor.limits
    name = descriptor.display_name
    display_for = getattr(family_registry, "display_for", None)
    try:
        displayed = display_for(resolved) if callable(display_for) else None
        if isinstance(displayed, tuple) and displayed and isinstance(displayed[0], str):
            name = displayed[0]
    except (AttributeError, KeyError, TypeError, ValueError):
        pass

    cuda_binary, cuda_reason = _cuda_support(namespace, engine, descriptor.id, model_path)
    family_accelerator = getattr(descriptor, "supports_accelerator", False)
    if family_accelerator is not True:
        cuda_binary = False
        cuda_reason = f"{name} does not support an accelerator in this Colibri installation."
    gateway = getattr(descriptor, "has_gateway_adapter", False) is True
    return {
        "schema_version": 1,
        "family": descriptor.id,
        "name": name,
        "model_id": descriptor.default_model_id,
        "engine": str(engine),
        "limits": {
            "default_context": limits.default_context,
            "max_context": limits.max_context,
            "default_output": getattr(limits, "interactive_max_output", limits.default_max_output),
            "max_output": getattr(limits, "interactive_max_output", limits.default_max_output),
        },
        "gateway": gateway,
        "family_accelerator": family_accelerator,
        "cuda_binary": cuda_binary,
        "cuda_reason": cuda_reason,
        "gpus": _nvidia_devices(),
        "resource_env": _resource_environment(descriptor),
        "cli": cli,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--support-dir", required=True)
    parser.add_argument("--launcher", required=True)
    parser.add_argument("--model", required=True)
    args = parser.parse_args()
    try:
        payload = collect(args.support_dir, args.launcher, args.model)
    except (OSError, ValueError, TypeError, KeyError, AttributeError) as error:
        payload = {"schema_version": 1, "error": str(error)}
    encoded = json.dumps(payload, ensure_ascii=False)
    if len(encoded.encode("utf-8")) > 262_144:
        encoded = json.dumps({"schema_version": 1, "error": "metadata response was too large"})
    print(encoded)


if __name__ == "__main__":
    main()
