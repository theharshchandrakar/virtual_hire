# Backend Implementation Plan

**Purpose:** A working plan for taking the backend from its current state to v1-complete, following [EPIC.md](EPIC.md)'s epic breakdown, the Jira `VHIRE` backlog, and the [CODE.md](CODE.md)/[CONTRIBUTING.md](CONTRIBUTING.md) workflow. This is a living doc — update it as epics land or sequencing changes, don't let it go stale.

---

## 1. Where things actually stand (as of 2026-07-17)

Three branches matter right now, and they don't all agree with each other:

| Branch | State | Contains |
|---|---|---|
| `main` (local) | 1 commit **behind** `origin/main` | Missing the merged E1/E2 work — needs a pull. |
| `origin/main` | Source of truth | E1 + E2 fully merged (PR #3). Does **not** yet have the proctoring/verdict pivot docs. |
| `docs/vhire-pivot-proctoring-transcript-scoring` (current branch) | Branched **before** PR #3 merged | Has the new docs + EPIC.md pivot, but is missing E1/E2's actual code (models, auth, deps, migrations). |
| `feature/VHIRE-12-org-qdrant-provisioning` | Open **draft** PR #4, WIP/stub only | Partial E3 (org create + Qdrant provisioning) — explicitly marked stub, not implementation-complete. |

**Jira (`VHIRE` project) backlog reality:**

| Epic | Jira status | Notes |
|---|---|---|
| E1 Data Layer, E2 Auth/Tenant Context | ✅ Done (VHIRE-1–10) | Merged to `origin/main`. |
| E3 Org/HR User/Requisition API | 🟡 To Do — VHIRE-12 has a draft stub PR open | VHIRE-24 (HR invite + req CRUD), VHIRE-25 (org deactivation/teardown) not started. |
| E4 Ingestion, E5 Task Queue, E6 Parsing, E7 Embedding | 🔲 To Do (VHIRE-13–23 exist) | No code started. |
| E8–E14 (pipeline/scorecards, crew, RAG, notifications, privacy, test suite, observability) | ⚪ **No Jira tickets yet** | Only exist as epics in EPIC.md. |
| E15–E21 (verdict data model, scoring engine, OpenRouter/Judge, resume/transcript/proctoring verdicts) | ⚪ **No Jira tickets yet** | Added in the 2026-07-16 docs pivot; never synced to Jira per [CLAUDE.md](CLAUDE.md)'s own log. |

**Bottom line:** the two "already done" epics live on `origin/main`, not on this branch. Nothing here is contradictory or broken — it's just three legitimate branches that haven't been reconciled yet.

---

## 2. Housekeeping before writing implementation code

Do these in order, each is quick:

1. **Fast-forward local `main`** to `origin/main` (E1/E2 merge).
2. **Land the docs pivot**: open a PR for `docs/vhire-pivot-proctoring-transcript-scoring` against `main` and merge it (docs-only, no conflicts expected against E1/E2's code since those changes don't touch `/docs` or `EPIC.md`). Do this *before* starting new feature branches so everyone builds on top of one `main`.
3. **Decide on the WIP E3 draft PR (#4)**: either continue it to completion as VHIRE-12's real implementation, or close it and redo VHIRE-12 clean per the CODE.md stub→approval→implement flow. Recommend continuing it rather than discarding — it already scoped the provisioning approach.
4. **Sync Jira for E8–E21**: create the missing epics/stories in `VHIRE` (mirroring the VHIRE-1…25 pattern already established) so step 1 of CODE.md ("pick the next backlog item") has something to pick for anything past E7. This can happen incrementally — no need to pre-create all of it before starting E3/E4/E5.

---

## 3. Build order

Following EPIC.md's dependency graph, grouped into sequential phases. Epics inside the same phase have no dependency on each other and can be worked in parallel (different branches/PRs, one story per PR per CONTRIBUTING.md).

| Phase | Epics | Why this grouping |
|---|---|---|
| **Done** | E1, E2 | Foundation — everything else needs org/tenant context. |
| **Phase A** | E3 (finish), E5 | Org API unblocks ingestion; task queue has no dependency on E3 beyond E1/E4, can start in parallel. |
| **Phase B** | E4 | Needs E3 (requisitions to attach to). |
| **Phase C** | E6, E7, E8 | E6/E7 (parsing → embedding) and E8 (pipeline/scorecards) share no data dependency — genuinely parallel tracks. |
| **Phase D** | E9, E11 | E9 (summarization) needs E7+E8; E11 (notifications) needs E5+E8 — independent of each other. |
| **Phase E** | E10 | Needs E7+E9 (shared crew scaffolding). |
| **Phase F** | E15, E16 | New verdict-service schema + deterministic Scoring Engine — only depends on E1, can actually start as early as Phase A if capacity allows. |
| **Phase G** | E17 | OpenRouter gateway + Judge agent — needs E9 (crew to extend) and E16. |
| **Phase H** | E18, E19 | Resume Analyzer verdict (needs E6/E16/E17); transcript/assignment ingestion API (needs E15/E3/E8) — parallel. |
| **Phase I** | E20, E21 (code only) | Transcript+assignment verdict; proctoring build-out. E21's code can be built here, but **is not launch-ready** until legal sign-off per org/jurisdiction (see §5). |
| **Phase J** | E12, E13, E14 | Privacy/deletion, multi-tenancy test-suite gate, observability — these close out the release and depend on nearly everything above. E13 is a **hard CI gate**; nothing ships to pilot without it green. |

Note: E15/E16 don't have to wait for E8/E9/E10 to finish — if there's parallel capacity, pulling them into Phase C/D alongside the RAG track shortens the critical path to the verdict services. Sequenced later above only to match the more conservative "finish core pipeline first" reading of EPIC.md's own phase table.

---

## 4. Per-story workflow (unchanged, just a pointer)

Every story still follows [CODE.md](CODE.md)'s 7 steps and [CONTRIBUTING.md](CONTRIBUTING.md)'s branch/PR rules — nothing new here, this plan is just the backlog ordering:

`pick VHIRE story → stub w/ docstrings → human approval → tests (if warranted) → implement + pass tests → human approval → branch push + PR → Lead Architect merge`

Branch naming: `feature/VHIRE-<n>-<slug>` (matches what's already in use). One story, one PR.

---

## 5. Blockers to flag now, not mid-sprint

Carried forward from EPIC.md's cross-cutting risk table — these aren't engineering tasks, they need a decision/owner from outside this backlog:

| Blocker | Blocks | Owner needed |
|---|---|---|
| Verdict/Judge model choice (200–300B class, via OpenRouter) | E17 → E18/E20/E21 | Product/eng decision |
| Video platform integration target (Zoom/Meet/Teams) | E19, E21 | Product decision |
| Proctoring signal-detection vendor + DPA | E21 | Vendor selection, legal |
| STT fallback vendor (if no platform transcript) | E19 | Vendor selection |
| Biometric data / two-party consent legal review | E21 **launch** (not code) | Legal — likely multi-month, start this in parallel now |
| Scoring Engine rubric disparate-impact review | E16/E18/E20 | Confirm with product owner whether this is in scope for pilot launch |

None of these block *starting* E15/E16 (schema + deterministic rules are vendor-agnostic) — but they do block finishing E17/E19/E21's actual integration code, so surface them to whoever owns those decisions now.

---

## 6. Immediate next action

Recommend: do the housekeeping in §2, then start Phase A — finish VHIRE-12 (E3's Qdrant provisioning stub → real implementation) since it's already mid-flight, followed by VHIRE-24/25 to close out E3, while E5 (VHIRE-13–15) proceeds in parallel on a second branch.
