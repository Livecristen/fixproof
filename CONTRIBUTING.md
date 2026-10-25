# Contributing

FixProof is an agent skill (`SKILL.md`) plus `scripts/verify.py`. Changes should keep the CLI's reported status equal to what the code computes, and keep the docs equal to what the CLI prints.

## Setup

- Python 3.9 or newer, and git.
- Node if you run `examples/js-ts` or `examples/ts`. For `examples/ts`: Tested with Node 22.18.0+ / 23.6.0+ / 24.x (unflagged type stripping); CI uses 24.22.1. The CLI does not need Node.
- In GitHub Actions the interpreter is `python`. Some Linux machines, including the one used to check the docs, have `python3` and do not have `python`.

From a checkout:

```bash
python3 -m unittest discover -s tests -v
python3 examples/run_example.py python
python3 examples/run_example.py js-ts
python3 examples/run_example.py ts
python3 scripts/verify.py --help
python3 scripts/verify.py --version
```

## Behavior changes

- Keep `scripts/verify.py` on the Python standard library, and compatible with Python 3.9. `tests/test_meta.py` parses its imports.
- A behavior change needs an executed scenario in `tests/`. Those tests build a temporary git repository and assert the status and the exit code.
- Do not document a result the tests do not support. If a command appears in the docs, run it, and keep the quoted output in step with the CLI.
- Root markdown is checked by `test_no_banned_claims` in `tests/test_meta.py` and by the `banned-claims grep` step in `.github/workflows/ci.yml`. The rejected pattern lives in that test. Do not add it to markdown at the repository root. The same test walks `examples/**/*.md`.
- Never commit a real secret. Tests build fake tokens at runtime.
- Leave the copyright notice in `LICENSE` unchanged.
- `references/` is internal planning material. `.gitattributes` marks it `export-ignore`. It is not the product spec. User-facing behavior is `scripts/verify.py`, `SKILL.md`, and the README.

## Security and issues

Report vulnerabilities through a private GitHub security advisory, as [SECURITY.md](SECURITY.md) describes. Do not file them as issues.

Use the templates for a bug, a feature request, or a configuration problem (install path, flags, environment, git setup).

## Pull requests

Say what changed, which tests you ran, and which documented commands you re-ran if the docs quote them. CI runs the unit tests, the three examples, the wording checks, and gitleaks, on Ubuntu and Windows, for Python 3.9 and 3.13.
