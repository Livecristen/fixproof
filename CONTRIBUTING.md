# Contributing

- Keep `scripts/verify.py` on the Python standard library and compatible with Python 3.9.
- Every behavior change needs an executed scenario test in `tests/` (`python -m unittest discover -s tests -v`).
- Do not add claims to the docs that the tests do not back. CI rejects the words listed in `tests/test_meta.py`.
- Never commit real secrets, even in tests; build fake tokens at runtime.
