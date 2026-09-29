"""Validate the installed CLI's grammar before sending launcher arguments."""

import math
import re

from .domain import LauncherError


def validate_cli(value):
    """Accept only a bounded, JSON-safe parser snapshot from the bridge."""
    invalid = "Colibri returned invalid command capabilities."
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise LauncherError(invalid)
    if "error" in value and (not isinstance(value["error"], str) or not value["error"]):
        raise LauncherError(invalid)
    commands = value.get("commands")
    if not isinstance(commands, dict) or len(commands) > 128:
        raise LauncherError(invalid)
    for name, command in commands.items():
        if not isinstance(name, str) or not re.fullmatch(r"[\w-]{1,64}", name):
            raise LauncherError(invalid)
        if not isinstance(command, dict):
            raise LauncherError(invalid)
        options, positionals = command.get("options"), command.get("positionals")
        if not isinstance(options, dict) or len(options) > 256:
            raise LauncherError(invalid)
        if not isinstance(positionals, list) or len(positionals) > 64:
            raise LauncherError(invalid)
        for flag, option in options.items():
            if not isinstance(flag, str) or not re.fullmatch(r"--?[\w-]{1,128}", flag):
                raise LauncherError(invalid)
            if not isinstance(option, dict) or not isinstance(option.get("required"), bool):
                raise LauncherError(invalid)
            nargs = option.get("nargs")
            if (isinstance(nargs, bool) or
                    not (nargs is None or isinstance(nargs, int) and 0 <= nargs <= 128 or
                         isinstance(nargs, str) and nargs in {"?", "*", "+", "...", "A..."})):
                raise LauncherError(invalid)
            choices = option.get("choices")
            if choices is not None and (not isinstance(choices, list) or len(choices) > 256 or
                    any(not isinstance(item, (str, int, float, bool, type(None))) or
                        isinstance(item, str) and len(item) > 1024 or
                        isinstance(item, float) and not math.isfinite(item) for item in choices)):
                raise LauncherError(invalid)
            aliases = option.get("aliases", [flag])
            if (not isinstance(aliases, list) or not aliases or len(aliases) > 16 or
                    any(not isinstance(alias, str) or alias not in options for alias in aliases)):
                raise LauncherError(invalid)
        for positional in positionals:
            if (not isinstance(positional, dict) or not isinstance(positional.get("name"), str) or
                    not 1 <= len(positional["name"]) <= 128 or
                    not isinstance(positional.get("required"), bool)):
                raise LauncherError(invalid)
    return value


def supports_option(cli, command, flag, takes_value=True):
    """Whether this command accepts the option in the shape the UI emits."""
    if not isinstance(cli, dict) or cli.get("error"):
        return False
    definition = cli.get("commands", {}).get(command, {}).get("options", {}).get(flag)
    if not isinstance(definition, dict):
        return False
    nargs = definition.get("nargs")
    return nargs in (None, 1, "?") if takes_value else nargs == 0


def command_errors(cli, command, arguments):
    """Check explicit ``(flag, value-or-None)`` pairs against one command."""
    try:
        validate_cli(cli)
    except LauncherError as error:
        return [str(error)]
    if cli.get("error"):
        return [f"Colibri command capabilities could not be inspected: {cli['error']}"]
    definition = cli["commands"].get(command)
    if definition is None:
        return [f"This Colibri installation does not support the {command} command."]
    errors = []
    present = {flag for flag, _value in arguments}
    options = definition["options"]
    for flag, value in arguments:
        if flag not in options:
            remedy = ("choose Automatic for this setting or use a compatible Colibri installation"
                      if flag in {"--ram", "--vram", "--ctx", "--ngen"}
                      else "use a compatible Colibri installation")
            errors.append(f"Colibri {command} does not support {flag}; {remedy}.")
            continue
        if not supports_option(cli, command, flag, takes_value=value is not None):
            errors.append(f"Colibri {command} {flag} accepts an incompatible number of arguments.")
            continue
        choices = options[flag].get("choices")
        if value is not None and choices is not None:
            kind = options[flag].get("type", "str")
            try:
                parsed = {"int": int, "float": float, "str": str}.get(kind, str)(value)
            except (TypeError, ValueError):
                parsed = object()
            if parsed not in choices:
                errors.append(f"Colibri {command} {flag} does not accept {value!r}.")
    required = set()
    for flag, option in options.items():
        aliases = option.get("aliases", [flag])
        if option["required"] and not present.intersection(aliases):
            required.add(aliases[0])
    for flag in sorted(required):
        errors.append(f"Colibri {command} requires {flag}, which this launcher cannot supply.")
    for positional in definition["positionals"]:
        if positional["required"]:
            errors.append(f"Colibri {command} requires the positional argument {positional['name']}, which this launcher cannot supply.")
    return errors
