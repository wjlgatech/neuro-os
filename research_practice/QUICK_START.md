# Quick Start

You just unzipped the Research OS. Here's the 60-second orientation.

────────────────────────────────────────────────────────────────────

## What's in here

```
research-os/
├── README.md                       ← system prompt + operating principles
├── PAPERS_MANIFEST.md              ← starter papers, why each one, links
├── download-starter-papers.sh      ← one command grabs all three PDFs
├── inbox/                          ← raw PDFs go here
├── extracted/                      ← Layer 1 notes (one per paper)
│   └── _TEMPLATE.md                ← copy this for each paper
├── synthesis/                      ← Layer 2 cross-paper patterns
│   └── _TEMPLATE.md
├── briefs/                         ← Layer 3 decision-ready outputs
│   └── _TEMPLATE.md
└── archive/                        ← processed but no longer active
```

────────────────────────────────────────────────────────────────────

## First 5 Minutes

```bash
cd research-os
chmod +x download-starter-papers.sh
./download-starter-papers.sh
```

That puts three PDFs in `inbox/`:
1. Kirkpatrick — EWC
2. Ha & Schmidhuber — World Models
3. Pellegrini — Latent Replay

────────────────────────────────────────────────────────────────────

## Week 1 Plan

```
Day 1 (~2hr):  Read worldmodels.github.io interactive version, then the paper.
               Copy extracted/_TEMPLATE.md → extracted/01_ha_schmidhuber.md
               Fill it out. No jargon laundering.

Day 3 (~2hr):  Read Kirkpatrick EWC.
               Copy template → extracted/02_kirkpatrick.md. Fill it out.

Day 5 (~2hr):  Read Pellegrini Latent Replay.
               Copy template → extracted/03_pellegrini.md. Fill it out.

Day 7 (~2hr):  Copy synthesis/_TEMPLATE.md → synthesis/01_first_synthesis.md.
               Cluster the three by mechanism. Find recurring patterns and
               anti-patterns. Map the frontier.

               Then: copy briefs/_TEMPLATE.md → briefs/01_procore_oec_v1.md.
               Write one ProCore-specific brief. Concrete. Actionable.

Day 7 evening: Stop-condition check. Did the system work?
               If yes → scale. Add 2-4 papers from PAPERS_MANIFEST.md.
               If no → fix the system before adding inputs.
```

Total time: ~10 hours over 7 days.

────────────────────────────────────────────────────────────────────

## Using This With Claude

If you're using this as a Claude Project:

1. Create a new Project in claude.ai
2. Paste the contents of README.md as the Project Instructions
3. Drag the inbox/ PDFs into the Project knowledge base
4. Use the extracted/, synthesis/, briefs/ templates as starting prompts

The README is designed to function as both human documentation AND a system
prompt for Claude. Claude will then apply the same Layer 1 / 2 / 3 discipline
that you do.

────────────────────────────────────────────────────────────────────

## The One Rule

If you find yourself adding papers without processing them, you're in
survey-mode. Stop adding. Start processing.

Run the experiment. Report back.
