# LinkedIn Post — /10xgoal Skill
**Date:** 2026-05-27
**Platform:** LinkedIn
**Title:** My AI agent lied to me about finishing its work. Then I realized I do the same thing.
**CTA:** Drop your goal in comments — I'll compile one live
**Version:** v3 — upgraded from skill deep-read

---

My AI coding agent worked for 47 minutes straight.

Then it said: "All tests passing. Code is clean. Ready for review."

Three tests were still broken. The linter had 14 warnings. It had introduced a new bug that didn't exist before.

The agent wasn't broken. It was confident.

Language models don't verify. They predict what "done" sounds like.

And "done" sounds like: *"All tests passing. Code is clean."*

I stared at my screen and understood something for the first time:

**A goal is not a promise to yourself. It's a contract with an evaluator.**

And if the evaluator can't check it — if there's no mechanical test for "done" — the agent (or you) will hallucinate completion. Every time.

---

The uncomfortable truth:

Most goals fail not because you lack discipline. They fail because they're unenforceable contracts.

"Get healthier." "Grow the business." "Learn AI."

Imagine you're an agent executing those. When do you stop? How do you verify done? What does the evaluator check?

Nothing. The evaluator checks nothing. So you either declare victory on a good day or quietly give up on a bad one.

That's not a willpower problem. That's a contract problem.

---

I studied how goals fail structurally — the bugs baked in at the moment of writing.

I found six failure modes. Each one makes the goal unenforceable in a specific way.

**#1 — Unmeasurable**
You used an adjective where you needed a number.
"Get healthier" — healthier than what? Measured how? By whom?
The evaluator can't check adjectives.
Fix: replace every adjective with a metric.
"Resting heart rate below 65 bpm by October, checked every Sunday morning."

**#2 — Unbounded**
No scope. No finish line.
"Learn AI" — all of AI? Which part? When are you done?
Unbounded goals are buffets. You graze forever and never commit to a meal.
Fix: "Complete fast.ai Part 1 and deploy one model to production by August 1."

**#3 — Bundled**
"This year: get fit, learn Spanish, start a podcast, read 50 books, build a side project."
Five goals sharing one person's willpower. When one falls behind, the guilt contaminates the rest. By March, all five are zombies.
Fix: sequence. One goal. Finish it. Then the next.
The person who does one thing finishes it. The person who does five things finishes their Netflix queue.

**#4 — Unverifiable**
"Become a better writer."
A stranger cannot verify this. Which means you can't either — not honestly. You'll judge by how you feel, which fluctuates with sleep and caffeine and whether someone liked your last post.
Fix: "Publish 12 essays, each receiving 5+ thoughtful comments." Now there's evidence. Not feelings.

**#5 — Misaligned** ← *this one is the sneaky one*
You're optimizing the visible symptom, not the actual cause.
A client spent three weeks telling me "I need to build my network." After two clarifying questions, the real goal surfaced: "I want three conversations this month with people who make me feel less alone in what I'm building."
That's a fundamentally different goal. One is a LinkedIn grind. The other is a human need.
Fix: ask *"Is this the real problem, or the one I'm comfortable admitting?"*

**#6 — Undependencied**
"Launch my startup."
Cool. Do you have a validated idea? A customer who'll pay? An LLC? A way to accept money?
You'll hit prerequisite #1 on Day 1, lose momentum, and say "I'll get back to it next month."
Fix: map the dependency chain first. Prerequisites aren't distractions — they're load-bearing structure.

---

My day job is Physical AI — teaching machines to perceive and act in the real world.

Every autonomous system I've built runs an OEC closed loop: **Observe → Evaluate → Control → repeat.**

This is how robots go from flailing randomly to placing a brick precisely. The evaluator in the loop is what makes the system self-correcting.

After my agent lied to me, I realized:

**Humans don't have an evaluator in their goal loop.**

We have the plan. We have the effort. We're missing the mechanical check that compares reality to intent and refuses to be fooled.

We're running open-loop. No wonder we crash.

---

So I built the evaluator. I call it `/10xgoal`.

Here's what makes it different from every other goal-setting framework:

**It reads your context before asking you anything.**

Before asking a single question, it silently reads your project files — your CLAUDE.md, your package.json, your recent git commits, your CI config. It builds a picture of what you've been working on, what broke, what you tried, what tools you have.

Then, when it detects a failure mode, it already knows the answer. Instead of asking "how do you run your tests?" it says: "I found `pytest tests/` in your pyproject.toml — should we use that as the verification command?"

Maximum three questions. Never more. It respects your momentum.

---

Here's what the compiled output actually looks like:

**Before:** "I want to get serious about investing and build a 6-month emergency fund."

Lint result: Bundled (2 goals), Unverifiable (no check for "serious"), Undependencied (no current baseline).

**After:**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 GOAL 1 of 2: Know Your Numbers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/goal Pull the last 3 bank statements. Calculate exact monthly
expenses: fixed + variable. Determine current runway in months.

EVALUATOR CHECKLIST:
□ One document exists with specific dollar amounts
□ No category says "roughly" or "about"
□ Current runway in months is written down

SCOPE GUARD:
• Only touch: your bank app + a single doc
• Stop if: you don't have 3 months of statements available
ESTIMATED: ~90 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 GOAL 2 of 2: Write Your Investment Constitution
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

/goal Define 3 buckets: Fortress (emergency), Foundation (long-term),
Frontier (high-risk). Set percentage allocations. Write 5 decision
rules you'll follow regardless of emotion.

EVALUATOR CHECKLIST:
□ Document exists with all 3 buckets
□ Percentages add to 100%
□ Every decision rule uses specific numbers, not "reasonable amounts"

DEPENDS ON: Goal 1 (needs your baseline numbers)
ESTIMATED: ~60 min
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

A two-headed wish became two sequential, verifiable contracts.

You can't lie to yourself. The spec won't let you.

---

One quality test I apply to every compiled goal:

**A stranger should be able to run this goal. No implicit knowledge required beyond what's in the contract.**

If there's anything "understood" between you and the goal — any assumption that isn't written down — it's not compiled. It's still a wish with extra steps.

---

The thing that surprised me most:

**The compilation step is the transformation.**

When you're forced to specify what "get healthier" actually means — to pick a number, a timeline, an evaluator check — you discover what you actually want.

Half the time, it's not what you thought.

The compiler doesn't just clean up your goals. It finds the goals underneath your goals.

---

The same six failure modes that kill human goals kill AI agent goals.

Feed a coding agent "make the code better" and it will rearrange deck chairs for 20 minutes and call it done.

Feed it a compiled goal — scoped, measurable, with explicit evaluator checks — and it becomes a machine. It knows exactly what done looks like. No hallucination. No premature victory declaration.

The compiler works for both species.

---

One more thing: if your goal is already well-formed, the compiler says so immediately and gets out of the way.

*"This goal is well-formed. Here's the evaluator checklist I'd add."*

Most frameworks make you do the whole process regardless. `/10xgoal` respects good work.

---

**Your turn:**

Take your most important current goal. Run it through the six checks:

□ Measurable — is there a number?
□ Bounded — do you know when you're done?
□ Singular — or secretly 3 goals in a trenchcoat?
□ Verifiable — could a stranger confirm you achieved it?
□ Aligned — is this the real problem, or the comfortable one?
□ Dependencied — what must be true before you can start?

If it fails even one — it's a wish. Not a contract.

**Drop your raw goal in the comments. I'll compile one live — evaluator checklist and all.**

---

*Physical AI engineer. Co-founder. Building systems that close the loop between human intent and real-world outcomes.*

*Follow for more on autonomous systems, knowledge infrastructure, and what machines teach us about how to think.*

---

#AI #GoalSetting #PhysicalAI #ClaudeCode #BuildInPublic #Founders #AgentAI #Productivity
