# arXiv Submission Checklist

This file lists what's required before pressing submit on arxiv.org.
Task #12 (Wk 11: Submit arXiv preprint) consumes this checklist.

## Pre-submission gates

- [ ] **OSF pre-registration is live** — paste the OSF DOI into the
      "Pre-registered Hypotheses" section of the paper before submission.
      Currently the paper references `docs/plans/phase-1-osf-prereg.md`
      as a draft; the OSF version needs to be public and timestamped
      before the paper goes live so reviewers can verify the
      pre-registration predates the results.
- [ ] **Co-author commitment** — Wk 1 outreach went to 4 candidates
      (Lomonaco, Carta, Hayes, Luccioni). Confirm authorship list
      before arXiv submission. If solo: paper goes up under Paul Wu only.
      If co-authored: get authorship-order signoff in writing.
- [ ] **API key rotated** — the key `sk-ant-api03-1oaY...` was echoed
      to a session log during Wk 4-5 work; rotate at
      https://console.anthropic.com/settings/keys before publishing the
      repo URL.
- [ ] **Repo anonymization decision** — arXiv preprints are typically
      NOT double-blind, so the GitHub link to `wjlgatech/neuro-os` can
      stay non-anonymous for arXiv. For the ICLR 2027 submission later,
      mirror to `anonymous.4open.science` and update the paper's repo
      link.

## Final paper polish

- [ ] **Convert MD → PDF.** Use `pandoc arxiv_draft.md -o arxiv.pdf
      --pdf-engine=xelatex` (preferred) or upload to Overleaf and
      reformat as LaTeX. arXiv accepts PDF directly.
- [ ] **Insert one figure**: a system diagram of the 6-system comparison
      (B1-B5 + Ours_full_loop) with the closed-loop signal arrows for
      Ours. The paper currently has only tables; a figure helps
      readability and is conventional.
- [ ] **Verify citation accuracy** — the 13 references in §10 are
      abbreviated. Fill in BibTeX entries for the camera-ready.
- [ ] **Spell-check the entire draft.** Especially anglicization of
      "Bennett's S" and Greek letters (Δp, κ).
- [ ] **Re-read §9.1 (Limitations)** — make sure every limitation we
      acknowledge actually matches the published version of the paper.
      Do not hide flaws; do not invent new ones.
- [ ] **Verify the world-os demo runs.** `streamlit run world_os/app.py`
      must load without errors before the paper goes to arXiv. Take 3
      screenshots (Proposal Inbox, Accept/Reject Gate, Cross-rater Diff)
      and save to `world_os/assets/` for the LinkedIn / HN companion posts.

## arXiv submission form

1. Go to https://arxiv.org/submit
2. Category: `cs.LG` (primary), `cs.CL` (secondary)
3. Paste abstract from `abstract.txt` into the abstract field.
4. License: `arXiv non-exclusive` is fine; CC-BY is better for
      reuse/discoverability if comfortable.
5. Upload PDF + optional source files (LaTeX `.tex` if produced).
6. Author info: Paul Wu (independent), email, ORCID.
7. Comments field: include the companion repo link
   `https://github.com/wjlgatech/neuro-os` and the OSF pre-reg DOI.

## Post-submission

- [ ] **LinkedIn announcement** (per /goal-3 brand cadence, Day 13
      milestone). Lead with the headline finding: "Mechanism Survival
      vs Summary Fidelity: a new metric for AI-assisted research."
- [ ] **HN Show-HN draft** (per /goal-2 repo strategy). Time the post
      to coincide with arXiv being indexed (typically 2-3 days after
      submission).
- [ ] **Newsletter long-form** (per /goal-3): full walkthrough of the
      schema + the load-bearing self-review finding, 1500+ words.
- [ ] **Update `MEMORY.md`** to reflect that the arXiv preprint is
      live; mark `phase-1-mechanism-survival-paper` memory as
      "preprint submitted YYYY-MM-DD".

## What's NOT in scope for this submission

- ICLR 2027 polish (that's Wk 14-20, Task #23).
- Workshop tailoring (that's Wk 12-13, Task #22).
- N=200+ scale-up (that's a v2 paper).
- Real (non-synthetic) decision corpus (that's the ICLR submission
  expansion).

These are all flagged in `docs/plans/phase-1-mechanism-survival-paper.md`
as later milestones. The arXiv version is the wedge that establishes
the methodology and unlocks the downstream artifacts (repo launch,
brand content, co-author recruitment for Phase 3).
