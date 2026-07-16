# Contributing to Sift

**Depends on:** [CODE.md](CODE.md) (the story lifecycle this process wraps around) and the `VHIRE` Jira project (backlog/sprint source of truth).

This document covers the rules for getting a change merged. For what to do *within* a story (stub → approval → tests → implementation → approval), see [CODE.md](CODE.md) — this document governs everything from "code is ready" to "code is on `main`".

## Core rule

**No one pushes directly to `main`.** Every change — regardless of size — goes through a branch and a pull request. The Lead Architect (currently Kunal Gupte) is the only one who merges into `main`, and only after reviewing the PR in full. This applies to all collaborators, including the Lead Architect's own changes, which still go through a PR (self-merged only after the same review has actually happened).

## Branch naming convention

Branch off `main`, using this format:

```
<type>/<JIRA-KEY>-<short-kebab-case-description>
```

| Part | Rules |
|---|---|
| `type` | One of: `feature`, `fix`, `chore`, `docs`, `refactor`, `spike` |
| `JIRA-KEY` | The story/epic key from the `VHIRE` project (e.g. `VHIRE-6`). Omit only for work with no corresponding Jira item (e.g. a README fix) — use `docs/no-ticket-readme-fix` in that case. |
| description | 2–5 words, lowercase, hyphen-separated, describing the change — not the ticket title verbatim |

Examples:

```
feature/VHIRE-6-resume-parsing-agent
fix/VHIRE-11-scorecard-immutability-check
chore/VHIRE-14-bump-crewai
docs/vhire-1-readme-setup
```

## Pull request rules

- One story (or one small, tightly related set) per PR — matches [CODE.md](CODE.md)'s one-story-per-commit rule. Don't bundle unrelated stories to save review round-trips.
- PR description must reference the Jira key and summarize what changed and why (not just what — the "why" is what a reviewer without full context needs).
- Before opening a PR, the branch must pass the same local checks [CODE.md](CODE.md) requires before step 6's approval gate:
  ```
  .venv\Scripts\python.exe -m pytest
  .venv\Scripts\ruff.exe check app tests
  ```
  A PR opened with a failing check is not ready for review — fix first, then open.
- Force-pushes to a PR branch to address review feedback are fine; force-pushes to `main` are never acceptable from anyone.
- Draft PRs are welcome for early feedback but must be marked ready-for-review explicitly before the Lead Architect is expected to review them.

## Review and merge

- Only the Lead Architect merges to `main`. Other collaborators may review and comment, but merge authority is not delegated.
- The Lead Architect's review is a thorough review, not a rubber stamp — expect it to cover correctness against the story's contract, invariant compliance (see [docs/04-invariants.md](docs/04-invariants.md)), test coverage, and adherence to [CLAUDE.md](CLAUDE.md)'s house style, not just "does it run."
- Requested changes block merge until resolved — push follow-up commits to the same branch rather than opening a new PR.
- Squash-merge is the default merge strategy, so `main`'s history stays one commit per story; the Lead Architect may merge-commit instead if a PR is a deliberately-preserved multi-commit sequence.
- Delete the branch after merge.

## Open Questions

- Should PR review be required to come from someone other than the story's author once the team grows beyond the Lead Architect + one contributor, or does the Lead Architect remain the sole reviewer regardless of team size?
- Does this project want CI (automated `pytest`/`ruff` on PR open) wired up, or is the local pre-PR check sufficient given the team size? Revisit once GitHub Actions or equivalent is in scope.
