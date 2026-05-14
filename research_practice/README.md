# Research OS: Physical AI Continual Learning + World Models

## Purpose
This folder is my research operating system for the frontier where continual
learning, world models, spatial reasoning, and visual-language grounding meet
embodied AI deployed in physical environments — especially construction sites.

The goal is NOT to accumulate paper summaries. The goal is to extract
**transferable, first-principles, decision-grade intelligence** that lets me:
1. Show up to technical conversations as a peer, not a student
2. Recognize patterns and anti-patterns across the field
3. Make better strategic and technical decisions, faster
4. Build the ProCore design-to-reality OEC loop with evidence

## Core Principle
Every paper, every concept, every technique should be interrogated for:
- What's the underlying mechanism that makes it work?
- What's the first principle beneath the mechanism?
- Where else does this principle apply, beyond the original domain?
- What's the anti-pattern — the way people get this wrong?

If I can't answer those four questions, I haven't actually read the paper.

## Folder Structure

```
research-os/
├── inbox/        ← raw PDFs land here; auto-expire after 2 weeks
├── extracted/    ← Layer 1: per-paper structured notes
├── synthesis/    ← Layer 2: cross-paper patterns + frontier maps
├── briefs/       ← Layer 3: ProCore-ready decision documents
└── archive/      ← processed but no longer active
```

## How To Process Each Paper (Layer 1: Extraction)

For each paper added to this folder, produce a structured note with these fields:

**Core Claim (one sentence, plain language)**
What is the paper actually claiming? Strip the jargon.

**Underlying Mechanism**
Why does the technique work? What's the causal chain? Not "what is it" but
"what is the thing it exploits about how learning/perception/reasoning works?"

**First Principle**
The deepest, most general truth this paper rests on. Often unstated in the
paper itself. Should be transferable beyond the paper's domain.

**Anti-Pattern**
The way this is commonly misunderstood or misapplied. The version that looks
right but isn't. The trap.

**Transferability Test**
Where else does this mechanism apply?
- Inside Physical AI / construction?
- Outside Physical AI (other domains, other problems, other systems)?
- To non-technical domains (people, organizations, decisions)?
If a mechanism doesn't transfer, it's probably a local optimization, not a
principle.

**Connection To OEC**
How does this paper relate to the closed-loop architecture?
- Observation (sensors, perception, scene understanding)
- Evaluation (delta detection, anomaly, design-vs-reality)
- Control (feed-forward prediction, feedback adaptation)
- Continual loop (learning on-site over time)

**Verdict**
- Foundational (read it, understand it deeply, it's a load-bearing idea)
- Useful (a technique to keep in the toolbox)
- Misleading (looks right, isn't — explain why)
- Skip (not worth the read; explain why for future reference)

**One-Sentence Compression**
Tweet-length distillation. The thing I'd say if someone asked me at a
conference what this paper is about. Forces abstraction.

## How To Synthesize (Layer 2: Pattern Recognition)

When the folder has 5+ papers, run a synthesis pass that:

**Cluster By Mechanism, Not Topic**
Papers in the same topic ("continual learning") often use totally different
mechanisms. Papers in different topics ("RL," "world models," "lifelong
perception") often use the *same* mechanism. The clusters that matter are by
mechanism — that's where transferable insight lives.

**Recurring Patterns**
What approaches keep working across papers? Why? What's the deeper truth they
share?

**Recurring Anti-Patterns**
What approaches keep failing? Why? What's the false intuition that keeps
generating them?

**Frontier Map**
- What's well-solved?
- What's actively contested?
- What's known to be unsolved?
- What's unsolved AND nobody is working on it? (← This is where opportunity lives)

**False Consensus Detection**
Where does the field agree but might be wrong? What "everyone knows" claims
should I challenge from first principles?

## How To Make It Actionable (Layer 3: Decisions)

After synthesis, for each cluster of insights, write a short brief:

**For ProCore Specifically**
- Which OEC layer does this affect?
- What would change in the architecture if I took this seriously?
- What would I prototype to test it?

**For Physical AI Broadly**
- What's the bigger pattern this fits into?
- Where else in the embodied AI stack does this apply?

**Next Decisions Unlocked**
- What technical decision does this clarify?
- What conversation should I have because of this?
- What experiment would test it cheapest and fastest?

**Questions For Thiago / The Team**
- What would I ask in the next technical conversation because of this?
- What would I push back on if it came up?

## Operating Principles For This Folder

1. **Mechanism over outcome.** If I can't explain WHY a technique works, I
   don't understand it yet. Re-read.

2. **First principles over jargon.** If the only way I can describe an idea is
   with the paper's own terminology, I haven't internalized it.

3. **Transfer over memorization.** A paper I can't apply to a different domain
   is a paper I haven't really learned.

4. **Anti-patterns are gold.** Knowing what doesn't work, and why, is often
   more valuable than knowing what does.

5. **Synthesis over collection.** Five papers I've connected into a pattern
   beat fifty papers I've individually summarized.

6. **Compression forces understanding.** If I can't tweet it, I don't get it.

7. **Action over accumulation.** Every paper should leave me with a question
   to ask, an experiment to try, or a decision to make.

## Two-Builder Cross-Pollination

This is my Physical AI research folder, but the patterns I extract should also
illuminate how I build myself.
- A continual learning principle for AI is often a continual learning
  principle for me.
- A world model architecture insight might be a mental model architecture
  insight.
- An OEC closed-loop pattern in robotics maps to OEC in personal growth and
  team building.

When a paper teaches me something about systems, also ask: what does this
teach me about how to build myself, my team, or my company?

## Anti-Patterns For This Folder Itself

Watch for these failure modes and call them out:
- **Survey-mode reading.** Reading widely to feel productive without
  committing to depth.
- **Paper-collection fetish.** Adding papers without processing them.
- **Jargon laundering.** Using paper terminology in notes instead of plain
  language — disguised non-understanding.
- **Local optimization.** Going deep on a paper that doesn't transfer.
- **False completeness.** Thinking "I've covered the field" when actually I've
  just touched it.

## The Cadence

```
DAILY:    No paper reading. Process inbox 0-1 papers max.
WEEKLY:   Scan Tier 2 + Tier 3 sources. Add 2-4 papers to inbox.
          Process 2-3 papers from inbox to extracted/.
MONTHLY:  Run Layer 2 (synthesis) across all extracted papers.
          Run Layer 3 (briefs) on the synthesis output.
          Archive papers that didn't contribute to a pattern.
```

If you can't sustain the weekly cadence, you're collecting too many papers.
Cut the intake, not the processing.

## The Minimum Viable Version Stop-Condition

Set a calendar reminder for one week after starting. Two questions:
1. Did I produce the ProCore brief?
2. Did I have a clearer mental model for the next conversation than I do today?

If both answers are yes → scale the system. Add more papers.
If either is no → the system is broken. Fix it before adding inputs.
