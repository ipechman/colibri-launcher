# Contributing

Keep changes focused on launching an existing local Colibri installation on
Windows. Preserve settings compatibility, responsiveness, readable themes,
explicit CPU/CUDA behavior, and ownership of the launched process tree.

Follow [the build guide](docs/building.md). Run the complete suite with the pinned
upstream checkout configured. For packaging changes, build and smoke-test the
extracted ZIP. Add a regression test for a behavior change or bug fix.

Do not commit models, engines, a Colibri checkout, build outputs, user settings,
or credentials. Avoid removing useful tests or required notices to reduce the
line count. Compatibility changes should identify the Colibri version and
reproduce its CLI behavior using fixtures or contract tests.

For UI changes, check both themes, disabled controls, and Windows display scaling.
Do not claim inference or GPU performance validation from simulated tests.

Open pull requests against `main`. Include the problem, resulting behavior, and
validation performed. This project is independent of upstream Colibri.
