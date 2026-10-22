"""HACS reads repository metadata as UTF-8 before it can install a release."""
from pathlib import Path
import subprocess
import unittest


class EncodingTests(unittest.TestCase):
    def test_tracked_text_files_are_utf8(self):
        root = Path(__file__).resolve().parents[1]
        names = subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=root
        ).decode("utf-8").split("\0")
        for name in filter(None, names):
            path = root / name
            if path.suffix.lower() in {".md", ".py", ".json", ".yml", ".yaml", ".txt"} or path.name == ".gitignore":
                with self.subTest(file=name):
                    path.read_bytes().decode("utf-8")
