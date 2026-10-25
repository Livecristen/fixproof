# Changelog

## 0.3.0-rc1 (2026-10-25), release candidate

One CLI fix against 0.2.0. Everything else is docs, CI and dependency work.

- Fix: `check --revert-mode worktree` returned BLOCKED (`git commit-tree ... Author identity unknown`) on machines without a git user. The temporary commit now uses a fixed identity. Regression test: `test_p3_11_worktree_mode_without_git_identity`.
- Docs: the README now says what happens with the `ts` example on Node without type stripping (Node 20 gives FAILED).
- Docs: README, CONTRIBUTING and SKILL.md rewritten from real CLI runs (#4). Issue templates added. Install, options, status rules, exit codes and examples are documented. The README sample report is checked by `tests/test_meta.py` with `validate`.
- Docs: `--version` and the version text now read 0.3.0-rc1. The README sample report stays as recorded with 0.2.0.
- Internal plan: removed the nonexistent `verify.py report` subcommand from `references/PLAN.md`.
- CI: `actions/setup-node` 4.4.0 → 7.1.0 (#1), `actions/setup-python` 5.6.0 → 7.1.0 (#2), `actions/checkout` 4.4.0 → 7.0.1 (#3). All still pinned to commit SHAs.
- Tests: the fake PEM fixture is built at runtime. `.gitleaksignore` covers the one historical finding.

## 0.2.0 (2026-10-25)

Security fix round (FIXLIST P1–P3):

- Timestamped backups, never deleted silently. `restore` command and `--discard-backup`.
- Child environment allowlist plus `--pass-env`. `--no-shell` and `--allow-exe`.
- `state.json` hash checked by `check`. Atomic writes, path and symlink guards.
- Wider secret redaction. Output marked as untrusted.
- Warnings for root, protected branches and remotes. `--dry-run`, `--revert-mode worktree`, `--include-ignored`.
- `--json` limited to `.fixproof/`. CI actions pinned to SHAs, gitleaks job, Dependabot.

## 0.1.0 (2026-10-25), MVP

- `SKILL.md`, stdlib CLI `init` / `check` / `validate`, hash-chained evidence log, and a revert test with dirty-tree safety.
- Examples for Python, JS and TS, and 9 scenario tests. CI on Ubuntu and Windows.
