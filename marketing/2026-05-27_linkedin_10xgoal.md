# LinkedIn Post — /10xgoal Skill
**Date:** 2026-05-27
**Platform:** LinkedIn
**Title:** Claude, Codex, and Hermes all shipped `/goal` this year. They all have the same blind spot.
**CTA:** Drop your raw goal in comments — I'll compile one live
**Version:** v4 — reframed around the /goal ecosystem gap

---
<!-- SHORT TEASER POST -->

## SHORT POST (teaser)

Claude, Codex, and Hermes all shipped `/goal` this year.

All of them assume the same thing: that you already know how to write a machine-verifiable goal.

Most people don't.

So you type `/goal fix all the bugs and make the tests pass` — and the agent works for 47 minutes and confidently hands you broken code.

Not because the agent failed. Because the spec was broken.

The agent honored your contract exactly. You just wrote a bad contract.

---

The bottleneck in AI-assisted execution isn't the agent anymore.

It's the input.

`/goal` is a race car. Most people hand it a napkin sketch and wonder why it crashes.

---

I built the missing layer: `/10xgoal`.

It sits upstream of `/goal`. You feed it your raw, messy intent. It lint-checks your goal against 6 structural failure modes, reads your project context, asks ≤3 clarifying questions, and emits a compiled contract ready to drop directly into `/goal`.

The full pipeline:

**messy human intent → `/10xgoal` → compiled contract → `/goal` → verified execution**

Right now most people are skipping the middle step.

Long-form below — with the 6 failure modes, a live before/after example, and the evaluator output format.

Drop your raw `/goal` in the comments. I'll compile one live.

---

#AIAgents #ClaudeCode #Codex #GoalSetting #BuildInPublic #Founders #DeveloperTools

---
<!-- END SHORT POST -->

---

## LONG FORM POST

---

Claude Code, Codex, and Hermes Agent all shipped a `/goal` command this year.

The idea: give the agent a precise objective, and it executes until the evaluator confirms it's done. No hallucination. No premature victory declaration. Just machine-verifiable progress.

It's genuinely one of the best ideas in AI tooling right now.

And every single one of them has the same assumption buried in the fine print:

**That you already know how to write a machine-verifiable goal.**

They don't.

---

Here's what actually happens.

You open Claude Code. You type:

`/goal fix all the bugs and make the tests pass`

The agent works for 47 minutes. Then it says: "All tests passing. Code is clean. Ready for review."

Three tests still broken. Linter has 14 warnings. One new bug introduced that didn't exist before.

The agent wasn't broken. It executed exactly what you asked.

*Fix all the bugs* — it fixed the ones it noticed.
*Make the tests pass* — it found a path to passing tests.

You wrote a broken contract. The agent honored it perfectly.

That's not an agent failure. That's an input failure.

---

The bottleneck in AI-assisted execution isn't the agent anymore.

The agents are good. Getting better every month.

The bottleneck is the spec.

`/goal` is a race car. Most people hand it a hand-drawn map and wonder why it crashes.

---

I spent six months studying how goal specs fail structurally — not discipline failures, not motivation failures — the bugs baked in at the moment you write them down.

I found six failure modes. Each one makes the goal unenforceable in a specific way.

**#1 — Unmeasurable**
"Make the API faster."
Faster than what? By how much? Measured when?
The evaluator cannot check adjectives. The agent will optimize until it feels done.
Fix: "P99 latency under 200ms on the `/search` endpoint, measured by the existing `pytest tests/perf/` suite."

**#2 — Unbounded**
"Fix all the bugs."
Which bugs? In which files? Found how — linter? failing tests? customer reports?
The agent will work until it runs out of tokens or confidence, then declare victory.
Fix: "Fix the 4 failing tests in `tests/test_auth.py`. Stop there."

**#3 — Bundled**
"Refactor the auth module, add tests, fix the linter warnings, and update the docs."
That's four goals wearing one trenchcoat. The evaluator can't check any of them cleanly because partial completion is ambiguous.
Fix: sequence. Four separate `/goal` commands. Each one completes before the next starts.

**#4 — Unverifiable**
"Improve the code quality."
How do you PROVE this is done? Not "it looks cleaner" — what command confirms it?
Fix: "Ruff reports zero findings on `agent/`. `mypy agent/ --strict` exits clean."
Now the evaluator has a test. The agent has a finish line.

**#5 — Misaligned** ← *the silent killer*
You've been debugging a crash for 30 minutes. Then you type: `"optimize the database queries"`
The real problem is the crash. You're running the agent on the wrong thing.
This is the failure mode `/goal` cannot catch — because it only knows what you typed, not what you actually need.
Fix: before specifying the goal, ask — *"is this the real problem, or the one I'm comfortable admitting?"*

**#6 — Undependencied**
"Deploy to production."
Do you have passing tests? A staging verification? Migrations run? Env vars set?
The agent will hit prerequisite #1 on step 1, stall, and either hallucinate a workaround or stop with an unhelpful error.
Fix: map the dependency chain first. State the prerequisites explicitly in the spec.

---

Every one of these failure modes produces the same symptom:

**The agent confidently executes the wrong thing.**

And you can't blame the agent. You handed it an unenforceable contract. It did its best.

---

This is the friction nobody's talking about in the `/goal` ecosystem.

Claude, Codex, and Hermes are optimizing the execution layer. Faster. Smarter. More reliable.

But the input layer — the spec itself — is still hand-written by humans who've never been taught what a machine-verifiable goal looks like.

The result: the most powerful agent tooling in history, fed goals that would fail a 10-second lint check.

---

So I built the missing preprocessor.

I call it `/10xgoal`. It sits upstream of `/goal`.

You feed it your raw, messy, half-formed intent — the thing you'd say out loud before you knew this needed to be precise. It runs the lint check. Scores all six failure modes. Reads your project context (CLAUDE.md, your test commands, your recent git history) so it can pre-fill answers without interrogating you. Then emits a compiled spec ready to paste directly into `/goal`.

Maximum three clarifying questions. Never more.

Here's what the output looks like:

**You typed:** "I want to get serious about investing and build a 6-month emergency fund."

**Lint result:** Bundled (2 goals), Unverifiable (no check for "serious"), Undependencied (no current baseline).

**Compiled:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 GOAL 1 of 2: Know Your Numbers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/goal Pull last 3 bank statements. Calculate exact monthly
expenses: fixed + variable. Determine current runway in months.

EVALUATOR CHECKLIST:
□ One doc exists with specific dollar amounts
□ No category says "roughly" or "about"
□ Current runway in months is written down

SCOPE GUARD:
• Only touch: bank app + one document
• Stop if: fewer than 3 months of statements available
ESTIMATED: ~90 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 GOAL 2 of 2: Write Your Investment Constitution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/goal Define 3 buckets: Fortress (emergency), Foundation
(long-term), Frontier (high-risk). Set allocations. Write
5 decision rules you'll follow regardless of emotion.

EVALUATOR CHECKLIST:
□ Document exists with all 3 buckets named
□ Percentages sum to 100%
□ Every rule uses specific numbers, not "reasonable amounts"

DEPENDS ON: Goal 1 (needs baseline numbers as input)
ESTIMATED: ~60 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

A vague two-headed wish became two sequential, verifiable contracts — each one ready to drop directly into `/goal`.

---

One quality test I apply to everything that comes out:

**A stranger should be able to run this goal. No implicit knowledge required beyond what's written.**

If anything is "understood" — if any assumption isn't in the contract — it's not compiled. It's still a wish.

---

The thing that surprised me most building this:

**The compilation step is the transformation.**

When you're forced to specify what "improve the code quality" actually means — to pick a command, a threshold, a scope — you discover what you actually wanted.

Half the time, it's not what you thought you were asking for.

One client spent three weeks telling me "I need to build my network." Two clarifying questions in, the real goal surfaced: "I want three conversations this month with people who make me feel less alone in what I'm building."

That's a fundamentally different goal. One is a LinkedIn grind. The other is a human need.

The compiler finds the goal underneath the goal. In 60 seconds.

---

`/goal` is a powerful primitive. It changed how I build.

But a powerful primitive given broken input is just a faster way to build the wrong thing.

`/10xgoal` is the missing step between your intention and your `/goal` command.

The pipeline: messy human intent → `/10xgoal` → compiled contract → `/goal` → verified execution.

That's the full loop. Right now, most people are skipping the middle step.

---

**Your turn:**

Take the last `/goal` you ran — or the next one you're about to run. Check it against the six modes:

□ Measurable — is there a verifiable number?
□ Bounded — does the evaluator know when to stop?
□ Singular — or secretly 3 goals sharing one spec?
□ Verifiable — what command proves it's done?
□ Aligned — is this the real problem, or the visible one?
□ Dependencied — what must be true before this can start?

If it fails even one — don't run it yet.

**Drop your raw goal in the comments. I'll compile one live — evaluator checklist, scope guard, and all.**

---

*Physical AI engineer. Co-founder. I build systems that close the loop between human intent and real-world outcomes — in robots and in code.*

*Follow for more on AI agent tooling, autonomous systems, and what it takes to make execution actually work.*

---

#AIAgents #ClaudeCode #Codex #GoalSetting #PhysicalAI #BuildInPublic #Founders #AgentAI #DeveloperTools
