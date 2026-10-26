# Changelog

## Unreleased

- SKILL.md: report the exit code of `verify.py` itself, not a wrapping shell, and report BLOCKED for a `.git` without write access instead of proving the fix in a copy. The snapshot hint now also matches git's "insufficient permission" message. Both come from a real Codex CLI run.
- Fix: `init` no longer crashes with a traceback when `.git/info/exclude` is not writable (for example in an agent sandbox that mounts `.git` without write access). It warns instead, and skips the write when `.fixproof/` is already ignored, for example via `.gitignore`. If git cannot write objects at all, the BLOCKED message now says that `.git` must be writable. Found in a real Codex CLI run on Windows.
- Docs: Windows PowerShell 5.1 install. `~` is not expanded for `git clone`, so the README now shows a `$HOME` variant.
- Docs: one Node statement for the TypeScript example everywhere: Tested with Node 22.18.0+ / 23.6.0+ / 24.x (unflagged type stripping); CI uses 24.22.1. Matrix: 22.17.1 FAILED, 22.18.0 VERIFIED, 23.5.0 FAILED, 23.6.0 VERIFIED, 24.22.1 VERIFIED.

## 0.3.0 (2026-10-25)

Final release of the 0.3.0-rc1 candidate, with no CLI behavior change against rc1.

- Version is 0.3.0 in `scripts/verify.py` and in the new `VERSION` file. `tests/test_meta.py` checks that the two match.
- README: the example transcript and the sample report were regenerated from a real 0.3.0 run.
- Release draft (#5) is retitled to v0.3.0. Its Node requirement for the TypeScript example now matches what was tested: unflagged type stripping, Node 22.18+ or 23.6+.

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
