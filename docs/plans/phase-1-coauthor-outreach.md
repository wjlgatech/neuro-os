# Phase 1 — Co-Author Outreach Plan

> **Goal:** Recruit 1–2 academic co-authors for the Phase 1 mechanism-survival paper. Pitch is bounded — they contribute inter-rater annotation + one related-work section for second-author credit. Send outreach in Wk 1 (May 12–18, 2026); accept first 1–2 positive responses by EOD Wk 2 (May 25); fall back to solo + paid annotator if zero responses.

---

## What we need from a co-author

1. **Inter-rater extraction pass** on the N=10 paper corpus — extract `MechanismCard`s independently from the same papers. Compute Cohen's κ per field. ~10 hours of work over 2 weeks.
2. **Related-work section** for the paper (~1.5 pages). Drafted by them, reviewed by Paul. ~6 hours.
3. **One round of paper review** before submission. ~3 hours.

**Total ask:** ~20 hours over ~3 months. Single-author credit on a NeurIPS-track / ICLR submission with shipped open-source code.

**What we do NOT ask for:** code contributions, experiment running, deadline ownership, infrastructure. The substrate is already shipped.

---

## Shortlist (4 candidates, ranked)

### Candidate 1 — Vincenzo Lomonaco (University of Pisa / ContinualAI)

**Why he's #1:** Lomonaco co-authored the **Latent Replay** paper that is one of our three starter corpus papers. He runs ContinualAI (the nonprofit). Recipient of the 2025 "Marco Somalvico" Award from the Italian AI Association. >80 papers in continual learning. Active publisher in 2025–2026. Has a track record of organizing community benchmarks (which is exactly the kind of contribution we're proposing). Mid-career = bandwidth.

**Why he might say yes:** (a) our paper directly cites his work as a load-bearing reference, (b) the methodology we propose is consistent with ContinualAI's "real-world evaluation" framing, (c) the inter-rater ask is small.

**Why he might say no:** he has many demands on his time; he may have CL-specific commitments at NeurIPS 2026 already.

**Contact:** `https://www.vincenzolomonaco.com/` lists his email + ContinualAI Slack. Personal email is more responsive than Twitter/X for a first contact.

**Personalization for this candidate:** lead with "your Latent Replay paper is one of our three anchor citations — we'd be honored to have you formally on the methodology paper that operationalizes mechanism survival across the CL literature."

---

### Candidate 2 — Antonio Carta (University of Pisa, Avalanche library lead)

**Why he's strong:** Lomonaco's collaborator at Pisa. Lead maintainer of the **Avalanche** continual-learning library (8k+ GitHub stars — concrete eval-infrastructure experience). His work on streaming evaluation is exactly the eval-methodology DNA we need. More likely to respond than Lomonaco because he's slightly less famous.

**Why he might say yes:** ContinualAI alignment + our paper builds on Avalanche-compatible primitives (we could explicitly add Avalanche integration to `agent/research/` as a sweetener).

**Why he might say no:** if Lomonaco is co-author already, he may consider it redundant from the Pisa side.

**Contact:** `https://www.antoniocarta.dev/` lists his email. CV available on his site.

**Personalization:** lead with the Avalanche connection + offer to add Avalanche compatibility as a v1 feature of `world-os`.

---

### Candidate 3 — Tyler Hayes (NEC Labs America, Continual Learning research)

**Why he's strong:** Research scientist at NEC Labs with a strong publication record in continual learning evaluation and latent replay extensions (the third pillar of our corpus). Mid-career, well-cited (~2k citations). Industry affiliation = different reviewer pool than pure-academic candidates.

**Why he might say yes:** the paper opens a new evaluation framework that his team would benefit from. Industry researchers often need NeurIPS papers for promotion cycles.

**Why he might say no:** NEC Labs may require legal/IP review before any external co-authorship.

**Contact:** Google Scholar lists his NEC Labs email. Search "Tyler Hayes NEC Labs continual learning."

**Personalization:** lead with "our paper extends the latent-replay evaluation paradigm you've built on. We'd value your read on the inter-rater protocol."

---

### Candidate 4 — Sasha Luccioni (Hugging Face, AI Evaluation Methodology)

**Why she's strong:** Active researcher on AI eval methodology, with a strong public profile and prior NeurIPS / FAccT papers. The mechanism-survival framing aligns with her "evaluations as a science" agenda. Hugging Face = community-distribution amplifier for `goal-world-os-repo` and `goal-love12xfuture-brand` (secondary benefit).

**Why she might say yes:** the paper sits in her thesis space (rigorous eval); HuggingFace cares about reproducibility (we ship code with the paper).

**Why she might say no:** very high public-profile / bandwidth constraints; many existing collaborations.

**Contact:** `sasha.luccioni@huggingface.co` (public). Twitter `@SashaMTL` also responsive.

**Personalization:** lead with "your work on evaluations as a science is the framing our paper operationalizes. We'd value your expertise on the methodology rigor."

---

## Outreach email template

> **Subject:** Co-author invite — *Mechanism Survival* (Phase 1 paper, ICLR 2027 target) — ~20 hours over 3 months

Hi [First Name],

I'm Paul Wu, building `neuro-os`, an open-source closed-loop substrate for AI-assisted research. I'm reaching out because we're submitting a paper that operationalizes [paper-specific hook from personalization above].

**Working title:** *Mechanism Survival: A Closed-Loop System for Research as Predictive Compression.*

**One-sentence thesis:** AI-for-research systems should be evaluated on whether extracted mechanisms *predict reality* in adjacent decisions over a 40-day window — not on summary fidelity (BLEU, ROUGE, retrieval@k). We propose the eval methodology, ship the code, and benchmark against vanilla RAG / GraphRAG / summarization on a corpus of 10 papers (including [their relevant paper if applicable]).

**Venue plan:** arXiv preprint mid-July, NeurIPS 2026 workshop submission Aug, ICLR 2027 main / evaluations track Sept submission.

**Your contribution (~20 hours over 3 months):**
- Independent inter-rater extraction pass on our 10-paper corpus (compute Cohen's κ) — ~10 hours
- Related-work section, ~1.5 pages — ~6 hours
- One round of pre-submission review — ~3 hours

**What I bring:** the substrate is already shipped (87+ tests passing, mechanism-card schema in `agent/research/ontology.py`, closed-loop ingest/review/share/outcome pipeline). The corpus is locked. The pre-registration is on OSF [will be by EOD Wk 1]. The methodology and the code are done. What's left is the rigor of independent annotation and the polish of strong writing.

**Authorship:** second author position; affiliation listed; full credit on the artifact.

**Timeline:** I need a yes/no by end of next week (May 25, 2026) so I can plan the inter-rater pass for July. If now isn't the right time but a future collaboration could be, I'd love to know that too.

Happy to share the full outline, the pre-registration draft, or hop on a 20-minute call.

Best,
Paul Wu
GitHub: wjlgatech
LinkedIn newsletter: love12xfuture
Working draft: `https://github.com/wjlgatech/neuro-os/blob/main/docs/plans/phase-1-mechanism-survival-paper.md`

---

## Logistics — how to send

1. **Send all 4 emails Wk 1 (May 12–18).** Don't stagger. Parallel send is intentional — first to commit wins, but also: people respond to social proof / fear of missing out, so simultaneous outreach generates more responses than sequential.
2. **Track responses in a simple file.** Could be `phase-1-coauthor-responses.md` (private to you, not committed to public repo).
3. **Hard deadline EOD Wk 2 (May 25).** If two say yes, pick the top-ranked of the two and politely decline the other. If zero say yes, switch to fallback (paid annotator) without delay.
4. **Reply within 24h.** Even a "thank you for the interest, let me think" buys engagement.

---

## Fallback plan if all 4 decline

**Paid annotator route.** Recruit one PhD student or postdoc via Upwork / academic Twitter / r/MachineLearning to do the inter-rater extraction pass only (no co-authorship). Budget: $500–1500 for ~10 hours of expert annotation. Acknowledged in the paper, not on the author list.

This is a strictly worse outcome (no credibility lift, no related-work section help) but preserves the inter-rater claim. Trigger the fallback by 2026-05-25 EOD.

---

## What we are NOT doing

- **Not contacting top-tier famous PIs** (Pascanu, Liang, Finn, Hadsell, Ha, Schmidhuber) for first-author / advisor roles. Response rate is ~5%, the ask is too heavy, the bandwidth doesn't exist. Reserved for Phase 3.
- **Not contacting people whose work we're critiquing.** Reviewer bias risk.
- **Not asking for compute or funding.** The paper runs on Paul's compute budget. Co-author contribution is intellectual.
