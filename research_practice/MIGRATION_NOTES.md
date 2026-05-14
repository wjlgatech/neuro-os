# Migration: research-os → research_practice/

**Date:** 2026-05-14

## What happened

`research-os/` was previously a sibling project at
`/Users/jialiang.wu/Documents/Projects/research-os/`. It contained
Paul's personal paper-reading practice — operating principles in
`README.md`, the locked N=10 corpus in `PAPERS_MANIFEST.md`, PDFs in
`inbox/`, hand-written Layer 1 mechanism cards in `extracted/`, and
templates for Layer 2 synthesis and Layer 3 briefs.

The split between "research-os (sibling, personal practice)" and
"neuro-os (production system)" was always artificial: the 10 mechanism
cards existed in **both** places — `research-os/extracted/01_kirkpatrick.md`
AND `neuro-os/tests/fixtures/research/gold/01_kirkpatrick_ewc.json` —
two representations of the same intellectual work, manually kept in
sync. The position paper argues that **reading IS the schema**, but
the directory structure was contradicting it.

On 2026-05-14 the entire contents were moved into
`neuro-os/research_practice/` and the source directory removed (via
`mv`). All path references in code and documentation were updated.

## What's in here

- `README.md` — the original operating-principles doc (the "research-os" framing).
- `PAPERS_MANIFEST.md` — the locked N=10 corpus rationale and per-paper notes.
- `QUICK_START.md` — original onboarding doc.
- `download-starter-papers.sh` — the original 3-paper starter download script.
- `inbox/` — the 10 paper PDFs + their pdftotext `.txt` extractions.
- `extracted/` — the 10 hand-written Layer 1 mechanism cards (markdown).
- `synthesis/` — template for Layer 2 cross-paper synthesis (no content yet).
- `briefs/` — template for Layer 3 decision briefs (no content yet).
- `archive/` — empty placeholder for archived papers.

## What changed in code

- `experiments/phase_1/corpus.py` — `CORPUS_ROOT` now resolves to
  `<repo>/research_practice/inbox/` (was an absolute path to
  `Projects/research-os/inbox/`).
- `experiments/phase_1/extractors/base.py` — docstring updated.
- `world_os/data_loaders.py` — `PAPERS_DIR` now points to
  `<repo>/research_practice/inbox/` (was `<repo-parent>/research-os/inbox/`).

## What changed in docs

- Path mentions in `docs/plans/*.md`, `experiments/phase_1/README.md`,
  `experiments/phase_1/decisions/TODO_REAL_DATA.md`,
  `experiments/phase_1/paper/arxiv_draft.md`,
  `experiments/phase_1/results/findings.md`,
  `world_os/DESIGN_BRIEF.md`, `world_os/README.md` were updated to
  reference `research_practice/` instead of `research-os/`.
- Memory entries in `~/.claude/projects/-Users-jialiang-wu-Documents-Projects/memory/`
  that mention research-os should be updated lazily (read+write on
  next session that touches them); the *path* references are now wrong
  but the *content* about the project still applies.

## What did NOT change

References to "research-os" remain in these files **on purpose**,
because they describe a hypothetical sibling project as an API
consumer, NOT a path:

- `CHANGELOG.md` — historical change descriptions.
- `agent/belief_os.py` — docstring naming "research-os (hypothetical)"
  as a sample API consumer.
- `examples/07_belief_os_consumer.py` — sample code naming "research-os
  (hypothetical)" as the consuming module.
- `tests/test_belief_os_api.py` — test docstring.
- `ui/app.py` — UI copy that describes hypothetical consumers.

These can stay as written; the conceptual API consumer "research-os"
is independent of the actual personal-practice directory.

## The data-duplication issue (still open)

The 10 mechanism cards exist in BOTH:
- `research_practice/extracted/*.md` (human-readable markdown)
- `tests/fixtures/research/gold/*.json` (Pydantic-validated)

These are two representations of the same content. Resolving this to
a single source of truth is a bigger refactor; deferred. Options
when we revisit:

1. **Markdown as source.** A `make gold` target parses
   `extracted/*.md` into Pydantic JSON. Markdown is the human-edited
   surface; JSON is the derived artifact.
2. **JSON as source.** Renderer produces the markdown view on demand.
   Markdown becomes a derived artifact only useful for human review.
3. **Schema as the only source.** Drop the markdown; the schema
   provides a Pydantic-form view in the world-os UI. The Layer 1
   extraction template is replaced by the schema itself.

Recommendation: Option 3, paired with the world-os v1 upgrade to
Next.js (Q3 2026). The position paper's argument — that reading IS
the schema — pulls toward this.

## Verifying the move

Run:

```bash
# Confirm corpus loads
python3 -c "from experiments.phase_1.corpus import load_corpus; print(len(load_corpus()))"
# Should print: 10

# Confirm world-os UI data loaders work
python3 -c "
import sys
sys.path.insert(0, 'world_os')
import data_loaders
print('papers:', len(data_loaders.list_papers()))
print('paper text bytes (ewc):', len(data_loaders.load_paper_text('ewc-kirkpatrick-2017')))
"
# Should print: papers: 10 ; paper text bytes (ewc): 61148
```

Both checks pass as of 2026-05-14.
