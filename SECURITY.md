# Security

## Threat model
FixProof makes fabricated verification results hard and visible. It does not make them impossible.
- Results are produced by commands the CLI runs; records in `.fixproof/runs.jsonl` are hash-chained.
- `verify.py validate` recomputes the chain and the status. Hand-edited statuses, outcomes or outputs are detected.
- `state.json` (commands, globs, baseline) is hashed into the chained baseline record; `check` refuses to run modified commands.
- An agent with write access can delete `.fixproof/` and recompute a consistent chain. Re-run `check` yourself (or in CI) for an independent result.

## Working tree safety
The revert test backs up every file it will touch, checks the backup's hash, and verifies a fingerprint of all
tracked and untracked files after restoring. On mismatch it exits 5 and keeps the backup in `.fixproof/backup/`.
With unmerged paths, symlinked or out-of-repo paths, or an existing backup from an interrupted run it refuses (BLOCKED)
without modifying or deleting anything; `verify.py restore` replays the backup manifest. Files are written atomically
(temp file + rename), restore continues past per-file errors, and SIGINT/SIGTERM trigger the restore. A hard kill
(SIGKILL) cannot be intercepted: run `verify.py restore` afterwards. A WARNING is printed before the working tree is
touched; `--dry-run` previews and `--revert-mode worktree` avoids touching the working tree.

## Secrets
Command output is redacted before it is stored (common token formats, PEM keys, `password=`-style pairs, and values of
env vars whose names contain KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL). Redaction is pattern-based: review reports before sharing.
Child processes get a sanitized environment: a small allowlist (PATH, HOME, LANG, SYSTEMROOT, TEMP and similar)
plus names passed with `--pass-env`; variables that look like secrets are not passed unless named explicitly.
Repro commands run with your privileges; do not run FixProof on untrusted repositories. FixProof warns when run as root.

## Reporting
Please report vulnerabilities privately to the maintainers via a GitHub security advisory on this repository.
