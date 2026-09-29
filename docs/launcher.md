# Using Colibri Launcher on Windows

Install Colibri, Python 3.10+, and your model files first. NVIDIA CUDA also needs
a compatible driver and the matching CUDA runtime for the selected Colibri engine.

## Where to put it

Extract the complete Windows ZIP inside your Colibri folder:

```text
Colibri/
  coli
  family_registry.py
  ...your Colibri engine and support files...
  ColibriLauncher/
    ColibriLauncher.exe
    _internal/
```

The executable and `_internal` can also sit directly beside `coli`. Source
checkouts with `c/coli` are supported. The app uses its own folder or immediate
Colibri parent, even when a shortcut has a different working directory. It does
not use an old saved installation path or an unrelated Colibri copy on PATH.

The package includes Python and Qt for the interface. Colibri runs with a separate
external Python, discovered automatically. Use **Python interpreter** to select
another interpreter if needed. Engines, GPU libraries, and model weights are not bundled.

When updating, close the old launcher and replace the whole launcher folder.
Keep `_internal` with its executable. Saved settings are stored separately.

## Start a model

1. Choose **Add model folder** and select a folder with its configuration,
   tokenizer, and weights. Colibri identifies its model family and engine.
2. Choose **Web Chat** or **API Server**.
3. Choose **Automatic**, **CPU only**, or **NVIDIA CUDA**. For CUDA, choose a GPU
   under **GPU devices** when the engine requires a single card.
4. Review the readiness message. Missing engines, runtime libraries, incompatible
   devices, and invalid limits block Start until corrected.
5. Press **Start**. The window stays responsive during loading. Web Chat opens
   in the browser when ready; API Server shows a local address and model identifier.
6. Press **Stop** to close the model process tree launched by this application.

Closing the window while a model is active offers to stop it and quit, or cancel
closing. An unrelated process on the chosen port is never stopped by the launcher.

**Advanced settings** provides RAM/VRAM budgets, context, output length, and port.
Automatic values use Colibri's defaults. Options are saved per model. Renaming or
removing a model entry changes the library shortcut, not its files.

**Details and logs** shows runtime messages and a redacted, copyable PowerShell
command. Use Start to apply the full environment and resource settings; the command
preview omits environment values.

## GPU readiness

An NVIDIA card alone does not mean every engine can use it. The launcher checks
the model family, engine, runtime, selected devices, and Colibri diagnostics.
Automatic may fall back to CPU with an explanation. Explicit CUDA choices must
pass checks and do not silently become CPU launches.

Some engines, including the tested DeepSeek V4 engine, support only one GPU.
Select NVIDIA CUDA first, then an individual card. Selecting all cards for a
single-GPU engine blocks Start.

A missing CUDA DLL must be supplied as part of the corresponding Colibri setup.
The launcher names missing runtime files when it can determine them. It does
not build/download a CUDA library or substitute one from another Colibri version.

Readiness is a preflight result, not a measurement of GPU utilization. Runtime
messages reporting a CPU fallback are surfaced in the status and log. AMD HIP,
Vulkan, Metal, and non-Windows launchers are outside this project's supported scope.

## Preferences and compatibility

Choose Light or Dark at the bottom of the sidebar. The preference is saved and
changing it does not interrupt a running model.

Settings remain in `%LOCALAPPDATA%\Colibri\launcher.json`, schema version 1.
Existing users keep saved models, options, their Python choice, and theme.
Invalid settings are preserved with a `.corrupt-...` suffix before defaults are
restored. The app never resumes inference automatically at startup.

Colibri v1.11.0 and v1.12.1 are tested compatibility targets. Model support comes
from the installed Colibri registry, with compatible JSON diagnostics. Ordinary
Colibri diagnostics may update `.coli_analysis.json` in a model folder; they do
not load its tensor payloads or start inference.

The launcher discovers commands, flags, argument counts, required arguments, and
choices from the installed CLI's argument parser during each readiness check.
The isolated metadata probe stops parser inspection before a command is dispatched.
The version number is informational, not a list of permitted releases.

Web Chat or API Server is disabled when the installed CLI does not provide it.
Optional settings that are unsupported stay at Automatic. An existing explicit
value is preserved and remains editable so you can reset it to Automatic;
incompatible values block Start instead of being silently ignored. Flags required
for model selection, compute control, local binding, and diagnostics must exist.
Automatic resource placement is requested only when that command supports it.

New commands and flags do not automatically become additional GUI controls. The
interface keeps its focused launch workflow. A future CLI that replaces its parser,
registry, diagnostic schema, or GPU behavior may still need a launcher update;
capability discovery does not establish compatibility with unknown semantics.

## Troubleshooting

- **Colibri not found:** put the complete launcher folder directly inside Colibri.
  A source launch must use Colibri's folder as the working directory.
- **Python not found:** choose a working Python 3.10+ interpreter under Python interpreter.
- **CUDA unavailable:** inspect the reported missing engine, DLL, or device. Use
  an individual GPU if the engine does not support multiple cards.
- **Web Chat assets missing:** choose API Server or follow Colibri's instructions
  to supply its `web/dist/index.html` assets.
- **Port in use:** select a free port under Advanced settings.
- **Loading takes time:** inspect the logs. A listening socket alone does not
  count as a ready model, and Stop remains available during loading.
- **Other failure:** correct the configuration and use Retry check.
  Include the redacted error in an issue; remove private paths and credentials.

Servers bind to `127.0.0.1`. Remote hosting, automatic installation, model downloads,
and multiple simultaneous model servers are not part of this launcher.
