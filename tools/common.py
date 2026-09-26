"""Shared helpers for the repository tooling. Nothing here ships inside a skill."""
from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = ROOT / "skills"
VENDOR_FILE = ROOT / "vendor.json"
REPO_SLUG = "Egoushka/agent-skills"
FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?)\n---[ \t]*(?:\n|\Z)", re.S)
TEXT_SUFFIXES = {".md", ".txt", ".py", ".sh", ".js", ".ts", ".json", ".yaml", ".yml", ".toml", ".html", ".css", ""}


def estimate_tokens(text: str) -> int:
    """Rough token count (characters / 4). Good enough to compare skills, not to bill."""
    return (len(text) + 3) // 4


@dataclass
class Skill:
    path: Path
    meta: dict
    body: str
    error: str | None = None

    @property
    def name(self) -> str:
        return self.path.name

    @property
    def description(self) -> str:
        value = self.meta.get("description", "")
        return value.strip() if isinstance(value, str) else ""

    @property
    def body_lines(self) -> int:
        return len(self.body.strip("\n").splitlines())

    @property
    def metadata_tokens(self) -> int:
        # What every session pays for this skill before it is ever used.
        return estimate_tokens(f"{self.meta.get('name', '')}: {self.description}")

    @property
    def body_tokens(self) -> int:
        return estimate_tokens(self.body)

    def files(self) -> list[Path]:
        return sorted(p for p in self.path.rglob("*") if p.is_file() and "__pycache__" not in p.parts)


def load_skill(path: Path) -> Skill:
    text = (path / "SKILL.md").read_text(encoding="utf-8")
    match = FRONTMATTER.match(text)
    if not match:
        return Skill(path, {}, text, "SKILL.md has no YAML frontmatter")
    try:
        meta = yaml.safe_load(match.group(1)) or {}
    except yaml.YAMLError as exc:
        return Skill(path, {}, text[match.end():], f"frontmatter is not valid YAML: {exc}")
    if not isinstance(meta, dict):
        return Skill(path, {}, text[match.end():], "frontmatter must be a YAML mapping")
    return Skill(path, meta, text[match.end():])


def iter_skills() -> list[Skill]:
    return [load_skill(p) for p in sorted(SKILLS_DIR.iterdir()) if (p / "SKILL.md").is_file()]


def load_vendor() -> dict:
    return json.loads(VENDOR_FILE.read_text(encoding="utf-8"))


def vendored() -> dict[str, dict]:
    return {entry["name"]: entry for entry in load_vendor()["skills"]}


def save_vendor(config: dict) -> None:
    VENDOR_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git(*args: str, cwd: Path | None = None, check: bool = True) -> str:
    result = subprocess.run(["git", *args], cwd=cwd or ROOT, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)}: {result.stderr.strip() or result.stdout.strip()}")
    return result.stdout.strip()


def is_text(path: Path) -> bool:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return False
    try:
        path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return False
    return True
