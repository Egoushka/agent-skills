# Contributing

Suggestions for skills and corpora are welcome as issues. This is a personal, curated set, so a new skill needs to earn its always-on context cost.

Before opening a pull request:

1. Read [docs/authoring.md](docs/authoring.md). `make check` enforces most of it.
2. For a new skill, add trigger cases to `evals/<skill>.json`, covering both prompts that should fire it and prompts that should not.
3. Run `make check catalog` and commit the regenerated README block.
4. Use conventional commit messages (`feat(skill): …`, `fix(refs): …`, `chore(vendor): …`); they become the activity feed on the catalog site.

Vendored skills are never edited here. Fix them upstream, and the weekly sync brings the fix back.
