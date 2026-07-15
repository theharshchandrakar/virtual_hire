# 09 — Roadmap

**Purpose:** Phase the build so scope commitments are explicit and sequenced, mapped directly to the in-scope/out-of-scope decisions already made.

**Depends on:** [01-problem-space-and-scope.md](01-problem-space-and-scope.md) (phases are this doc's scope table, sequenced) and [08-privacy-and-compliance.md](08-privacy-and-compliance.md) (compliance sign-off gates phase exits).
**Feeds into:** Nothing downstream — this is the terminal document; it is the one most expected to be revised as reality intervenes.

---

## Phase overview

| Phase | Theme | Ships | Does NOT ship |
|---|---|---|---|
| v1 | Prove the core record: intake → pipeline → structured feedback, plus RAG-based search over it | Resume intake (web + email-in), parsing via the LLM crew's Extraction Agent, fixed application pipeline, interview scheduling metadata, structured scorecards, on-demand candidate summary (Summarizer Agent), HR-initiated RAG search & match rationale (vector index + Reasoning Agent), single-org-scoped auth, consent + deletion flow covering embeddings | Any item from the Scope Creep Watchlist in [01-problem-space-and-scope.md](01-problem-space-and-scope.md), including autonomous/background candidate ranking; calendar-native scheduling; ATS integration; candidate self-service portal |
| v2 | Reduce integration friction, add pipeline analytics | One-way ATS export, calendar integration (read availability, write scheduled events), requisition-level funnel analytics dashboard, configurable scorecard competency templates per requisition (already in data model, exposed in UI), stage *renaming* (not restructuring) | Bi-directional ATS sync, AI ranking, video/audio capture, custom pipeline stages beyond renaming |
| v3 | Evaluate expansion based on validated demand | Candidate self-service portal (if repeat-application volume justifies it, per Open Question in [00-ideation.md](00-ideation.md)); opt-in advisory analytics (e.g., flagging incomplete scorecards, pipeline bottlenecks) — explicitly **not** candidate ranking; deeper multi-language parsing support if A5's English/PDF assumption proves too narrow | Full ATS replacement, offer/e-signature management, native sourcing — none of these are planned even in v3 without a separate scoping exercise, since they represent fundamentally different products |

## Exit criteria per phase

**v1 → v2** requires all of:
- Success criteria from [00-ideation.md](00-ideation.md) trending toward target with at least one pilot organization (≥90% resumes without manual re-keying, ≥80% decisions with complete scorecards, ≥50% of RAG searches acted on).
- Zero cross-tenant data isolation incidents (I2 **and I11** test suites green on every deploy, no exceptions found in pilot usage — the Qdrant collection-per-organization cross-tenant test is treated with the same release-blocker severity as the Postgres RLS test, per [04-invariants.md](04-invariants.md)'s 2026-07-15 revision).
- The three highest-confidence Open Unknowns from [02-assumptions.md](02-assumptions.md) validated with real pilot data (pipeline shape fit, resume format distribution, scorecard competency field adequacy), plus the embedding-quality unknown (A16) validated against real search usage.
- **[NEEDS LEGAL REVIEW]** items in [08-privacy-and-compliance.md](08-privacy-and-compliance.md) resolved for at least the jurisdiction(s) the pilot organizations operate in, including the third-party AI subprocessor DPAs.

**v2 → v3** requires all of:
- At least one organization actively using ATS export and calendar integration without support-escalation-level friction.
- Funnel analytics adopted (viewed regularly, not just available) by pilot organizations, establishing that deeper analytics investment in v3 has a real audience.
- A specific, named organization request substantiates each v3 feature before it's built — per the Scope Creep Watchlist's "what would need to be true" conditions, not built speculatively.

## Timeline

```mermaid
gantt
    title Sift Build Roadmap
    dateFormat  YYYY-MM-DD
    axisFormat  %b %Y

    section v1 - Core Record
    Data model + FastAPI core        :v1a, 2026-08-01, 45d
    Ingestion + Extraction Agent parsing :v1b, after v1a, 30d
    Pipeline + scorecards UI         :v1c, after v1a, 45d
    Qdrant collection provisioning + embedding pipeline :v1e, after v1b, 25d
    LLM crew - Summarizer + Reasoning Agents :v1f, after v1e, 30d
    RAG search UI                    :v1g, after v1f, 20d
    Multi-tenancy hardening + I2/I11 test suites (Postgres RLS + Qdrant collection isolation) :v1d, after v1f, 20d
    Pilot org onboarding             :milestone, after v1g, 0d

    section v2 - Integrations & Analytics
    Legal review resolution incl. AI subprocessor DPAs (gating) :v2a, after v1d, 30d
    Calendar integration             :v2b, after v2a, 30d
    ATS one-way export               :v2c, after v2a, 25d
    Funnel analytics dashboard       :v2d, after v2b, 30d
    v2 GA                            :milestone, after v2d, 0d

    section v3 - Evaluate Expansion
    Validate v3 candidates against exit criteria :v3a, after v2d, 30d
    Build validated v3 features only :v3b, after v3a, 60d
```

## Open Questions

- Should v1's pilot phase be time-boxed (e.g., fixed 8 weeks) or milestone-boxed (proceeds to v2 only when exit criteria are met, regardless of elapsed time) — the exit-criteria framing above implies the latter, confirm this is the intended operating model.
- Which specific organization(s) will serve as v1 design partners, and does their profile match the target org-size assumptions (A14) closely enough to validate them meaningfully?
- If a v2/v3 exit criterion is never met (e.g., no organization ever requests a specific v3 feature), is the plan to simply not build it indefinitely, or is there a re-evaluation trigger (e.g., annual scope review)?
- The v1 timeline now includes the embedding pipeline and multi-model LLM crew as sequential dependencies before pilot onboarding — should RAG search instead ship as a fast-follow shortly after a leaner v1 pilot (core record only), to de-risk the pilot timeline from AI-pipeline build risk?
