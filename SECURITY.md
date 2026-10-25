# Security

## Threat model
FixProof makes fabricated verification results hard and visible. It does not make them impossible.
- Results are produced by commands the CLI runs; records in `.fixproof/runs.jsonl` are hash-chained.
- `verify.py validate` recomputes the chain and the status. Hand-edited statuses, outcomes or outputs are detected.
- An agent with write access can delete `.fixproof/` and recompute a consistent chain. Re-run `check` yourself (or in CI) for an independent result.

## Working tree safety
The revert test backs up every file it will touch, checks the backup's hash, and verifies a fingerprint of all
tracked and untracked files after restoring. On mismatch it exits 5 and keeps the backup in `.fixproof/backup/`.
With unmerged paths it refuses (BLOCKED) without modifying anything.

## Secrets
Command output is redacted before it is stored (common token formats, PEM keys, `password=`-style pairs, and values of
env vars whose names contain KEY/TOKEN/SECRET/PASSWORD/CREDENTIAL). Redaction is pattern-based: review reports before sharing.
Repro commands run with your privileges; do not run FixProof on untrusted repositories.

## Reporting
Please report vulnerabilities privately to the maintainers via a GitHub security advisory on this repository.
