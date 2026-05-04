# Primitive: Falsifiability

> Belief OS primitive 3 of 6 | neuro-os personal_epistemic_v1
> Sources: Popper "The Logic of Scientific Discovery" (1934/1959), Deutsch "The Beginning of Infinity" (2011)

## 1. One-Sentence Definition
A belief is real knowledge only if it forbids something — if no possible observation could reduce your confidence in it, it is not a belief about the world.

## 2. Core Mechanism
```
belief(X) is real iff there exists observation O such that:
    P(X | O) << P(X)

i.e., you can name what would change your mind
```
The *test* of a belief is the set of observations it rules out, not the set it explains.

## 3. Intuition
Theories that "explain everything" — astrology, vague self-help, conspiracy thinking — are unfalsifiable, and that is their failure mode, not their strength. A real claim restricts the space of possible futures; an unreal claim is consistent with any future you observe.

## 4. Worked Example
- "The economy is fragile right now." -> what observation would falsify this? If you can't say, this is mood, not analysis.
- "Tesla deliveries will exceed 500k next quarter." -> falsified by the actual delivery number. This is a real prediction.

## 5. AI Analogy
| Reasoning | AI |
|---|---|
| Falsifying observation | Held-out test sample |
| Unfalsifiable theory | Model that fits training data with arbitrary parameters |
| Bold prediction | Model with low effective complexity that still fits |

## 6. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Goalpost-shifting | Move what would falsify after observing | "I meant 500k *adjusted* deliveries" |
| Vague phrasing | Predictions worded so any outcome confirms | "Markets will be volatile" |
| Conspiracy logic | Counter-evidence becomes evidence | "Of course they say that — they would" |

## 7. Falsification Test (recursive)
For every belief you hold, write the sentence: "I would reduce my confidence in X if I observed ___." If the blank is hard to fill, the belief is decoration.

## 8. Mental Practice
Before stating an opinion in a meeting, mentally complete: "I'm wrong if ___ happens." Say the opinion only if the blank fills.

## 9. Connections
- ENFORCED BY: Bayesian Updating (forbids ad-hoc rescue)
- DEPENDS ON: Second-Order Thinking (what *would* the world look like under each hypothesis?)
- BLOCKED BY: Survivorship Bias (the falsifying examples may be filtered out)

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 10/10 | "Forbids something" |
| Transferability | 10/10 | Universal epistemic test |
| Executability | 9/10 | One-sentence challenge |
| Falsifiability | 10/10 | Self-applying |

## 11. Key Sources
- Book: Popper (1959) The Logic of Scientific Discovery
- Book: Deutsch (2011) The Beginning of Infinity
- Essay: Yudkowsky "Making Beliefs Pay Rent (in Anticipated Experiences)" https://www.lesswrong.com/posts/a7n8GdKiAZRX86T5A/
