"""Tests for local patches on vendored skills: applied in order, and a stale one stops the run."""
from __future__ import annotations

import difflib
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import vendor  # noqa: E402

PATH = "skills/demo/SKILL.md"
ORIGINAL = "---\nname: demo\ndescription: Demo. Use when testing.\n---\nRead `../other/notes.md` first.\nThen use other-skill.\n"
STEP_ONE = ORIGINAL.replace("Read `../other/notes.md` first.", "Read the notes first.")
STEP_TWO = STEP_ONE.replace("Then use other-skill.", "Then carry on.")


def write_patch(directory: Path, name: str, old: str, new: str) -> Path:
    """A patch as the repo stores it: a line on why, then a diff in upstream paths."""
    diff = difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True), f"a/{PATH}", f"b/{PATH}")
    patch = directory / name
    patch.write_text(f"Drop a pointer to a skill the hub leaves out.\n\ndiff --git a/{PATH} b/{PATH}\n" + "".join(diff), encoding="utf-8")
    return patch


class LocalPatches(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.work, self.patches = root / "upstream", root / "patches"
        self.patches.mkdir()
        vendor.git("init", "--quiet", str(self.work))
        (self.work / PATH).parent.mkdir(parents=True)
        (self.work / PATH).write_text(ORIGINAL, encoding="utf-8")

    def tearDown(self):
        self.tmp.cleanup()

    def entry(self, *patches: Path) -> dict:
        return {"name": "demo", "repo": "someone/skills", "patches": [str(p) for p in patches]}

    def test_patches_apply_in_listed_order(self):
        # The second patch's context only exists after the first has applied.
        first = write_patch(self.patches, "1.patch", ORIGINAL, STEP_ONE)
        second = write_patch(self.patches, "2.patch", STEP_ONE, STEP_TWO)
        vendor.apply_patches(self.entry(first, second), "a" * 40, self.work)
        self.assertEqual((self.work / PATH).read_text(encoding="utf-8"), STEP_TWO)

    def test_patch_that_no_longer_applies_stops_the_run(self):
        stale = write_patch(self.patches, "stale.patch", STEP_ONE, STEP_TWO)
        with self.assertRaises(RuntimeError) as caught:
            vendor.apply_patches(self.entry(stale), "b" * 40, self.work)
        self.assertIn("stale.patch no longer applies to someone/skills@bbbbbbb", str(caught.exception))
        self.assertEqual((self.work / PATH).read_text(encoding="utf-8"), ORIGINAL)

    def test_entry_without_patches_is_untouched(self):
        vendor.apply_patches({"name": "demo", "repo": "someone/skills"}, "c" * 40, self.work)
        self.assertEqual((self.work / PATH).read_text(encoding="utf-8"), ORIGINAL)


if __name__ == "__main__":
    unittest.main()
