"""Executed scenario tests for FixProof. Each test builds a throwaway git repo."""
import json
import os
import stat
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(os.path.dirname(HERE), "scripts", "verify.py")
PY = '"%s"' % sys.executable
RESULTS = []

BUGGY = "def add(a, b):\n    return a - b\n\n\ndef sub(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n\n\ndef sub(a, b):\n    return a - b\n"
TEST_ADD = ("import unittest\nfrom calc import add\n\n\nclass T(unittest.TestCase):\n"
            "    def test_add(self):\n        self.assertEqual(add(2, 3), 5)\n\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n")
TEST_SUB = ("import unittest\nfrom calc import sub\n\n\nclass T(unittest.TestCase):\n"
            "    def test_sub(self):\n        self.assertEqual(sub(5, 3), 2)\n\n\n"
            "if __name__ == '__main__':\n    unittest.main()\n")
REPRO = PY + " -m unittest test_calc"
SUITE = PY + " -m unittest test_other"


def sh(args, cwd, check=True):
    p = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if check and p.returncode != 0:
        raise AssertionError(p.stdout.decode())
    return p


def write(root, name, text):
    path = os.path.join(root, name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as fh:
        fh.write(text)


def snapshot_bytes(root):
    out = {}
    for d, dirs, files in os.walk(root):
        dirs[:] = [x for x in dirs if x not in (".git", ".fixproof", "__pycache__")]
        for f in files:
            p = os.path.join(d, f)
            with open(p, "rb") as fh:
                out[os.path.relpath(p, root)] = fh.read()
    return out


class Base(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="fixproof-t-")
        sh(["git", "init", "-q"], self.root)
        for k, v in (("user.name", "t"), ("user.email", "t@example.invalid"),
                     ("core.autocrlf", "false"), ("commit.gpgsign", "false")):
            sh(["git", "config", k, v], self.root)

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def commit(self, files):
        for k, v in files.items():
            write(self.root, k, v)
        sh(["git", "add", "-A"], self.root)
        sh(["git", "commit", "-q", "-m", "c"], self.root)

    def fp(self, *args):
        p = subprocess.run([sys.executable, VERIFY] + list(args), cwd=self.root,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        return p.returncode, p.stdout.decode("utf-8", "replace")

    def report(self):
        with open(os.path.join(self.root, ".fixproof", "report.json"), encoding="utf-8") as fh:
            return json.load(fh)

    def record(self, name, rc, expected_status, expected_rc):
        rep = self.report()
        RESULTS.append((name, rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rep["status"], expected_status, rep["reasons"])
        self.assertEqual(rc, expected_rc)
        vrc, vout = self.fp("validate", os.path.join(".fixproof", "report.json"))
        self.assertEqual(vrc, 0, vout)

    def std_repo(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": TEST_ADD, "test_other.py": TEST_SUB})


class Scenarios(Base):
    def test_01_real_fix(self):
        self.std_repo()
        rc, out = self.fp("init", "--repro", REPRO, "--suite", SUITE)
        self.assertEqual(rc, 0, out)
        write(self.root, "calc.py", FIXED)
        rc, out = self.fp("check")
        self.record("1 real fix", rc, "VERIFIED", 0)

    def test_02_fix_does_not_solve(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", BUGGY.replace("return a - b", "return a * b", 1))
        rc, _ = self.fp("check")
        self.record("2 fix does not solve bug", rc, "FAILED", 1)

    def test_03a_green_test_not_reproducing(self):
        self.commit({"calc.py": BUGGY, "test_other.py": TEST_SUB,
                     "test_calc.py": TEST_ADD.replace("self.assertEqual(add(2, 3), 5)", "self.assertTrue(True)")})
        rc, _ = self.fp("init", "--repro", REPRO, "--suite", SUITE)
        self.record("3a green test, bug not reproduced", rc, "UNVERIFIED", 3)

    def test_03b_test_passes_without_fix(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", "# fixed (claimed)\n" + BUGGY)
        write(self.root, "test_calc.py", TEST_ADD.replace("assertEqual(add(2, 3), 5)", "assertEqual(add(2, 3), -1)"))
        rc, _ = self.fp("check")
        self.record("3b test green without the fix (revert)", rc, "UNVERIFIED", 3)

    def test_04_missing_dependency(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": "import not_installed_pkg_xyz\n" + TEST_ADD,
                     "test_other.py": TEST_SUB})
        rc, _ = self.fp("init", "--repro", REPRO, "--suite", SUITE)
        self.record("4 missing dependency", rc, "BLOCKED", 4)

    def test_05_timeout(self):
        self.commit({"calc.py": BUGGY, "slow.py": "import time\ntime.sleep(30)\n"})
        rc, _ = self.fp("init", "--repro", PY + " slow.py", "--timeout", "2")
        self.record("5 timeout", rc, "BLOCKED", 4)

    def test_06_regression(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED.replace("def sub(a, b):\n    return a - b", "def sub(a, b):\n    return a + b"))
        rc, _ = self.fp("check")
        self.record("6 regression", rc, "FAILED", 1)

    def test_07_flaky(self):
        counter = os.path.join(self.root, "..", os.path.basename(self.root) + "-counter")
        self.addCleanup(lambda: os.path.exists(counter) and os.remove(counter))
        flaky = ("import os\nc = os.environ['FP_COUNTER']\nn = int(open(c).read()) if os.path.exists(c) else 0\n"
                 "open(c, 'w').write(str(n + 1))\n")
        self.commit({"calc.py": BUGGY, "test_other.py": TEST_SUB,
                     "test_calc.py": TEST_ADD.replace("    def test_add(self):\n",
                                                      "    def test_add(self):\n        if n % 2: self.fail('flaky')\n").replace(
                         "import unittest\n", "import unittest\n" + flaky, 1)})
        os.environ["FP_COUNTER"] = counter
        try:
            self.fp("init", "--repro", REPRO, "--suite", SUITE, "--pass-env", "FP_COUNTER")
            write(self.root, "calc.py", FIXED)
            rc, _ = self.fp("check", "--reruns", "4")
        finally:
            del os.environ["FP_COUNTER"]
        self.record("7 flaky", rc, "UNVERIFIED", 3)
        self.assertIn("flaky", self.report()["reasons"][0])

    def test_08_missing_environment(self):
        self.std_repo()
        os.environ.pop("FIXPROOF_TEST_DB_URL", None)
        rc, _ = self.fp("init", "--repro", REPRO, "--require-env", "FIXPROOF_TEST_DB_URL")
        self.record("8 missing environment", rc, "BLOCKED", 4)

    def test_09_secrets_redacted(self):
        secret_tok = "ghp_" + "A1b2C3d4E5f6G7h8I9j0K1l2M3n4O5p6Q7r8"
        env_secret = "s3cr3t-value-from-env-123"
        self.commit({"calc.py": BUGGY, "test_other.py": TEST_SUB,
                     "test_calc.py": "import os\nprint('token=%s')\nprint('db', os.environ['FP_DB_PASSWORD'])\n" % secret_tok + TEST_ADD})
        os.environ["FP_DB_PASSWORD"] = env_secret
        try:
            self.fp("init", "--repro", REPRO, "--suite", SUITE, "--pass-env", "FP_DB_PASSWORD")
            write(self.root, "calc.py", FIXED)
            rc, _ = self.fp("check")
        finally:
            del os.environ["FP_DB_PASSWORD"]
        self.record("9 report with secrets", rc, "VERIFIED", 0)
        blob = b""
        for d, _, files in os.walk(os.path.join(self.root, ".fixproof")):
            for f in files:
                blob += open(os.path.join(d, f), "rb").read()
        self.assertNotIn(secret_tok.encode(), blob)
        self.assertNotIn(env_secret.encode(), blob)
        self.assertIn(b"[REDACTED]", blob)

    def test_10_dirty_tree_unsafe_blocked(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": TEST_ADD, "test_other.py": TEST_SUB, "notes.txt": "base\n"})
        sh(["git", "checkout", "-q", "-b", "other"], self.root)
        self.commit({"notes.txt": "other branch\n"})
        sh(["git", "checkout", "-q", "-"], self.root)
        self.commit({"notes.txt": "main branch\n"})
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        write(self.root, "user_wip.txt", "my uncommitted work\r\nkeep me\n")
        sh(["git", "merge", "-q", "other"], self.root, check=False)  # conflict -> unmerged
        before = snapshot_bytes(self.root)
        rc, _ = self.fp("check")
        self.record("10 dirty tree, unsafe to back up", rc, "BLOCKED", 4)
        self.assertEqual(snapshot_bytes(self.root), before)

    def test_11_dirty_tree_backed_up(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": TEST_ADD, "test_other.py": TEST_SUB, "README": "x\n"})
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        write(self.root, "README", "user edit, CRLF\r\nline2\r\n")
        write(self.root, "wip/new.txt", "untracked work\n")
        before = snapshot_bytes(self.root)
        rc, _ = self.fp("check")
        self.record("11 dirty tree, backed up + restored", rc, "VERIFIED", 0)
        self.assertEqual(snapshot_bytes(self.root), before)


class Guards(Base):
    def _exclude(self):
        return os.path.join(self.root, ".git", "info", "exclude")

    def test_readonly_git_exclude_is_warning_not_crash(self):
        if hasattr(os, "geteuid") and os.geteuid() == 0:
            self.skipTest("root ignores file permissions")
        self.std_repo()
        excl = self._exclude()
        os.makedirs(os.path.dirname(excl), exist_ok=True)
        write(self.root, os.path.join(".git", "info", "exclude"), "# empty\n")
        os.chmod(excl, stat.S_IREAD)
        try:
            rc, out = self.fp("init", "--repro", REPRO, "--suite", SUITE)
        finally:
            os.chmod(excl, stat.S_IREAD | stat.S_IWRITE)
        self.assertEqual(rc, 0, out)
        self.assertIn("WARNING - could not add .fixproof/", out)
        self.assertNotIn("Traceback", out)

    def test_gitignore_entry_skips_exclude_write(self):
        self.commit({"calc.py": BUGGY, "test_calc.py": TEST_ADD, "test_other.py": TEST_SUB,
                     ".gitignore": ".fixproof/\n"})
        excl = self._exclude()
        before = open(excl, encoding="utf-8").read() if os.path.exists(excl) else None
        rc, out = self.fp("init", "--repro", REPRO, "--suite", SUITE)
        self.assertEqual(rc, 0, out)
        after = open(excl, encoding="utf-8").read() if os.path.exists(excl) else None
        self.assertEqual(before, after)

    def test_12_tampered_report(self):
        self.std_repo()
        self.fp("init", "--repro", REPRO, "--suite", SUITE)
        write(self.root, "calc.py", BUGGY.replace("return a - b", "return a * b", 1))
        rc, _ = self.fp("check")
        path = os.path.join(self.root, ".fixproof", "report.json")
        rep = self.report()
        i = [n for n, r in enumerate(rep["records"]) if r.get("label") == "after_repro"][0]
        for mutate in (lambda r: r.update(status="VERIFIED", exit_code=0),
                       lambda r: r["records"][i].update(outcome="pass"),
                       lambda r: r["records"][i].update(untrusted_stderr_tail="OK"),
                       lambda r: r["records"].pop(-1)):
            bad = json.loads(json.dumps(rep))
            mutate(bad)
            with open(path + ".bad", "w") as fh:
                json.dump(bad, fh)
            vrc, out = self.fp("validate", path + ".bad")
            self.assertEqual(vrc, 3, out)
            self.assertIn("integrity mismatch", out)
        RESULTS.append(("12 tampered report (4 mutations)", "UNVERIFIED", 3, "validate: integrity mismatch"))

    def test_13_restore_mismatch_detected(self):
        script = ("import os, sys\nimport glob\nif glob.glob('.fixproof/backup-*'):\n    open('sneaky.txt','w').write('x')\n"
                  "from calc import add\nsys.exit(0 if add(2,3)==5 else 1)\n")
        self.commit({"calc.py": BUGGY, "repro.py": script, "test_other.py": TEST_SUB})
        self.fp("init", "--repro", PY + " repro.py", "--suite", SUITE)
        write(self.root, "calc.py", FIXED)
        rc, out = self.fp("check")
        rep = self.report()
        RESULTS.append(("13 tree changed during revert", rep["status"], rc, rep["reasons"][0][:70]))
        self.assertEqual(rc, 5, out)
        with open(os.path.join(self.root, "calc.py")) as fh:
            self.assertEqual(fh.read(), FIXED)

    def test_14_timeout_during_revert_restores(self):
        script = ("import os, sys, time\nimport glob\nif glob.glob('.fixproof/backup-*'):\n    time.sleep(30)\n"
                  "from calc import add\nsys.exit(0 if add(2,3)==5 else 1)\n")
        self.commit({"calc.py": BUGGY, "repro.py": script, "test_other.py": TEST_SUB})
        self.fp("init", "--repro", PY + " repro.py", "--suite", SUITE, "--timeout", "3")
        write(self.root, "calc.py", FIXED)
        before = snapshot_bytes(self.root)
        rc, _ = self.fp("check")
        self.record("14 timeout during revert", rc, "PARTIALLY VERIFIED", 2)
        self.assertEqual(snapshot_bytes(self.root), before)

    def test_15_fix_and_test_same_file(self):
        inline = ("import sys\n\ndef add(a, b):\n    return a - b\n\nsys.exit(0 if add(2, 3) == 5 else 1)\n")
        self.commit({"test_inline.py": inline, "test_other.py": TEST_SUB, "calc.py": BUGGY})
        self.fp("init", "--repro", PY + " test_inline.py", "--suite", SUITE)
        write(self.root, "test_inline.py", inline.replace("a - b", "a + b"))
        rc, _ = self.fp("check")
        self.record("15 fix and test in same file", rc, "PARTIALLY VERIFIED", 2)

    def test_16_non_git_blocked(self):
        d = tempfile.mkdtemp(prefix="fixproof-nogit-")
        self.addCleanup(shutil.rmtree, d, True)
        p = subprocess.run([sys.executable, VERIFY, "init", "--repro", "echo hi", "--dir", d],
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT, cwd=d,
                           env=dict(os.environ, GIT_CEILING_DIRECTORIES=os.path.dirname(d)))
        RESULTS.append(("16 non-git project", "BLOCKED", p.returncode, "not a git repository"))
        self.assertEqual(p.returncode, 4)

    def test_17_usage_error(self):
        rc, _ = self.fp("init")
        self.assertEqual(rc, 64)


def tearDownModule():
    if RESULTS:
        print("\n%-42s %-20s %-5s %s" % ("scenario", "status", "exit", "first reason"))
        for r in sorted(RESULTS, key=lambda x: int(x[0].split()[0].rstrip("ab"))):
            print("%-42s %-20s %-5s %s" % r)


if __name__ == "__main__":
    unittest.main()
