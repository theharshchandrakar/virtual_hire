# 03 — Ontology

**Purpose:** Define the core nouns of the system — what they are, what makes two instances the same or different, and what states they move through.

**Depends on:** [02-assumptions.md](02-assumptions.md) (entity boundaries follow directly from the org/candidate/interview assumptions).
**Feeds into:** [04-invariants.md](04-invariants.md) (rules are stated in terms of these entities) and [05-data-model.md](05-data-model.md) (every entity here becomes a table).

---

## Design principle

Model only what v1 needs to operate. An entity earns a place here if the system must query, constrain, or transition it independently. If a concept can live as a field on another entity, it does not get its own primitive — see "Not a first-class entity" below.

## Core primitives

### Organization
The tenant boundary. Everything else in the system exists within exactly one Organization.
- **Identity:** system-generated ID. Two Organizations are never the same entity even if names collide (e.g., two different companies named "Acme").
- **Lifecycle:** `active` → `suspended` → `active` (billing/admin action) or `active` → `deactivated` (terminal, data retained per [08-privacy-and-compliance.md](08-privacy-and-compliance.md)).

### HRUser
A person acting on behalf of an Organization: HR generalist, recruiter, or hiring manager. (Interviewer is a role an HRUser can hold on a specific Interview, not a separate account type — see A3 in [02-assumptions.md](02-assumptions.md).)
- **Identity:** email address, unique within an Organization (per A2, one Organization per HRUser in v1).
- **Lifecycle:** `invited` → `active` → `deactivated`. Deactivated HRUsers are retained for audit-trail integrity (past scorecards/actions remain attributed) but cannot authenticate.

### JobRequisition
An open role an Organization is hiring for.
- **Identity:** system-generated ID, scoped to an Organization. Title + department is not identity — two requisitions can share a title.
- **Lifecycle:** `draft` → `open` → `on_hold` ⇄ `open` → `filled` | `cancelled` (terminal states).

### Candidate
A person who has submitted at least one Application to a specific Organization.
- **Identity:** system-generated ID, scoped to an Organization. Per A1/A8, Candidate identity is **not** shared across Organizations — the same human applying to two different Organizations on Sift produces two independent Candidate records. Within one Organization, email address is the practical dedup key.
- **Lifecycle:** `active` (has at least one live Application) → `archived` (no open Applications, retained per retention policy) → `deleted` (right-to-be-forgotten executed, see [08](08-privacy-and-compliance.md)).

### Resume
A single uploaded document representing one Candidate's work history, plus the structured data extracted from it.
- **Identity:** system-generated ID. A Resume is a distinct entity from the file bytes — re-parsing does not create a new Resume, it updates extracted fields on the same one.
- **Lifecycle:** `uploaded` → `parsing` → `parsed` | `parse_failed` (terminal-ish; can be retried, which returns it to `parsing`).

### Application
The join of a Candidate to a JobRequisition — "this person applied for this role." This is the entity the pipeline state machine operates on.
- **Identity:** system-generated ID. A given (Candidate, JobRequisition) pair should have at most one active Application — reapplication after rejection is a policy decision handled at the application layer (see [04-invariants.md](04-invariants.md)).
- **Lifecycle:** see full state diagram in [04-invariants.md](04-invariants.md) — `submitted` → `screening` → `interviewing` → `offer` → `hired`, with `rejected` and `withdrawn` reachable from most non-terminal states.

### Interview
A single interview session between one Interviewer and one Application's Candidate.
- **Identity:** system-generated ID. Per A12, a panel interview with three interviewers produces three Interview records, not one — each carries its own scheduling metadata and yields its own Scorecard.
- **Lifecycle:** `scheduled` → `completed` | `cancelled` | `no_show`.

### Interviewer
A role, not a separate account: an HRUser assigned to conduct a specific Interview. Modeled as the relationship between HRUser and Interview, not a standalone entity — see "Not first-class" below for the reasoning.

### Scorecard
The structured feedback record for one completed Interview.
- **Identity:** system-generated ID, 1:1 with the Interview it belongs to (per A12).
- **Lifecycle:** `draft` (interviewer is filling it in) → `submitted` (locked; see immutability invariant in [04](04-invariants.md)) → `amended` (a correction was made via the audit-trailed amendment process, original preserved).

## Entity-relationship diagram

```mermaid
erDiagram
    ORGANIZATION ||--o{ HRUSER : employs
    ORGANIZATION ||--o{ JOBREQUISITION : owns
    ORGANIZATION ||--o{ CANDIDATE : "scopes"

    JOBREQUISITION ||--o{ APPLICATION : receives
    CANDIDATE ||--o{ APPLICATION : submits
    CANDIDATE ||--o{ RESUME : owns

    APPLICATION }o--o| RESUME : "references (at submission time)"
    APPLICATION ||--o{ INTERVIEW : schedules

    HRUSER ||--o{ INTERVIEW : conducts
    INTERVIEW ||--o| SCORECARD : yields

    HRUSER ||--o{ JOBREQUISITION : "owns (recruiter/hiring manager)"
```

Notes on cardinality choices:
- `APPLICATION }o--o|  RESUME`: an Application references the Candidate's Resume at the time of submission (a Candidate can update their Resume between applications; each Application pins the version relevant to it via a resume snapshot reference, not a live pointer — this is stated as a data-model decision in [05-data-model.md](05-data-model.md)).
- `INTERVIEW ||--o| SCORECARD`: zero-or-one because a Scorecard doesn't exist until the interviewer submits it, but at most one per Interview.

## What is NOT a first-class entity in v1 (and why)

| Concept | Why it's not modeled separately |
|---|---|
| **Interviewer** | Fully represented by the (HRUser, Interview) relationship. No attributes exist that aren't either on HRUser (identity, role) or on Interview (which session, when). Promoting it to an entity would add a table with no independent lifecycle. |
| **Offer** | Out of scope per [01-problem-space-and-scope.md](01-problem-space-and-scope.md) — offer management is explicitly deferred to a potential v2+ ATS-adjacent feature. `Application.status = offer` is a state, not an entity with its own data (terms, approval chain, etc.). |
| **Employee** | The moment an Application reaches `hired`, the person leaves Sift's domain. No post-hire entity exists; that's HRIS territory. |
| **NotificationEvent** | Notifications (email on status change, interview scheduled, etc.) are modeled as side effects of state transitions in the architecture layer ([06-architecture.md](06-architecture.md)), not as a queryable domain entity in v1. If delivery auditing becomes a requirement, this may be promoted later. |
| **Department / Team** | JobRequisition carries a free-text department field in v1; a full org-chart entity is out of scope per A1 in [02-assumptions.md](02-assumptions.md). |
| **ConsentRecord** | Consent is captured as a timestamped field/event tied to Candidate and Resume submission (see [08-privacy-and-compliance.md](08-privacy-and-compliance.md)), not modeled as an independently queryable entity in v1 — reconsidered if audit requirements demand a full consent ledger. |

## Open Questions

- Should Resume be versioned explicitly (a Candidate can have multiple Resumes over time, each Application pins one) — the diagram assumes yes; confirm this matches how reapplication should behave.
- Does JobRequisition need an owner distinct from "any recruiter/hiring manager in the org can edit it," or is ownership assignment needed for permissions in v1?
- Is "one Application per (Candidate, JobRequisition) pair, ever" too strict — should a rejected Candidate be allowed to reapply to the same JobRequisition if it reopens later?
