"""Stdlib-only import check and wording check for the docs."""
import ast
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ALLOWED = {"argparse", "datetime", "fnmatch", "hashlib", "json", "os", "re", "shutil",
           "shlex", "signal", "subprocess", "sys", "tempfile", "time"}


class Meta(unittest.TestCase):
    def test_stdlib_only(self):
        tree = ast.parse(open(os.path.join(ROOT, "scripts", "verify.py"), encoding="utf-8").read())
        mods = set()
        for n in ast.walk(tree):
            if isinstance(n, ast.Import):
                mods |= {a.name.split(".")[0] for a in n.names}
            elif isinstance(n, ast.ImportFrom):
                mods.add((n.module or "").split(".")[0])
        self.assertTrue(mods <= ALLOWED, mods - ALLOWED)
        if hasattr(sys, "stdlib_module_names"):
            self.assertTrue(mods <= set(sys.stdlib_module_names), mods - set(sys.stdlib_module_names))

    def test_no_banned_claims(self):
        docs = [f for f in os.listdir(ROOT) if f.endswith(".md")]
        for d, _, files in os.walk(os.path.join(ROOT, "examples")):
            docs += [os.path.relpath(os.path.join(d, f), ROOT) for f in files if f.endswith(".md")]
        bad = re.compile(r"\b(first|only|unforgeable)\b", re.I)
        for f in docs:
            text = open(os.path.join(ROOT, f), encoding="utf-8").read()
            self.assertIsNone(bad.search(text), "%s: %s" % (f, bad.findall(text)))


if __name__ == "__main__":
    unittest.main()
