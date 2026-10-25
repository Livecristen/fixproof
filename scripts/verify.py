#!/usr/bin/env python3
"""FixProof CLI: verify that a bug fix actually fixes the bug.

Python 3.9+, standard library modules exclusively. The CLI runs every command
itself and records the evidence; agents never supply results.

Commands:
  init      record the baseline (unfixed tree) and run the reproduction
  check     after the fix: reruns, suite, revert test, status, JSON report
  validate  re-check a JSON report (hash chain + recomputed status)
"""
import argparse
import datetime
import fnmatch
import hashlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import tempfile
import time

VERSION = "0.1.0"
STATE_DIR = ".fixproof"

EXIT = {
    "VERIFIED": 0,
    "FAILED": 1,
    "PARTIALLY VERIFIED": 2,
    "UNVERIFIED": 3,
    "BLOCKED": 4,
}
EXIT_RESTORE_ERROR = 5
EXIT_USAGE = 64

DEFAULT_TEST_GLOBS = [
    "test_*.py", "*_test.py", "tests/*", "test/*", "__tests__/*",
    "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts", "*.test.mjs",
    "*.test.cjs", "*.test.tsx", "*.spec.tsx",
]

MISSING_DEP_PATTERNS = [
    r"ModuleNotFoundError", r"ImportError: ", r"Cannot find module",
    r"ERR_MODULE_NOT_FOUND", r"command not found",
    r"is not recognized as an internal or external command",
    r"No such file or directory: '[^']*'\s*$",
]
ZERO_TESTS_PATTERNS = [
    r"\bRan 0 tests\b", r"\bcollected 0 items\b", r"\bno tests ran\b",
    r"^# tests 0\s*$", r"\bNo tests found\b", r"\b0 passing\b",
]

SECRET_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}\b"),
    re.compile(r"\bxox[abprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}"),
    re.compile(r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|access[_-]?key)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
]
SECRET_ENV_HINT = re.compile(r"(?i)(KEY|TOKEN|SECRET|PASSWORD|PASSWD|CREDENTIAL)")


# ----------------------------------------------------------------- helpers
def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha256(data):
    if isinstance(data, str):
        data = data.encode("utf-8", "replace")
    return hashlib.sha256(data).hexdigest()


def redact(text):
    if not text:
        return text
    for value in sorted(_secret_env_values(), key=len, reverse=True):
        text = text.replace(value, "[REDACTED]")
    for pat in SECRET_PATTERNS:
        if pat.groups >= 3:
            text = pat.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)
        else:
            text = pat.sub("[REDACTED]", text)
    return text


def _secret_env_values():
    out = []
    for k, v in os.environ.items():
        if SECRET_ENV_HINT.search(k) and v and len(v) >= 6:
            out.append(v)
    return out


def git(root, *args, check=True, raw=False):
    p = subprocess.run(["git", "-C", root] + list(args), stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise GitError("git %s failed: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout if raw else p.stdout.decode("utf-8", "replace")


class GitError(Exception):
    pass


def find_git_root(path):
    try:
        out = subprocess.run(["git", "-C", path, "rev-parse", "--show-toplevel"],
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except FileNotFoundError:
        return None
    if out.returncode != 0:
        return None
    return os.path.normpath(out.stdout.decode().strip())


def state_path(root, name):
    return os.path.join(root, STATE_DIR, name)


def is_test_path(path, globs):
    p = path.replace("\\", "/")
    base = p.rsplit("/", 1)[-1]
    parts = p.split("/")
    for g in globs:
        if fnmatch.fnmatch(p, g) or fnmatch.fnmatch(base, g):
            return True
        if g.endswith("/*") and g[:-2] in parts[:-1]:
            return True
    return False


# -------------------------------------------------------------- worktree
def list_worktree_files(root):
    out = git(root, "ls-files", "-z", "-c", "-o", "--exclude-standard", raw=True)
    files = sorted(set(f.decode("utf-8", "surrogateescape") for f in out.split(b"\0") if f))
    return [f for f in files if not f.replace("\\", "/").startswith(STATE_DIR + "/")]


def fingerprint(root):
    """Map of path -> sha256 of raw bytes for tracked + untracked files."""
    fp = {}
    for f in list_worktree_files(root):
        full = os.path.join(root, f)
        if os.path.isfile(full):
            with open(full, "rb") as fh:
                fp[f] = sha256(fh.read())
    return fp


def snapshot_tree(root):
    """Write a git tree object of the whole worktree without touching the real index."""
    fd, tmp_index = tempfile.mkstemp(prefix="fixproof-index-")
    os.close(fd)
    os.remove(tmp_index)
    env = dict(os.environ, GIT_INDEX_FILE=tmp_index)
    try:
        for args in (["add", "-A"], ["write-tree"]):
            p = subprocess.run(["git", "-C", root] + args, env=env,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if p.returncode != 0:
                raise GitError(p.stderr.decode("utf-8", "replace").strip())
        return p.stdout.decode().strip()
    finally:
        if os.path.exists(tmp_index):
            os.remove(tmp_index)


def changed_paths(root, base_tree, cur_tree):
    out = git(root, "diff", "--name-status", "--no-renames", "-z", base_tree, cur_tree, raw=True)
    items = [x.decode("utf-8", "surrogateescape") for x in out.split(b"\0") if x]
    res = []
    for i in range(0, len(items) - 1, 2):
        res.append((items[i], items[i + 1]))
    return res


def unmerged(root):
    return git(root, "ls-files", "-u").strip() != ""


# ------------------------------------------------------------- running
def run_cmd(cmd, cwd, timeout, label):
    start = time.time()
    started = now()
    kwargs = {}
    if os.name == "nt":
        kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP
    else:
        kwargs["start_new_session"] = True
    timed_out = False
    try:
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        proc = subprocess.Popen(cmd, shell=True, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, env=env, **kwargs)
    except OSError as e:
        return _record(label, cmd, started, time.time() - start, 127, "", str(e), False)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        _kill_tree(proc)
        try:
            out, err = proc.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            out, err = b"", b""
    return _record(label, cmd, started, time.time() - start,
                   proc.returncode, out.decode("utf-8", "replace"),
                   err.decode("utf-8", "replace"), timed_out)


def _kill_tree(proc):
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except Exception:
        proc.kill()


def classify(rc, out, err, timed_out):
    text = (out or "") + "\n" + (err or "")
    if timed_out:
        return "timeout"
    if rc == 127 or (rc != 0 and any(re.search(p, text, re.M) for p in MISSING_DEP_PATTERNS)):
        return "missing_dependency"
    if any(re.search(p, text, re.M | re.I) for p in ZERO_TESTS_PATTERNS):
        return "zero_tests"
    return "pass" if rc == 0 else "fail"


def _record(label, cmd, started, duration, rc, out, err, timed_out):
    outcome = classify(rc, out, err, timed_out)
    r_out, r_err = redact(out), redact(err)
    return {
        "label": label,
        "cmd": redact(cmd),
        "started": started,
        "duration_s": round(duration, 3),
        "exit_code": rc,
        "timed_out": timed_out,
        "outcome": outcome,
        "stdout_sha256": sha256(r_out),
        "stderr_sha256": sha256(r_err),
        "stdout_tail": r_out[-2000:],
        "stderr_tail": r_err[-2000:],
    }


# --------------------------------------------------------- evidence log
class Log:
    def __init__(self, root):
        self.path = state_path(root, "runs.jsonl")

    def records(self):
        if not os.path.exists(self.path):
            return []
        with open(self.path, encoding="utf-8") as fh:
            return [json.loads(l) for l in fh if l.strip()]

    def append(self, rec):
        recs = self.records()
        prev = recs[-1]["hash"] if recs else "0" * 64
        rec = dict(rec, seq=len(recs), prev=prev)
        rec["hash"] = record_hash(rec)
        with open(self.path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, sort_keys=True) + "\n")
        return rec


def record_hash(rec):
    body = {k: v for k, v in rec.items() if k != "hash"}
    return sha256(json.dumps(body, sort_keys=True))


def verify_chain(records):
    prev = "0" * 64
    for i, r in enumerate(records):
        if r.get("seq") != i or r.get("prev") != prev or record_hash(r) != r.get("hash"):
            return False, "record %d broken" % i
        prev = r["hash"]
    return True, ""


# ------------------------------------------------------------- status
def decide(records):
    """Compute status purely from evidence records. Returns (status, reasons)."""
    by = lambda kind: [r for r in records if r.get("kind") == kind]
    reasons = []
    env = by("env_check")
    if any(not r["ok"] for r in env):
        return "BLOCKED", ["environment: " + "; ".join(r["detail"] for r in env if not r["ok"])]
    base = [r for r in by("run") if r["label"] == "baseline_repro"]
    if not base:
        return "BLOCKED", ["no baseline run recorded"]
    b = base[-1]["outcome"]
    if b in ("timeout", "missing_dependency"):
        return "BLOCKED", ["baseline reproduction: " + b]
    if b == "zero_tests":
        return "UNVERIFIED", ["baseline reproduction ran zero tests"]
    if b == "pass":
        return "UNVERIFIED", ["bug not reproduced: baseline reproduction passed before the fix"]
    guards = by("guard")
    if any(not g["ok"] for g in guards):
        return "BLOCKED", [g["detail"] for g in guards if not g["ok"]]
    after = [r["outcome"] for r in by("run") if r["label"] == "after_repro"]
    if not after:
        return "UNVERIFIED", ["no post-fix run recorded"]
    if any(o in ("timeout", "missing_dependency") for o in after):
        return "BLOCKED", ["post-fix reproduction: " + ", ".join(sorted(set(after)))]
    if "zero_tests" in after:
        return "UNVERIFIED", ["post-fix reproduction ran zero tests"]
    passes = after.count("pass")
    if passes == 0:
        return "FAILED", ["fix does not solve the bug: reproduction still fails (%d/%d runs)" % (len(after), len(after))]
    if passes != len(after):
        return "UNVERIFIED", ["flaky: reproduction passed %d/%d runs after the fix" % (passes, len(after))]
    # suite (pass-to-pass)
    suite_base = {r["label"][len("baseline_suite:"):]: r["outcome"] for r in by("run") if r["label"].startswith("baseline_suite:")}
    suite_after = {r["label"][len("after_suite:"):]: r["outcome"] for r in by("run") if r["label"].startswith("after_suite:")}
    regressions = [k for k, v in suite_base.items() if v == "pass" and suite_after.get(k) == "fail"]
    if regressions:
        return "FAILED", ["regression: suite command(s) passed before and fail after the fix: " + ", ".join(regressions)]
    partial = []
    if not suite_base:
        partial.append("no regression suite given")
    else:
        bad = [k for k, v in suite_after.items() if v != "pass"]
        if bad:
            partial.append("suite not fully passing/runnable after fix: " + ", ".join(bad))
    rev = by("revert")
    if not rev:
        partial.append("revert test not run")
    else:
        rv = rev[-1]
        if rv["result"] == "restore_error":
            return "BLOCKED", ["revert test: working tree restore mismatch: " + rv["detail"]]
        if rv["result"] == "unsafe":
            return "BLOCKED", ["revert test refused: " + rv["detail"]]
        if rv["result"] == "passes_without_fix":
            return "UNVERIFIED", ["revert test: reproduction also passes WITHOUT the fix, so it does not prove the fix"]
        if rv["result"] == "not_possible":
            partial.append("revert test not possible: " + rv["detail"])
        elif rv["result"] != "fails_without_fix":
            partial.append("revert test inconclusive: " + rv["detail"])
    if partial:
        return "PARTIALLY VERIFIED", partial
    return "VERIFIED", ["baseline failed, fix passes all reruns, revert test fails without the fix, no regressions"]


# ---------------------------------------------------------- revert test
def revert_test(root, state, args, log):
    """Temporarily remove the fix (non-test changes), run the repro, restore bytes exactly."""
    globs = state["test_globs"]
    if unmerged(root):
        return log.append({"kind": "revert", "result": "unsafe",
                           "detail": "working tree has unmerged paths (merge/rebase in progress); cannot back up safely"})
    try:
        cur_tree = snapshot_tree(root)
    except GitError as e:
        return log.append({"kind": "revert", "result": "unsafe", "detail": "backup snapshot failed: %s" % e})
    changes = changed_paths(root, state["baseline_tree"], cur_tree)
    fix = [(s, p) for s, p in changes if not is_test_path(p, globs)]
    tests_changed = [p for s, p in changes if is_test_path(p, globs)]
    if not fix:
        detail = "no non-test changes to revert"
        if tests_changed:
            detail = "fix and test live in the same/test file(s): " + ", ".join(tests_changed)
        return log.append({"kind": "revert", "result": "not_possible", "detail": detail})

    # 1) backup raw bytes of every file we will touch, plus full fingerprint
    before_fp = fingerprint(root)
    backup_dir = state_path(root, "backup")
    if os.path.exists(backup_dir):
        shutil.rmtree(backup_dir)
    os.makedirs(backup_dir)
    manifest = {}
    try:
        for s, p in fix:
            full = os.path.join(root, p)
            if os.path.exists(full):
                dst = os.path.join(backup_dir, sha256(p))
                shutil.copy2(full, dst)
                with open(dst, "rb") as fh:
                    if sha256(fh.read()) != before_fp.get(p):
                        raise IOError("backup verification failed for %s" % p)
                manifest[p] = dst
            else:
                manifest[p] = None
        with open(os.path.join(backup_dir, "manifest.json"), "w", encoding="utf-8") as fh:
            json.dump({"files": manifest, "fingerprint": before_fp}, fh, indent=1)
    except (IOError, OSError) as e:
        return log.append({"kind": "revert", "result": "unsafe", "detail": "backup failed: %s" % e})

    run = None
    restore_problem = ""
    try:
        # 2) write baseline versions of fix files (or delete files the fix added)
        for s, p in fix:
            full = os.path.join(root, p)
            if s == "A":
                if os.path.exists(full):
                    os.remove(full)
            else:
                blob = git(root, "rev-parse", "%s:%s" % (state["baseline_tree"], p)).strip()
                data = git(root, "cat-file", "--filters", "--path=" + p, blob, raw=True)
                os.makedirs(os.path.dirname(full) or root, exist_ok=True)
                with open(full, "wb") as fh:
                    fh.write(data)
        run = run_cmd(state["repro"], root, args.timeout, "revert_repro")
    except Exception as e:  # noqa
        restore_problem = "error during revert: %s" % e
    finally:
        # 3) restore raw bytes exactly
        for p, src in manifest.items():
            full = os.path.join(root, p)
            if src is None:
                if os.path.exists(full):
                    os.remove(full)
            else:
                os.makedirs(os.path.dirname(full) or root, exist_ok=True)
                shutil.copy2(src, full)
    after_fp = fingerprint(root)
    if after_fp != before_fp:
        diff = sorted(set(k for k in set(before_fp) | set(after_fp) if before_fp.get(k) != after_fp.get(k)))
        return log.append({"kind": "revert", "result": "restore_error",
                           "detail": "files differ after restore: %s; backup kept in %s" % (", ".join(diff), backup_dir)})
    shutil.rmtree(backup_dir, ignore_errors=True)
    if run is None:
        return log.append({"kind": "revert", "result": "inconclusive", "detail": restore_problem,
                           "restored": True})
    log.append(dict(run, kind="run"))
    o = run["outcome"]
    result = {"pass": "passes_without_fix", "fail": "fails_without_fix"}.get(o, "inconclusive")
    return log.append({"kind": "revert", "result": result, "detail": "reproduction outcome without fix: " + o,
                       "reverted_files": [p for s, p in fix], "restored": True,
                       "test_files_changed": tests_changed})


# ------------------------------------------------------------- commands
def cmd_init(args):
    root = find_git_root(args.dir)
    if not root:
        print("FixProof: BLOCKED - %s is not a git repository (required in v1)" % args.dir)
        return EXIT["BLOCKED"]
    sd = os.path.join(root, STATE_DIR)
    if os.path.exists(sd):
        shutil.rmtree(sd)
    os.makedirs(sd)
    excl = os.path.join(git(root, "rev-parse", "--git-dir").strip(), "info", "exclude")
    excl = excl if os.path.isabs(excl) else os.path.join(root, excl)
    os.makedirs(os.path.dirname(excl), exist_ok=True)
    existing = open(excl, encoding="utf-8").read() if os.path.exists(excl) else ""
    if STATE_DIR + "/" not in existing.split():
        with open(excl, "a", encoding="utf-8") as fh:
            fh.write("\n" + STATE_DIR + "/\n")
    log = Log(root)
    try:
        tree = snapshot_tree(root)
    except GitError as e:
        print("FixProof: BLOCKED - cannot snapshot tree: %s" % e)
        return EXIT["BLOCKED"]
    head = git(root, "rev-parse", "HEAD", check=False).strip()
    state = {"version": VERSION, "repro": args.repro, "suite": args.suite or [],
             "baseline_tree": tree, "baseline_head": head, "timeout": args.timeout,
             "test_globs": args.test_glob or DEFAULT_TEST_GLOBS,
             "require_env": args.require_env or [], "require_tool": args.require_tool or []}
    with open(state_path(root, "state.json"), "w", encoding="utf-8") as fh:
        json.dump(state, fh, indent=1)
    log.append({"kind": "baseline", "tree": tree, "head": head, "time": now(),
                "repro": redact(args.repro), "suite": [redact(s) for s in state["suite"]]})
    if not env_checks(state, log):
        return finish(root, log, args, "init")
    r = run_cmd(args.repro, root, args.timeout, "baseline_repro")
    log.append(dict(r, kind="run"))
    for i, s in enumerate(state["suite"]):
        log.append(dict(run_cmd(s, root, args.timeout, "baseline_suite:%d" % i), kind="run"))
    print("FixProof baseline: reproduction outcome = %s (exit %s)" % (r["outcome"], r["exit_code"]))
    if r["outcome"] != "fail":
        return finish(root, log, args, "init")
    print("Bug reproduced. Apply the fix, then run: verify.py check")
    return 0


def env_checks(state, log):
    ok = True
    for v in state["require_env"]:
        good = bool(os.environ.get(v))
        ok &= good
        log.append({"kind": "env_check", "ok": good, "detail": "env var %s %s" % (v, "set" if good else "missing")})
    for t in state["require_tool"]:
        good = shutil.which(t) is not None
        ok &= good
        log.append({"kind": "env_check", "ok": good, "detail": "tool %s %s" % (t, "found" if good else "missing")})
    return ok


def cmd_check(args):
    root = find_git_root(args.dir)
    if not root or not os.path.exists(state_path(root, "state.json")):
        print("FixProof: BLOCKED - no baseline found; run 'verify.py init' first (git repository required)")
        return EXIT["BLOCKED"]
    with open(state_path(root, "state.json"), encoding="utf-8") as fh:
        state = json.load(fh)
    if args.timeout is None:
        args.timeout = state["timeout"]
    log = Log(root)
    ok, why = verify_chain(log.records())
    if not ok:
        print("FixProof: UNVERIFIED - evidence log integrity mismatch (%s)" % why)
        return EXIT["UNVERIFIED"]
    if not env_checks(state, log):
        return finish(root, log, args, "check")
    if unmerged(root):
        log.append({"kind": "guard", "ok": False,
                    "detail": "dirty tree with unmerged paths: cannot back up safely; nothing was modified"})
        return finish(root, log, args, "check")
    for i in range(args.reruns):
        log.append(dict(run_cmd(state["repro"], root, args.timeout, "after_repro"), kind="run", rerun=i))
    for i, s in enumerate(state["suite"]):
        log.append(dict(run_cmd(s, root, args.timeout, "after_suite:%d" % i), kind="run"))
    status, _ = decide(log.records())
    if status in ("VERIFIED", "PARTIALLY VERIFIED") and not args.no_revert:
        revert_test(root, state, args, log)
    return finish(root, log, args, "check")


def build_report(root, records):
    status, reasons = decide(records)
    restore_err = any(r.get("kind") == "revert" and r.get("result") == "restore_error" for r in records)
    return {
        "tool": "fixproof", "version": VERSION, "generated": now(),
        "status": status, "exit_code": EXIT_RESTORE_ERROR if restore_err else EXIT[status],
        "reasons": reasons,
        "head": git(root, "rev-parse", "HEAD", check=False).strip() if root else "",
        "chain_head": records[-1]["hash"] if records else "",
        "records": records,
    }


def finish(root, log, args, phase):
    report = build_report(root, log.records())
    out = getattr(args, "json", None) or state_path(root, "report.json")
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(report, fh, indent=1, sort_keys=True)
    print_report(report, out)
    return report["exit_code"]


def print_report(report, path):
    print("=" * 60)
    print("FixProof %s  status: %s  (exit %d)" % (VERSION, report["status"], report["exit_code"]))
    for r in report["reasons"]:
        print("  - " + r)
    for rec in report["records"]:
        if rec.get("kind") == "run":
            print("  run %-16s exit=%-4s outcome=%-18s %.2fs  %s" % (
                rec["label"], rec["exit_code"], rec["outcome"], rec["duration_s"], rec["cmd"][:60]))
        elif rec.get("kind") == "revert":
            print("  revert test: %s (%s)" % (rec["result"], rec["detail"]))
    print("  report: %s" % path)
    print("  note: exit code 0 of a command alone never counts as a verified fix.")
    print("=" * 60)


def cmd_validate(args):
    try:
        with open(args.report, encoding="utf-8") as fh:
            rep = json.load(fh)
    except (OSError, ValueError) as e:
        print("FixProof validate: UNVERIFIED - unreadable report: %s" % e)
        return EXIT["UNVERIFIED"]
    recs = rep.get("records", [])
    ok, why = verify_chain(recs)
    problems = [] if ok else ["hash chain: " + why]
    if recs and rep.get("chain_head") != recs[-1].get("hash"):
        problems.append("chain_head does not match last record")
    status, reasons = decide(recs)
    if status != rep.get("status"):
        problems.append("status %r does not follow from evidence (recomputed %r)" % (rep.get("status"), status))
    restore_err = any(r.get("kind") == "revert" and r.get("result") == "restore_error" for r in recs)
    exp_exit = EXIT_RESTORE_ERROR if restore_err else EXIT[status]
    if rep.get("exit_code") != exp_exit:
        problems.append("exit_code does not follow from evidence")
    if problems:
        print("FixProof validate: UNVERIFIED - integrity mismatch")
        for p in problems:
            print("  - " + p)
        return EXIT["UNVERIFIED"]
    print("FixProof validate: report consistent; status %s" % status)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(prog="verify.py", description="FixProof: verify AI bug fixes with evidence.")
    ap.add_argument("--version", action="version", version=VERSION)
    sub = ap.add_subparsers(dest="cmd")
    pi = sub.add_parser("init", help="record baseline on the unfixed tree")
    pi.add_argument("--repro", required=True, help="command that reproduces the bug (must fail before the fix)")
    pi.add_argument("--suite", action="append", help="regression command (repeatable)")
    pi.add_argument("--timeout", type=float, default=300.0)
    pi.add_argument("--test-glob", action="append", help="glob for test paths (repeatable; replaces defaults)")
    pi.add_argument("--require-env", action="append", help="env var that must be set")
    pi.add_argument("--require-tool", action="append", help="executable that must be on PATH")
    pi.add_argument("--dir", default=".")
    pi.add_argument("--json")
    pc = sub.add_parser("check", help="verify the fix")
    pc.add_argument("--reruns", type=int, default=3)
    pc.add_argument("--timeout", type=float)
    pc.add_argument("--no-revert", action="store_true", help="skip revert test (result at most PARTIALLY VERIFIED)")
    pc.add_argument("--dir", default=".")
    pc.add_argument("--json")
    pv = sub.add_parser("validate", help="re-check a JSON report")
    pv.add_argument("report")
    try:
        args = ap.parse_args(argv)
    except SystemExit as e:
        return EXIT_USAGE if e.code else 0
    if not args.cmd:
        ap.print_help()
        return EXIT_USAGE
    try:
        return {"init": cmd_init, "check": cmd_check, "validate": cmd_validate}[args.cmd](args)
    except GitError as e:
        print("FixProof: BLOCKED - git error: %s" % e)
        return EXIT["BLOCKED"]


if __name__ == "__main__":
    sys.exit(main())
