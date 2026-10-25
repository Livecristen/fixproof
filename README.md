# FixProof

**Stop trusting AI fixes. Start verifying them.**

FixProof is an agent skill (`SKILL.md`) plus a small CLI (`scripts/verify.py`, Python 3.9+, standard library, no install)
for Claude Code, Codex, Cursor and other agents. The agent reproduces a bug and fixes it; **the CLI runs the commands itself,
records the evidence, and decides the status**. The CLI checks the evidence, not the agent.

FixProof makes made-up results hard and visible: results come from runs the CLI executed, records are hash-chained,
and `validate` recomputes the status from the raw evidence. It is not tamper-proof against an agent that rewrites
`.fixproof/` and recomputes the chain; see [SECURITY.md](SECURITY.md).

## Install (one folder)
```
# Claude Code (personal skills)
git clone https://github.com/Livecristen/fixproof ~/.claude/skills/fixproof
# Codex
git clone https://github.com/Livecristen/fixproof ~/.codex/skills/fixproof
# Cursor (project skill)
git clone https://github.com/Livecristen/fixproof .cursor/skills/fixproof
```
The skill needs `SKILL.md` and `scripts/verify.py`. Check it works: `python scripts/verify.py --help`.

## Use
```
python verify.py init  --repro "python -m pytest tests/test_bug.py" --suite "python -m pytest"
# ... apply the fix ...
python verify.py check            # status + .fixproof/report.json, exit code = status
python verify.py validate .fixproof/report.json
python verify.py restore          # after an interrupted run: put backed-up files back
```
Options: `--reruns N`, `--timeout S`, `--require-env VAR`, `--require-tool TOOL`, `--pass-env VAR`, `--no-shell`,
`--allow-exe NAME`, `--test-glob GLOB`, `--no-revert`, `--revert-mode worktree`, `--include-ignored`, `--dry-run`,
`--discard-backup`, `--json .fixproof/NAME.json`.

**Warning:** the revert test temporarily modifies files in your working tree. FixProof prints a WARNING with the file
list and backup path before it touches anything, and warns on protected-looking branches (main/master/release/prod),
configured remotes and root. Use `check --dry-run` to preview, or `check --revert-mode worktree` to run the revert test
in a temporary git worktree instead (ignored files such as `node_modules` are not present there).

## How a fix becomes VERIFIED
1. Baseline: the repro command fails on the unfixed tree (and not because of a timeout or a missing tool).
2. After the fix it passes on every rerun (mixed results are reported as flaky).
3. Suite commands that passed before still pass (pass-to-pass, as in SWE-bench grading).
4. **Revert test:** the CLI removes the non-test part of the fix, runs the repro (it must fail), and restores every
   file byte-for-byte, verified by a fingerprint of all tracked and untracked files. Uncommitted work is backed up
   before anything is touched; if the tree cannot be backed up safely (for example unmerged paths) the result is BLOCKED and nothing is modified.

Statuses and exit codes are documented in [SKILL.md](SKILL.md).

## Related work
- [obra/superpowers verification-before-completion](https://github.com/obra/superpowers/tree/main/skills/verification-before-completion),
  [rpikit](https://github.com/bostonaholic/rpikit), [ai-devkit verify](https://ai-devkit.com/skills/verify/): prompt rules for evidence before claims; FixProof adds a CLI that checks the evidence.
- [silkyland/reproduce-my-bug](https://github.com/silkyland/reproduce-my-bug) delivers the reproduction; FixProof proves the fix.

## Examples
`python examples/run_example.py python` · `... js-ts` · `... ts` (TypeScript needs Node 23.6+ for built-in type stripping).

## Limits (v1)
Git repositories are required. Test/fix separation uses path globs. Suite regressions are tracked per command, not per test case.

## License
MIT. See [LICENSE](LICENSE).

Not affiliated with Anthropic, OpenAI or Anysphere; names are trademarks of their owners.
