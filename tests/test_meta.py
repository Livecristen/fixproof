"""Stdlib-only import check and wording check for the docs."""
import ast
import json
import os
import re
import subprocess
import sys
import tempfile
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

    def test_version_file_matches_cli(self):
        with open(os.path.join(ROOT, "VERSION"), encoding="utf-8") as fh:
            ver = fh.read().strip()
        src = open(os.path.join(ROOT, "scripts", "verify.py"), encoding="utf-8").read()
        self.assertIn('VERSION = "%s"' % ver, src)

    def test_readme_example_report_validates(self):
        """The README sample is a real report: validate recomputes VERIFIED."""
        with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as fh:
            text = fh.read()
        marker = "<!-- example-report-start -->"
        end = "<!-- example-report-end -->"
        self.assertIn(marker, text)
        self.assertIn(end, text)
        chunk = text.split(marker, 1)[1].split(end, 1)[0]
        start = chunk.index("```json\n") + len("```json\n")
        body = chunk[start:chunk.index("\n```", start)]
        rep = json.loads(body)
        self.assertEqual(rep["tool"], "fixproof")
        self.assertEqual(rep["version"], "0.3.0")
        self.assertEqual(rep["status"], "VERIFIED")
        self.assertEqual(rep["exit_code"], 0)
        for needle in ("/tmp/", "/home/", "/usr/", "/Users/"):
            self.assertNotIn(needle, body)
        fd, path = tempfile.mkstemp(suffix=".json")
        os.close(fd)
        try:
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(body)
            proc = subprocess.run(
                [sys.executable, os.path.join(ROOT, "scripts", "verify.py"), "validate", path],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            self.assertEqual(proc.returncode, 0, proc.stdout.decode())
            self.assertIn(b"status VERIFIED", proc.stdout)
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
