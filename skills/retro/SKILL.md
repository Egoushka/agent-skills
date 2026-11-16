---
name: retro
description: Looks back at the current session for work a tool should do, friction to remove and preferences the user had to state, then prints at most 3 proposals with evidence. Use when the user says "retro", "what should we automate", "what tools do we need", "lessons", "what did you learn", and before a handoff after 30 or more tool calls. Not for a team or sprint retrospective.
license: MIT
compatibility: Works from the session's own tool calls and messages. Searching other sessions needs a transcript-search tool, which is optional.
metadata:
  author: Yehor Hrabovskyi
  version: "0.1.0"
  category: workflow
---

# Retro

Turns what this session did into proposals for the setup: a tool, a rule, a check or a fix. Why it exists: in an audit of past sessions, the agent offered a new tool unprompted in about 1% of them, while the same scratch scripts were rewritten again and again (one PR-body file in 12 sessions, one probe script in 6). Where tools did exist, they ran in 0-30% of the sessions that needed them. Agents repeat work and do not notice; this skill makes them look.

## Evidence comes from the record

Use what this session's tool calls and the user's messages show, never your impression of how it went:
- **Procedures.** The same multi-step sequence run twice or more, e.g. three raw ssh reads of one host, or PR create, wait, merge.
- **Scripts.** Scratch scripts you wrote to a temp folder or the scratchpad.
- **Failures.** Errors, retries and guessed paths.
- **The user's words.** The corrections they typed, quoted verbatim in 15 words or fewer, and their interrupts.

Then check whether it recurs beyond this session. If a transcript-search tool is available, search other sessions for a script name, a command or a phrase the user used. A tool needs the procedure in 3 or more sessions. A rule needs the correction in 2 or more, or an explicit "from now on / always / never". Without a search tool, say "other sessions: not checked" and keep the proposal to what this session proves.

## Check what exists first

Before proposing, look for something that already does it:
- the installed skills folders (user-level and project-level);
- the repo's `scripts/`, `Makefile`, `package.json` scripts and CLAUDE.md or AGENTS.md;
- any backlog or issue list the project keeps for tooling work, for items already open.

If the tool exists and went unused, propose its trigger instead of a new tool: a line in the instructions file of the repo where the work happens, or a hint hook. That is the more common gap.

## Output

At most 3 proposals, most valuable first, in exactly this block (a fixed shape lets a later job read it back from transcripts):

```
=== retro ===
- kind: tool | trigger | rule | check | fix
  what: <one line>
  evidence: <this session: counts, or the quote> · <other sessions: N, from the transcript search>
  where: <file or repo it lives in> · trigger: <what makes the agent use it>
  exists: <nearest existing tool or rule, or none>
  retire: <when to remove it, e.g. 0 uses in 30 days>
=== end ===
```

If nothing clears the thresholds, print the block with `- none` and one line on why. A weak proposal is worse than none.

## Kinds

- **tool**: a script, CLI subcommand, skill or subagent. Only for a procedure seen in 3 or more sessions. A new skill passes a with/without comparison on a few real prompts before it is installed.
- **trigger**: routing to something that exists. A hint when the raw form runs, or an instructions-file line where the work happens.
- **rule**: a preference the user stated. Name the file:
  - the user-level instructions file for every session;
  - the repo's CLAUDE.md, AGENTS.md or rules folder for one repo.

  Quote their words.
- **check**: a written rule broken again in this session. Make it a hook or a CI check, and replay it against past sessions before it goes live, so it does not block legitimate work.
- **fix**: one change that removes a failure you hit, such as a config line, a missing tool or a wrong path in a doc.

## Then

Don't build here unless the user asks. When they say "go ahead", build the first proposal the way the project builds everything else: its own branch and pull request, with the trigger included. Rules go into the source file, never into a generated copy.

Keep employer or customer details out of a public repo: if the session touched private work, the proposals stay in the chat and in that work's own files.
