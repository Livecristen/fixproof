> **INTERNAL – not part of the release.** See references/README.md.

# FixProof – Architecture Plan (Phase 1, needs Director OK)

## Scope (MVP, v1)
`SKILL.md` · `scripts/verify.py` (Python 3.9+, **stdlib only**) · JSON report + terminal output · exit codes · `examples/python`, `examples/js-ts` · `tests/` (9 scenarios) · `.github/workflows/ci.yml` · README, LICENSE (MIT), CONTRIBUTING, SECURITY. English, no fake stats.
Install: one folder (`SKILL.md` + `scripts/verify.py`), with one `git clone` command per agent (Claude Code, Codex, Cursor) in the README.

## Workflow, as enforced by the CLI
```
verify.py init     --repro "<cmd>" [--suite "<cmd>"]   # records baseline on the unfixed tree (git HEAD/diff hash)
verify.py check    # after the fix: runs repro (must now pass), suite (regressions), revert test, flaky reruns
verify.py validate report.json                         # re-checks a report's integrity/consistency
```
(There is no `report` subcommand: `init` and `check` write the report to `.fixproof/report.json`, or to `--json .fixproof/<name>.json`; `validate` re-checks it. Subcommands are `init`, `check`, `restore`, `validate`.)

The CLI runs every command itself, using subprocess with a timeout. Agents never supply results. It stores evidence in `.fixproof/` as `runs.jsonl`: per run the cmd, cwd, start/end time, exit code, duration, sha256 of stdout/stderr, a redacted tail, the git tree state, and a hash chain (each record holds the hash of the previous one).

## Revert test (required)
1. Compute the fix diff: `git diff <baseline-commit>` excluding test files (default test-path globs, configurable). Untracked fix files are included via `git add -N` handling.
2. Save a snapshot: the full diff, the list of untracked files, and the tree hash (`git stash create`, then `git write-tree` on a temp index).
3. Reverse-apply the fix part only (`git apply -R` of the non-test diff). Tests stay in place.
4. Run the repro command. Expected: **fails**.
5. Restore (`git apply` of the saved diff). Run it inside `try/finally`, plus a stored recovery patch at `.fixproof/recovery.patch` in case of a crash.
6. Check that the tree hash after restore equals the snapshot. If not, the result is BLOCKED, the report contains the recovery instructions, and exit code 5.
7. If the repro **passes without the fix**, the result is **at most UNVERIFIED** (the test does not depend on the fix).

## Dirty-tree safety (added on Director request)
- The revert test runs only when the working tree is clean **or fully backed up**. It must never lose uncommitted user changes.
- Implemented: before any modification the CLI copies every file it will touch to `.fixproof/backup/` (hash-verified) and records a
  sha256 fingerprint of ALL tracked + untracked (non-ignored) files. After the revert run it restores raw bytes and compares
  the full fingerprint. Mismatch → exit 5, backup kept.
- If a safe backup is impossible (unmerged paths / merge or rebase in progress, snapshot or backup write fails) → **BLOCKED**, nothing modified.
- As implemented, the revert writes baseline file contents directly (`git cat-file --filters`) instead of `git apply -R`, so CRLF/autocrlf setups restore byte-exactly.

## Status rules (documented in SKILL.md and enforced in code)
| Status | Rule |
|---|---|
| VERIFIED | baseline repro failed (exit≠0, and not from a timeout or a missing tool) AND after the fix repro passes N/N reruns AND the revert test fails AND the tree is restored AND the suite has no new failures (P2P) AND the relevant test was actually executed |
| PARTIALLY VERIFIED | repro verified, but the suite was not given or could not run fully. Or the revert test could not be applied cleanly and the reason is named |
| FAILED | repro still fails after the fix, OR new suite failures (a regression) |
| UNVERIFIED | baseline did not fail (not reproduced), OR the revert test passed without the fix, OR "0 tests ran", OR results are flaky (mixed pass/fail across reruns) |
| BLOCKED | missing dependency or command, timeout, missing environment, a dirty or non-git tree where required, or a restore mismatch |
Exit 0 of a command alone never yields VERIFIED.

## CLI exit codes
0 VERIFIED · 1 FAILED · 2 PARTIALLY VERIFIED · 3 UNVERIFIED · 4 BLOCKED · 5 tree restore error · 64 usage error.

## Making made-up results hard and visible
- Results come only from runs the CLI executed itself. `validate` recomputes the hash chain and the status from the raw records. A hand-edited report fails with exit 3 (UNVERIFIED) and a note "integrity mismatch".
- The report records the git HEAD and a diff hash at each run. A report that does not match the current tree is flagged.
- Limitation (stated in SECURITY.md): this is not tamper-proof against an agent that rewrites `.fixproof/`. It makes tampering detectable.

## Secret redaction
Before writing anything, redact patterns (AWS keys, GitHub/Slack tokens, `Bearer …`, PEM blocks, `password=`/`token=`/`secret=` pairs, and values of environment variables whose names contain KEY/TOKEN/SECRET/PASSWORD). Hashes are computed on the raw output, but only redacted text is stored.

## Test scenarios (tests/, stdlib `unittest`, each builds a temp git repo)
| # | Scenario | Expected status / exit |
|---|---|---|
| 1 | real fix | VERIFIED / 0 |
| 2 | fix does not solve the bug | FAILED / 1 |
| 3 | test green without relevant behavior (passes on baseline, or passes in the revert test) | UNVERIFIED / 3 |
| 4 | missing dependency (command not found / ImportError) | BLOCKED / 4 |
| 5 | timeout | BLOCKED / 4 |
| 6 | regression in the suite | FAILED / 1 |
| 7 | flaky test (random pass/fail, seeded) | UNVERIFIED / 3, with "flaky" noted |
| 8 | missing environment (required env var/tool absent) | BLOCKED / 4 |
| 10 | dirty tree that cannot be safely backed up (unmerged paths) | BLOCKED / 4, all files byte-identical afterwards |
| 11 | dirty tree with uncommitted + untracked user changes (backup possible) | VERIFIED / 0, all files byte-identical afterwards |
| 9 | output contains secrets | report contains no secret string (asserted by grep), and `[REDACTED]` is present |
Also: a tampered report fails `validate`, and after every revert test the tree is byte-identical (`git status --porcelain` + tree hash).

## Measurable acceptance criteria
- AC1: `verify.py` imports only the stdlib (checked by a test that scans imports). It runs on Python 3.9–3.13, on Linux and Windows.
- AC2: All 9 scenarios plus the tamper and restore tests pass in CI (GitHub Actions matrix: ubuntu + windows, Python 3.9 & 3.13).
- AC3: Each scenario produces the exact status and exit code in the table above, 10 out of 10 consecutive CI-equivalent runs (seeded flaky).
- AC4: Revert test: the tree hash before equals the tree hash after in 100% of tests, including when the repro command crashes or times out.
- AC5: The JSON report validates against `references/report.schema.json` (planned; not shipped, `validate` performs the structural and chain checks). `validate` detects any edit to a run record (100% of the mutation cases in the tests).
- AC6: Scenario 9 finds 0 occurrences of the seeded secrets in `.fixproof/` and in the report.
- AC7: The examples in `examples/python` (pytest or unittest) and `examples/js-ts` (`node --test`, no npm install needed) reach VERIFIED end-to-end in CI.
- AC8: Install = `git clone` + copy one folder. The README has one command per agent. A fresh clone runs `python scripts/verify.py --help` with no install step.
- AC10: Dirty tree: unsafe → BLOCKED with zero bytes changed; safe → revert runs and all user files are byte-identical afterwards (tests 10, 11; CRLF content included).
- AC9: The docs contain none of the words "first", "only" or "unforgeable" (a CI grep check).

## Risks / open points
- Splitting test files from fix files by globs is heuristic. Use an override flag (`--test-paths`).
- Fixes that touch the test file and the code in one hunk: refuse, and report PARTIALLY VERIFIED with a reason.
- Non-git projects: BLOCKED for the revert test (v1).
