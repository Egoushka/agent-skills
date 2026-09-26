# 0002: Vendor and pin community skills

- Status: accepted
- Date: 2026-09-27

## Context

A skill is both text that steers the agent and, often, code it runs. Snyk's February 2026 [ToxicSkills study](https://snyk.io/blog/toxicskills-malicious-ai-agent-skills-clawhub/) scanned 3,984 public skills. It found security flaws in 1,467 of them (36%) and confirmed malicious payloads in 76. Installing straight from a community repository's default branch means taking whatever it contains the next time anyone runs `npx skills update`.

## Decision

- **Community skills are vendored.** `vendor.json` records the repository, the path, a pinned commit and the license. `tools/vendor.py` copies the skill byte-for-byte at that commit, together with its upstream `LICENSE`. CI's `vendor.py verify` fails on any local modification.
- **Updates are pull requests.** A weekly workflow moves pins to upstream HEAD and opens one PR whose report lists changed files, token deltas and SKILL.md diffs. It flags changed `allowed-tools`, added or changed scripts, new URLs and description changes.
- **Curate, don't mirror.** Only the skill that earns its context is vendored; for example, one of taste-skill's thirteen overlapping skills. Each entry says why in its `why` field, and the catalog shows it.
- **First-party marketplaces are installed from source.** Publisher-maintained sets such as [dotnet/skills](https://github.com/dotnet/skills) (Microsoft) and [anthropics/skills](https://github.com/anthropics/skills) are trusted at the publisher level and change often, so they are installed through their own marketplaces instead of being copied here.

## Consequences

- A weekly review chore, which is also the point: every change is seen once.
- Upstream fixes arrive at most a week late unless the workflow is run by hand.
- Pull requests opened with `GITHUB_TOKEN` don't trigger other workflows. The sync job therefore appends validation output to the PR body, and a `SYNC_TOKEN` secret (a fine-grained PAT) makes CI run on those PRs as well.
