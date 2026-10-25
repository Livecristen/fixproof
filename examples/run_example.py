"""End-to-end demo: copy an example into a temp git repo, run init, apply the fix, run check.

Usage: python3 examples/run_example.py python|js-ts|ts
Exits with FixProof's exit code (0 = VERIFIED). The ts example: Tested with Node 22.18.0+ / 23.6.0+ / 24.x (unflagged type stripping); CI uses 24.22.1.
"""
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
VERIFY = os.path.join(os.path.dirname(HERE), "scripts", "verify.py")
PY = '"%s"' % sys.executable
CFG = {
    "python": {"bug": "slugify.py", "fixed": "slugify_fixed.py",
               "repro": PY + " -m unittest test_slugify", "suite": PY + " -m unittest test_other"},
    "js-ts": {"bug": "sum.js", "fixed": "sum_fixed.js",
              "repro": "node --test sum.test.js", "suite": "node --test empty.test.js"},
    # TypeScript via Node's built-in type stripping (no npm install).
    "ts": {"bug": "price.ts", "fixed": "price_fixed.ts",
           "repro": "node --test price.test.ts", "suite": "node --test zero.test.ts"},
}


def run(args, cwd):
    print("$ " + " ".join(args))
    return subprocess.call(args, cwd=cwd)


def main(name):
    cfg = CFG[name]
    tmp = tempfile.mkdtemp(prefix="fixproof-example-")
    try:
        for f in os.listdir(os.path.join(HERE, name)):
            if f != cfg["fixed"]:
                shutil.copy(os.path.join(HERE, name, f), tmp)
        for a in (["init", "-q"], ["config", "user.email", "demo@example.invalid"],
                  ["config", "user.name", "demo"], ["config", "core.autocrlf", "false"],
                  ["add", "-A"], ["commit", "-q", "-m", "buggy"]):
            subprocess.check_call(["git"] + a, cwd=tmp)
        rc = run([sys.executable, VERIFY, "init", "--repro", cfg["repro"], "--suite", cfg["suite"]], tmp)
        if rc != 0:
            return rc
        shutil.copy(os.path.join(HERE, name, cfg["fixed"]), os.path.join(tmp, cfg["bug"]))
        rc = run([sys.executable, VERIFY, "check"], tmp)
        if rc == 0:
            rc = run([sys.executable, VERIFY, "validate", os.path.join(".fixproof", "report.json")], tmp)
        return rc
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "python"))
