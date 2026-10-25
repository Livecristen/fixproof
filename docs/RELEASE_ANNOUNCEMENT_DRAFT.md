# DRAFT — do not publish

> **DRAFT.** Maintainer copy for a possible FixProof v0.3.0 note. This file has not been posted. Do not publish it to GitHub Releases, a discussion, social media, a chat, or a mailing list. Publishing this draft is not part of preparing the documentation.

## Suggested title

FixProof v0.3.0

## Suggested body

FixProof 0.3.0 is an MIT-licensed agent skill and a Python command-line tool that checks bug fixes with evidence the tool collected itself.

The skill tells the agent to reproduce the bug and edit the code. `scripts/verify.py` runs the reproduction, the suite, and a revert test, writes a hash-chained log under `.fixproof/`, and sets the status. `validate` recomputes that status from the records. The CLI needs Python 3.9 or newer and the standard library. There is no package install.

Agent skills such as verification-before-completion (superpowers and rpikit) and ai-devkit verify are prompt-level rules. reproduce-my-bug produces a reproduction dossier and does not verify the fix. FixProof's CLI validates the evidence itself.

A fix is **VERIFIED** when the baseline reproduction failed, the fix passes every rerun, the reproduction fails again with the non-test edits removed, the tree is restored, and no suite command that passed before now fails. The other verdicts are **FAILED**, **PARTIALLY VERIFIED**, **UNVERIFIED**, and **BLOCKED**. A restore mismatch stays BLOCKED and exits 5. Usage errors exit 64.

The log makes a hand-edited report visible: `validate` rejects a status that does not follow from the records. It does not stop an agent that can delete `.fixproof/` and write a new chain. Re-run `check` when you want a result from a machine you trust.

Install by cloning the repository into the agent skill folder (Claude Code, Codex, or Cursor). The README has the commands. Then run `scripts/verify.py --version`.

The Python, JavaScript, and TypeScript examples are in `examples/` and are run by `examples/run_example.py`. The TypeScript example: Tested with Node 22.18.0+ / 23.6.0+ / 24.x (unflagged type stripping); CI uses 24.22.1.

Known limits, spelled out in the README: the project must be a git repository; test paths and fix paths are split by globs; suite results are per command; the in-place revert test edits the working tree until restore finishes.

License: MIT.

## What this draft deliberately leaves out

No download counts, benchmarks, quotes, or user stories. No date is attached to later work. The repository's visibility is unchanged by this file.

## Maintainer checklist, if this note is ever published

- [ ] A maintainer has approved the wording against `README.md`, `SKILL.md`, and `scripts/verify.py`.
- [ ] `python3 scripts/verify.py --version` prints the version in the title.
- [ ] The install commands in the README have been run again.
- [ ] The DRAFT banner and this checklist are removed from the text that is actually published.
- [ ] The published text does not use the wording rejected by `tests/test_meta.py`.
