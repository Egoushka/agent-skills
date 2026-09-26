"""Tests for the skill linter's rules (spec errors vs authoring warnings)."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from common import Skill, load_skill  # noqa: E402
import validate  # noqa: E402


def codes(findings):
    return sorted({f["code"] for f in findings})


class FrontmatterRules(unittest.TestCase):
    def skill(self, directory: str, meta: dict, body: str = "Do the thing.\n") -> Skill:
        return Skill(Path(directory), meta, body)

    def test_valid_skill_is_clean(self):
        skill = self.skill("dev-references", {
            "name": "dev-references",
            "description": "Searches reference corpora. Use when the user wants a cited learning resource.",
            "metadata": {"version": "1.0"},
        })
        self.assertEqual(validate.check_frontmatter(skill), [])

    def test_spec_errors(self):
        skill = self.skill("x", {"name": "Bad--Name", "description": "d" * 1025, "metadata": {"version": 1.0}})
        errors = [f for f in validate.check_frontmatter(skill) if f["level"] == "error"]
        self.assertEqual(codes(errors), ["E002", "E003", "E005"])

    def test_reserved_words_and_angle_brackets(self):
        skill = self.skill("claude-helper", {"name": "claude-helper", "description": "Wraps <tags>. Use when needed."})
        self.assertEqual(codes(validate.check_frontmatter(skill)), ["E012", "E013"])

    def test_authoring_warnings(self):
        skill = self.skill("helper", {
            "name": "helper",
            "description": "I can help you with PDFs.",
            "allowed-tools": "Bash(npx:*) Read",
            "model": "fast",
        })
        self.assertEqual(codes(validate.check_frontmatter(skill)), ["W103", "W104", "W110", "W111"])


class BodyRules(unittest.TestCase):
    def test_links_inside_code_are_ignored_and_missing_files_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "demo"
            (root / "references").mkdir(parents=True)
            (root / "references" / "api.md").write_text("# API\n\nSee [more](deeper.md).\n", encoding="utf-8")
            (root / "SKILL.md").write_text(
                "---\nname: demo\ndescription: Demo. Use when testing.\n---\n"
                "Read [the API](references/api.md) and [this](missing.md).\n"
                "Format: `[title](url)`\n\n```\n[also](ignored.md)\n```\n",
                encoding="utf-8",
            )
            findings = validate.check_body(load_skill(root))
        messages = [f["message"] for f in findings]
        self.assertEqual(codes(findings), ["E008", "W109"])
        self.assertTrue(any("missing.md" in m for m in messages))
        self.assertFalse(any("url" in m or "ignored.md" in m for m in messages))

    def test_secret_scan(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "leaky"
            (root / "scripts").mkdir(parents=True)
            (root / "SKILL.md").write_text("---\nname: leaky\ndescription: x. Use when y.\n---\nok\n", encoding="utf-8")
            (root / "scripts" / "run.sh").write_text("TOKEN=ghp_" + "a" * 36 + "\n", encoding="utf-8")
            self.assertEqual(codes(validate.check_secrets(load_skill(root))), ["E009"])


class OverlapRule(unittest.TestCase):
    def test_similar_descriptions_warn_both_sides(self):
        a = Skill(Path("a"), {"description": "Designs landing pages and portfolios with strong visual taste and typography."}, "")
        b = Skill(Path("b"), {"description": "Designs portfolios and landing pages with visual taste, typography and motion."}, "")
        c = Skill(Path("c"), {"description": "Runs database migrations safely."}, "")
        result = validate.check_overlap([a, b, c])
        self.assertEqual(sorted(result), ["a", "b"])


if __name__ == "__main__":
    unittest.main()
