> **INTERNAL – not part of the release.** See references/README.md.

# FixProof – Research (Phase 1)

Date: 2026-10-25. Sources were opened/searched this session. Items marked (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth).

## 1. What exists

| Tool | Type | What it does | Machine-checks evidence? | Source |
|---|---|---|---|---|
| obra/superpowers `verification-before-completion` | Agent skill (prompt) | A central rule that the agent may not claim completion unless it has just run the proving command; a five-step gate (pick the command, run it, read the output, compare it with the claim, then state it). Its pattern section also recommends a red-green check for regression tests: confirm the test passes with the fix, fails once the fix is undone, and passes again after it is restored. | No, it is instructions to the agent only | https://github.com/obra/superpowers/tree/main/skills/verification-before-completion · mirror: https://github.com/openai/plugins/blob/main/plugins/superpowers/skills/verification-before-completion/SKILL.md |
| bostonaholic/rpikit `verification-before-completion` + `verifier` agent | Skill + LLM sub-agent | Same 5-step gate; a "Before claiming Fixed" checklist; the verifier agent runs format/lint/typecheck/build/tests and gives PASS/FAIL/WARN, which its own docs call "advisory". | No, the verdict comes from an LLM agent (`model: haiku`) | https://github.com/bostonaholic/rpikit/blob/main/skills/verification-before-completion/SKILL.md · https://github.com/bostonaholic/rpikit/blob/main/agents/verifier.md |
| codeaholicguy/ai-devkit `verify` | Agent skill (prompt) | 5-step gate, a list of hedging words to avoid in completion claims, and an explicit six-step regression check that undoes the fix and treats a still-passing test as a broken test. | No | https://github.com/codeaholicguy/ai-devkit/blob/main/skills/verify/SKILL.md · https://ai-devkit.com/skills/verify/ |
| silkyland/reproduce-my-bug | Agent skill (prompt), MIT | Never fixes. Intake, evidence sweep, ranked hypotheses, minimal failing test, flaky protocol, then a `REPRO.md` dossier. Outcomes: DETERMINISTIC / RATE-BASED / NOT-YET-REPRODUCED. Repo created 2026-07-06, 0 stars at fetch time. | No | https://github.com/silkyland/reproduce-my-bug · https://www.skills.sh/silkyland/reproduce-my-bug/reproduce-my-bug |
| obra/superpowers `systematic-debugging`, `test-driven-development` | Agent skills (prompt) | Root cause before any fix; a failing test before any code. | No | https://github.com/obra/superpowers/blob/main/skills/systematic-debugging/SKILL.md · https://github.com/openai/plugins/blob/main/plugins/superpowers/skills/test-driven-development/SKILL.md |
| agensi "flaky-test-detector" | Commercial skill listing | Rerun loops, root-cause classes, quarantine. | Unclear (only the listing was read) | https://www.agensi.io/skills/flaky-test-detector |
| SWE-bench harness | Benchmark grader (code) | Grades patches by FAIL_TO_PASS (tests that failed must now pass) and PASS_TO_PASS (tests that passed must still pass). | **Yes**, but it is benchmark infrastructure (Docker, a fixed dataset), not a per-fix tool for developers | https://github.com/SWE-bench/SWE-bench/blob/main/swebench/harness/grading.py · https://github.com/SWE-bench/SWE-bench/issues/174 |
| pytest-rerunfailures / pytest-flakefinder | pytest plugins | Repeat tests to expose flakiness. | Yes, for flakiness only | https://github.com/pytest-dev/pytest-rerunfailures (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth) · named in the agensi listing above |
| mutmut / Stryker | Mutation testing | Checks whether tests detect code changes (the "green test without relevant behavior" problem, at large scale and high cost). | Yes, but heavy and not fix-scoped | https://github.com/boxed/mutmut (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth) · https://stryker-mutator.io (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth) |
| gitleaks / detect-secrets | Secret scanners | Find credentials in repos. | Yes, for secrets only | https://github.com/gitleaks/gitleaks (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth) · https://github.com/Yelp/detect-secrets (URL verified reachable, HTTP 200, 2026-10-25; content not reviewed in depth) |

### Checking Product & Community's competitor claims
- "verification-before-completion (superpowers, rpikit, ai-devkit/verify) is only a prompt rule": **Confirmed** for all three. rpikit adds an LLM verifier agent, but that is still not a deterministic check.
- "ai-devkit also asks for a revert test": **Confirmed. Correction:** superpowers recommends it too (its pattern section describes undoing the fix and expecting the test to fail). Neither one enforces it by machine.
- "reproduce-my-bug only reproduces and never fixes; REPRO.md; DETERMINISTIC / RATE-BASED / NOT-YET-REPRODUCED": **Confirmed** from the README.
- "Nothing checks the evidence by machine": **Confirmed for the agent-skill ecosystem we checked.** It is **not true in general**: SWE-bench grading, mutation testing and flaky-test plugins check parts of this by machine. Our wording must stay limited to "agent fix-verification skills". We only searched the sources listed above, so this is not an exhaustive market survey.

## 2. What is missing (gaps)
1. No skill **records** before/after runs as evidence the tool captures itself (command, exit code, output hash, timestamps). Every existing skill relies on the agent describing what it saw.
2. The revert test exists only as an instruction. Nothing runs it automatically and checks that the working tree was restored.
3. There is no shared status vocabulary for fix verification with written rules (VERIFIED / FAILED / PARTIALLY / UNVERIFIED / BLOCKED). rpikit uses PASS/FAIL/WARN, and reproduce-my-bug only has reproduction statuses.
4. Exit 0 counts as success. No tool checks that the relevant test actually ran (for example "0 tests collected" or a filter that matched nothing).
5. Flaky runs, missing dependencies, timeouts and a missing environment are not told apart from FAILED.
6. Reports are not redacted for secrets.
7. There is no handoff format from a reproduction to a fix proof. reproduce-my-bug's REPRO.md "one command that fails" could feed in directly.

## 3. Where we can honestly do better
- Positioning: **"The CLI checks the evidence, not the agent."** Boundary: *reproduce-my-bug delivers the reproduction; FixProof proves the fix.*
- Honest claim: FixProof **makes made-up results hard and visible**. Do NOT claim "first", "only" or "unforgeable". An agent with shell access can still tamper with files. We make that detectable, not impossible.
- FixProof is not a debugging method and not a replacement for TDD or mutation testing. It is a small, fix-scoped mix of SWE-bench-style F2P/P2P logic, a revert test and secret redaction, packaged as a portable skill.
