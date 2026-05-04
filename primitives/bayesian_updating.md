# Primitive: Bayesian Updating

> Belief OS primitive 1 of 6 | neuro-os personal_epistemic_v1
> Sources: Bayes (1763), Jaynes "Probability Theory: The Logic of Science" (2003), Tetlock "Superforecasting" (2015)

## 1. One-Sentence Definition
Beliefs are probabilistic, and the rational way to update them when new evidence arrives is to multiply the prior by the likelihood and renormalize.

## 2. Core Mechanism
```
P(H | E) = P(E | H) * P(H) / P(E)

         posterior  =  likelihood  *  prior  /  marginal
```
Flow: hold prior -> observe evidence -> assess likelihood under each hypothesis -> renormalize -> new prior for the next observation.

## 3. Intuition
You should not flip your view because of one striking story; you should not refuse to update when evidence keeps piling up. The strength of an update is proportional to how much more likely the evidence is under one hypothesis than the alternatives, *weighted by where you started*.

## 4. Worked Example
A medical test is 99% accurate (sensitivity = specificity = 0.99). Disease prevalence in the population is 0.1%. A random person tests positive. P(disease | positive)?
- Prior P(disease) = 0.001
- Likelihood ratio = 0.99 / 0.01 = 99
- Posterior odds = 0.001/0.999 * 99 ≈ 0.099 -> P ≈ 9%

The base rate dominates the test's sensitivity.

## 5. AI Analogy
| Reasoning | AI |
|---|---|
| Prior | Initial weights / regularization |
| Likelihood | Loss given parameters |
| Posterior | Updated weights |
| Bayesian update | One gradient step |

## 6. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Base-rate neglect | Update on likelihood, ignore prior | "He's wearing a lab coat, must be a doctor" (in a hospital lobby of 2000 patients) |
| Anchoring | Refuse to update; prior stays despite strong evidence | "I read it in 2010, must still be true" |
| Over-update | One vivid datum swings posterior too far | Single anecdote overrides decade of stats |

## 7. Falsification Test
Write down P(X) before observing. After observing, write P(X | obs). If you cannot articulate WHICH new info changed the probability and BY HOW MUCH, you weren't doing Bayes.

## 8. Mental Practice
For one decision per week, write your prior as a number 0-1. Update only when you can name the evidence and likelihood ratio.

## 9. Connections
- DEPENDS ON: Base-Rate Reasoning (the prior)
- CHECKED BY: Falsifiability (you must say what would change your mind)
- BIASED BY: Survivorship Bias (the evidence pool you can see is filtered)

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 10/10 | One equation |
| Transferability | 10/10 | Any decision under uncertainty |
| Executability | 10/10 | Implement in three lines |
| Falsifiability | 9/10 | Calibration is measurable (Brier score) |

## 11. Key Sources
- Book: Jaynes (2003) Probability Theory: The Logic of Science
- Book: Tetlock & Gardner (2015) Superforecasting
- Paper: Tversky & Kahneman (1974) Judgment under Uncertainty https://www.science.org/doi/10.1126/science.185.4157.1124
