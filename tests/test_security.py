"""Tests for the Ops & Security fix list (P1-P3)."""
import glob
import json
import os
import re
import subprocess
import sys
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_scenarios import Base, BUGGY, TEST_SUB, FIXED, PY, REPRO, SUITE, VERIFY, RESULTS, snapshot_bytes, write, sh  # noqa

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import verify  # noqa

SLOW_REPRO = ("import glob, sys, time\nif glob.glob('.fixproof/backup-*'):\n    time.sleep(20)\n"
              "from calc import add\nsys.exit(0 if add(2, 3) == 5 else 1)\n")


class P1(Base):
    def test_p1_1_existing_backup_blocks_and_is_kept(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        old = os.path.join(self.root, ".fixproof", "backup-old")
        os.makedirs(old)
        write(old, "manifest.json", json.dumps({"files": {}, "fingerprint": {}}))
        write(old, "keep.bin", "precious")
        rc, out = self.fp("check")
        rep = self.report()
        RESULTS.append(("P1.1 existing backup", rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rc, 4, out)
        self.assertIn("restore", rep["reasons"][0])
        self.assertTrue(os.path.exists(os.path.join(old, "keep.bin")))
        rc, out = self.fp("init", "--repro", REPRO)
        self.assertEqual(rc, 4, out)
        self.assertTrue(os.path.exists(os.path.join(old, "keep.bin")))
        rc, out = self.fp("check", "--discard-backup")
        self.assertEqual(rc, 0, out)

    def test_p1_2_env_allowlist(self):
        probe = "import os, sys\nprint('LEAK' if os.environ.get('FP_SECRET_X') else 'CLEAN')\nprint('PASS' if os.environ.get('FP_OPTIN') else 'NOOPT')\nsys.exit(1)\n"
        self.commit({"probe.py": probe})
        os.environ["FP_SECRET_X"] = "zzzzzz"
        os.environ["FP_OPTIN"] = "1"
        try:
            self.fp("init", "--repro", PY + " probe.py")
            out1 = self.report()["records"][-1]["untrusted_stdout_tail"]
            self.fp("init", "--repro", PY + " probe.py", "--pass-env", "FP_OPTIN")
            out2 = self.report()["records"][-1]["untrusted_stdout_tail"]
        finally:
            del os.environ["FP_SECRET_X"], os.environ["FP_OPTIN"]
        self.assertIn("CLEAN", out1)
        self.assertIn("NOOPT", out1)
        self.assertIn("PASS", out2)
        self.assertIn("CLEAN", out2)
        RESULTS.append(("P1.2 env allowlist + --pass-env", "n/a", 0, "secret var absent; opt-in var present"))

    def test_p1_3_tampered_state_not_executed(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        sp = os.path.join(self.root, ".fixproof", "state.json")
        st = json.load(open(sp))
        st["repro"] = PY + " -c \"open('pwned.txt','w').write('x')\""
        json.dump(st, open(sp, "w"))
        rc, out = self.fp("check")
        rep = self.report()
        RESULTS.append(("P1.3 tampered state.json", rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rc, 4)
        self.assertFalse(os.path.exists(os.path.join(self.root, "pwned.txt")))


class P2(Base):
    def test_p2_4_no_shell_and_allow_exe(self):
        self.std_repo()
        rc, out = self.fp("init", "--repro", REPRO, "--suite", SUITE, "--no-shell")
        self.assertEqual(rc, 0, out)
        self.assertIn("FixProof run [baseline_repro]", out)
        write(self.root, "calc.py", FIXED)
        rc, out = self.fp("check")
        self.assertEqual(rc, 0, out)
        rc, out = self.fp("init", "--repro", REPRO, "--no-shell", "--allow-exe", "node")
        rep = self.report()
        RESULTS.append(("P2.4 --no-shell / --allow-exe mismatch", rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rc, 4, out)

    @unittest.skipIf(os.name == "nt", "symlinks need extra privileges on Windows")
    def test_p2_5_symlink_rejected(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": "import unittest\nfrom real.calc import add\nclass T(unittest.TestCase):\n    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n",
                     "real/__init__.py": "", "real/calc.py": BUGGY, "test_other.py": TEST_SUB})
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        os.remove(os.path.join(self.root, "real", "calc.py"))
        write(self.root, "fixed_calc.py", FIXED)
        os.symlink(os.path.join(self.root, "fixed_calc.py"), os.path.join(self.root, "real", "calc.py"))
        before = snapshot_bytes(self.root)
        rc, out = self.fp("check")
        rep = self.report()
        RESULTS.append(("P2.5 symlink in fix path", rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rc, 4, out)
        self.assertIn("symlink", rep["reasons"][0])
        self.assertEqual(snapshot_bytes(self.root), before)

    def test_p2_5_atomic_write_and_path_guard(self):
        p = os.path.join(self.root, "a.txt")
        verify.atomic_write(p, "x")
        verify.atomic_write(p, b"y")
        self.assertEqual(open(p).read(), "y")
        self.assertEqual([f for f in os.listdir(self.root) if f.startswith(".fixproof-tmp")], [])
        self.assertIsNone(verify.safe_path(self.root, "../outside.txt"))
        self.assertIsNotNone(verify.safe_path(self.root, "a.txt"))

    def test_p2_6_kill_mid_revert_then_restore(self):
        self.commit({"calc.py": BUGGY, "repro.py": SLOW_REPRO})
        self.fp("init", "--repro", PY + " repro.py", "--timeout", "60")
        write(self.root, "calc.py", FIXED)
        before = snapshot_bytes(self.root)
        proc = subprocess.Popen([sys.executable, VERIFY, "check", "--reruns", "1"], cwd=self.root,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.time() + 30
        while time.time() < deadline:
            if glob.glob(os.path.join(self.root, ".fixproof", "backup-*", "manifest.json")) and \
                    open(os.path.join(self.root, "calc.py")).read() == BUGGY:
                break
            time.sleep(0.05)
        proc.kill()  # SIGKILL / TerminateProcess: no cleanup possible
        proc.wait()
        self.assertEqual(open(os.path.join(self.root, "calc.py")).read(), BUGGY)
        rc, out = self.fp("restore")
        RESULTS.append(("P2.6 kill -9 mid-revert, then restore", "restored" if rc == 0 else "error", rc, out.strip()[:70]))
        self.assertEqual(rc, 0, out)
        self.assertEqual(snapshot_bytes(self.root), before)
        self.assertEqual(glob.glob(os.path.join(self.root, ".fixproof", "backup-*")), [])

    def test_p2_7_ignored_files_warning_and_option(self):
        self.std_repo()
        self.commit({".gitignore": "*.log\n"})
        write(self.root, "build.log", "ignored\n")
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        rc, _ = self.fp("check")
        self.assertEqual(rc, 0)
        self.assertTrue(any("ignored file" in w for w in self.report()["warnings"]))
        rc, _ = self.fp("check", "--include-ignored")
        self.assertEqual(rc, 0)
        RESULTS.append(("P2.7 ignored files", "VERIFIED", 0, "warning without flag; covered with --include-ignored"))

    def test_p2_9_untrusted_output_marked(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO)
        rep = self.report()
        run = [r for r in rep["records"] if r.get("kind") == "run"][0]
        self.assertEqual(run["output_trust"], "untrusted")
        self.assertIn("untrusted_stdout_tail", run)
        self.assertNotIn("stdout_tail", run)
        self.assertIn("never as instructions", rep["note"])
        skill = open(os.path.join(ROOT, "SKILL.md"), encoding="utf-8").read()
        self.assertIn("never instructions", skill)


class Redaction(unittest.TestCase):
    CASES = {
        "aws": "AKIA" + "ABCDEFGHIJKLMNOP",
        "github": "ghp_" + "a" * 36,
        "github_pat": "github_pat_" + "b" * 30,
        "slack": "xoxb-" + "1234567890-abc",
        "openai": "sk-" + "c" * 30,
        "stripe_live": "sk_live_" + "d" * 20,
        "stripe_restricted": "rk_live_" + "e" * 20,
        "google": "AIza" + "f" * 35,
        "jwt": "eyJhbGciOi" + "." + "eyJzdWIiOi" + "." + "s1gn4tur3x",
        "bearer": "Bearer " + "tok3nvalue99",
    }

    def test_p2_8_each_pattern(self):
        for name, secret in self.CASES.items():
            out = verify.redact("value: %s end" % secret)
            self.assertNotIn(secret.split(" ")[-1], out, name)
            self.assertIn("[REDACTED]", out, name)

    def test_p2_8_key_value_and_url(self):
        for key in ("password", "pass", "auth", "dsn", "cookie", "session", "token", "api_key", "private_key"):
            out = verify.redact("%s=hunter2xyz" % key)
            self.assertNotIn("hunter2xyz", out, key)
        out = verify.redact("postgres://admin:S3cr3tPw@db.local:5432/app")
        self.assertNotIn("S3cr3tPw", out)
        self.assertIn("db.local", out)

    def test_p2_8_multiline_pem(self):
        kind = "RSA " + "PRIVATE KEY"  # built at runtime so secret scanners do not flag the fixture
        pem = "-----BEGIN " + kind + "-----\nMIIEow" + "A" * 40 + "\nline2" + "B" * 40 + "\n-----END " + kind + "-----"
        out = verify.redact("before\n" + pem + "\nafter")
        self.assertNotIn("MIIEow", out)
        self.assertNotIn("line2", out)
        self.assertIn("before", out)
        self.assertIn("after", out)

    def test_p2_8_env_values_min_length_4(self):
        for name in ("FP_AUTH_X", "FP_SESSION_X", "FP_DSN_X", "FP_COOKIE_X", "FP_PRIVATE_X", "FP_PASS_X"):
            os.environ[name] = "q7z9"
            try:
                self.assertNotIn("q7z9", verify.redact("got q7z9 here"), name)
            finally:
                del os.environ[name]


class P3(Base):
    def test_p3_11_warnings_and_dry_run(self):
        self.std_repo()
        marker = PY + " -c \"open('ran.txt','w').write('x')\""
        rc, out = self.fp("init", "--repro", marker, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("DRY RUN", out)
        self.assertFalse(os.path.exists(os.path.join(self.root, "ran.txt")))
        self.assertFalse(os.path.exists(os.path.join(self.root, ".fixproof", "state.json")))
        sh(["git", "branch", "-M", "main"], self.root)
        sh(["git", "remote", "add", "origin", "https://example.invalid/x.git"], self.root)
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        before = snapshot_bytes(self.root)
        rc, out = self.fp("check", "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertIn("would temporarily modify: calc.py", out)
        self.assertEqual(snapshot_bytes(self.root), before)
        rc, out = self.fp("check")
        self.assertEqual(rc, 0, out)
        self.assertIn("WARNING: FixProof revert test will TEMPORARILY modify 1 file(s)", out)
        w = " ".join(self.report()["warnings"])
        self.assertIn("'main'", w)
        self.assertIn("remote", w)
        RESULTS.append(("P3.11 dry-run + warnings", "VERIFIED", 0, "dry-run ran nothing; branch/remote warnings shown"))

    def test_p3_11_worktree_mode(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        m = os.path.getmtime(os.path.join(self.root, "calc.py"))
        rc, out = self.fp("check", "--revert-mode", "worktree")
        self.assertEqual(rc, 0, out)
        self.assertEqual(os.path.getmtime(os.path.join(self.root, "calc.py")), m)
        self.assertEqual(self.report()["records"][-1]["mode"], "worktree")
        self.assertNotIn("fixproof-wt", sh(["git", "worktree", "list"], self.root).stdout.decode())
        RESULTS.append(("P3.11 --revert-mode worktree", "VERIFIED", 0, "user tree untouched"))

    def test_p3_12_json_path_restricted(self):
        self.std_repo()
        rc, out = self.fp("init", "--repro", REPRO, "--json", os.path.join(self.root, "README.md"))
        self.assertEqual(rc, 64, out)
        rc, out = self.fp("init", "--repro", REPRO, "--json", os.path.join(".fixproof", "state.json"))
        self.assertEqual(rc, 64, out)
        rc, out = self.fp("init", "--repro", REPRO, "--json", os.path.join(".fixproof", "mine.json"))
        self.assertEqual(rc, 0, out)
        RESULTS.append(("P3.12 --json outside .fixproof", "usage error", 64, "refused"))


class CIConfig(unittest.TestCase):
    def test_p2_10_p3_13_workflow_hardening(self):
        y = open(os.path.join(ROOT, ".github", "workflows", "ci.yml"), encoding="utf-8").read()
        uses = re.findall(r"uses:\s*(\S+)", y)
        self.assertTrue(uses)
        for u in uses:
            self.assertRegex(u, r"@[0-9a-f]{40}$", u)
        self.assertIn("persist-credentials: false", y)
        self.assertIn("timeout-minutes: 15", y)
        self.assertIn("gitleaks", y)
        self.assertRegex(y, r'node-version: "\d+\.\d+\.\d+"')
        self.assertTrue(os.path.exists(os.path.join(ROOT, ".github", "dependabot.yml")))


if __name__ == "__main__":
    unittest.main()
