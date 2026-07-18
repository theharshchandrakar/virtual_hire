# Claude Code — Project Context & Token Optimization Bootstrap

Paste this once per project (or save as `.claude/commands/optimize-context.md` and invoke as `/optimize-context`). It builds a persistent, low-token context layer and installs operating rules Claude Code must follow for the rest of the engagement.

---

## PROMPT

You are bootstrapping a **persistent, token-efficient context layer** for this codebase. This is a one-time setup pass that will pay off across every future session. Work in this order. Do not skip steps to save time now — the whole point is to save 10x more tokens later.

### 0. Reconnaissance (cheap, do first)

- Run `git log --oneline -20`, `git status`, `git diff --stat HEAD~5` to understand recent activity.
- Run `find . -type f -name "*.{ts,tsx,js,py,go,java,rs}" | wc -l` (adjust extensions) and get a rough size/complexity read before deciding how deep to go on indexing.
- Detect the primary language(s), package manager, monorepo vs single-repo, and test framework.
- Check for an existing `.claude/` or `CLAUDE.md` — if present, treat as authoritative and merge, don't overwrite blindly.

### 1. Create the context scaffold

Create a `.claude/context/` directory with these files. Keep every file **terse and structured** — this is machine-referenced context, not prose documentation.

```
.claude/
├── CLAUDE.md                  # always-loaded root memory (see §2)
├── context/
│   ├── project-map.md         # directory/module purpose map
│   ├── symbol-index.json      # AST-derived symbol table
│   ├── dependency-matrix.md   # who-imports/calls-whom
│   ├── object-map.md          # data models, schemas, entity relations
│   ├── decisions.md           # short ADRs — why, not what
│   └── session-log.md         # rolling append-only summaries, capped
```

### 2. `CLAUDE.md` (root, always loaded — keep under ~200 lines)

Include only what must be true for EVERY session:
- One-paragraph project purpose + architecture style (monolith/microservices/etc.)
- Tech stack + versions that matter (not a full package.json dump)
- Directory map at depth 1-2 only, with one-line purpose per folder
- Non-obvious conventions (naming, error handling patterns, auth model)
- Explicit pointer: "For symbols → `context/symbol-index.json`. For dependencies → `context/dependency-matrix.md`. For data model → `context/object-map.md`. Do not re-derive these by reading source — query the index first."
- A "DO NOT" list: files/dirs never to read in full (generated code, vendored deps, lockfiles, build output).

### 3. Build `symbol-index.json` via AST, not full-file reads

Use the language's real parser — don't eyeball files token-by-token:
- JS/TS: `ts-morph` or `typescript` compiler API, or `tree-sitter-typescript`
- Python: `ast` module (stdlib) or `tree-sitter-python`
- Go: `go/ast` + `go/parser`
- Multi-language fallback: `tree-sitter` with per-language grammars, or `ctags -R --fields=+n` as a fast baseline if a full AST pass isn't worth the setup cost for this repo's size

For each function/class/interface/type, extract:
```json
{
  "name": "processRoyaltyBatch",
  "kind": "function",
  "file": "src/pipeline/reconcile.py",
  "lines": [142, 198],
  "signature": "processRoyaltyBatch(batch: RoyaltyBatch, tolerance: float) -> ReconResult",
  "calls": ["fetchCatalog", "normalizeIsrc"],
  "called_by": ["run_pipeline"],
  "doc": "one-line purpose, extracted from docstring/comment if present"
}
```
Write a small script (`.claude/scripts/build-symbol-index.{py,ts}`) that does this and can be **re-run incrementally** — hash each source file (mtime + size or content hash), only re-parse files whose hash changed since the last index build. Store hashes in `.claude/context/.index-cache.json`.

### 4. Build `dependency-matrix.md`

From the same AST pass, derive a module-level (not symbol-level) adjacency map:
- Which files/modules import which others
- Fan-in/fan-out counts per module (flags god-modules and risky change surfaces)
- Render as a compact table, not a graph diagram (tables are far cheaper to re-inject into context than SVG/mermaid for this purpose):

```
| Module              | Imports              | Imported By                  | Fan-in | Fan-out |
|---------------------|-----------------------|-------------------------------|--------|---------|
| pipeline/reconcile  | catalog, isrc_utils  | run_pipeline, cli/audit       | 2      | 2       |
```

### 5. Build `object-map.md`

For data-model-heavy code (DB models, DTOs, API schemas, class hierarchies):
- List each entity: fields, types, relationships (1:1, 1:N, N:N), and which modules read/write it
- If an ORM is present (SQLAlchemy, Prisma, GORM, etc.), parse the schema directly rather than re-deriving from usage
- Note inheritance/interface implementation chains explicitly — this is the #1 thing that causes redundant file reads later

### 6. Operating rules — install these as standing instructions in `CLAUDE.md`

```markdown
## Context & Token Discipline (read before every task)

1. NEVER read a full file if `symbol-index.json` + a targeted `rg`/`grep` on the
   specific symbol answers the question. Full-file reads are last resort.
2. Before touching any file, run `git status` and `git diff <file>` — only
   review changed hunks, not the whole file, unless the file is new or the
   diff shows the change is structural (rename, large refactor).
3. After any multi-file change, regenerate ONLY the affected entries in
   symbol-index.json / dependency-matrix.md (re-run the incremental build
   script, scoped to changed files via the hash cache) — not a full rebuild.
4. At the end of a session, append a 3-5 line summary to `session-log.md`:
   what changed, why, what's still open. Prune session-log.md to the last
   20 entries — older context should live in git history + decisions.md,
   not in active memory.
5. For any "how does X work" question, check symbol-index.json's `calls`/
   `called_by` fields before opening source files to trace call chains.
6. Prefer `rg -n "pattern" --type <lang>` over reading directories file by
   file when searching for usage.
7. Batch related reads/edits in one turn rather than sequential
   read-think-read cycles when the files are already known from the index.
8. Treat `context/decisions.md` as the place for "why we did it this way" —
   don't re-derive rationale from commit archaeology if it's already logged.
```

### 7. Git diff strategy specifics

Add a small helper script `.claude/scripts/smart-diff.sh`:
```bash
#!/usr/bin/env bash
# Usage: smart-diff.sh <file-or-empty>
# Shows only changed hunks with 2 lines of context, not full file
if [ -z "$1" ]; then
  git diff --stat HEAD
else
  git diff -U2 HEAD -- "$1"
fi
```
Instruct Claude Code to prefer this over `cat`/full `view` on any file that already exists in git history and has uncommitted or recent changes.

### 8. Output of this bootstrap pass

When done, report back:
- File/symbol counts indexed
- Any modules with unusually high fan-in/fan-out (candidates for careful review)
- Any gaps (languages/files the AST parser couldn't handle — fall back to ctags or manual notes for those)
- Confirm `CLAUDE.md` is under ~200 lines and everything else is offloaded to `context/`

Do not proceed to any feature work in this same pass — this is infrastructure only. Stop after the report.
