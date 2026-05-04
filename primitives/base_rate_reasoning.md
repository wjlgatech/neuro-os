# Primitive: Base-Rate Reasoning

> Belief OS primitive 2 of 6 | neuro-os personal_epistemic_v1
> Sources: Tversky & Kahneman (1973, 1974), Kahneman "Thinking, Fast and Slow" (2011)

## 1. One-Sentence Definition
Before updating on specific evidence, anchor your estimate to the prior frequency of the outcome in the relevant reference class.

## 2. Core Mechanism
```
estimate(X) = base_rate(X in reference_class) +
              update(specific_evidence)
```
Step 1: choose the reference class. Step 2: look up the base rate. Step 3: only then update on the case-specific signal.

## 3. Intuition
Vivid descriptions trigger fast classification ("Linda sounds like a feminist"); base rates are pallid statistics that the System-1 brain ignores. The disciplined move is to *first* ask "of all people like X, what fraction Y?" and only then update on the colorful detail.

## 4. Worked Example
Linda is 31, single, outspoken, and very bright. She majored in philosophy and as a student was deeply concerned with discrimination and social justice. Which is more probable?
- (a) Linda is a bank teller
- (b) Linda is a bank teller AND active in the feminist movement

(b) is a strict subset of (a), so P(b) <= P(a). The base rate of bank tellers is much higher than the base rate of feminist bank tellers. Most respondents pick (b) — the *conjunction fallacy*.

## 5. AI Analogy
| Reasoning | AI |
|---|---|
| Reference-class frequency | Class prior in a Bayesian classifier |
| Case-specific evidence | Likelihood of features given class |
| Base-rate neglect | Classifier overfit to recent samples |

## 6. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Conjunction fallacy | A + B rated more probable than A alone | Linda problem |
| Representativeness | Match feature pattern, ignore frequency | "Looks like a startup founder" -> assumed to be one |
| Reference-class shopping | Pick a class that supports the conclusion | "Look at all the dropouts who made it" |

## 7. Falsification Test
State your reference class explicitly *before* you state your estimate. If you cannot name the reference class, the estimate is feel-based, not base-rate-based.

## 8. Mental Practice
Before any forecast, write: "Reference class: ___. Base rate: ___." Then update with case-specific info.

## 9. Connections
- FEEDS INTO: Bayesian Updating (the prior IS the base rate)
- BIASED BY: Survivorship Bias (the visible class is not the reference class)
- AMPLIFIES: Expected Value (correct EV needs correct base rates)

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 9/10 | Two-step recipe |
| Transferability | 10/10 | Any frequency-based forecast |
| Executability | 10/10 | Look up a number |
| Falsifiability | 8/10 | Reference-class disagreement is real |

## 11. Key Sources
- Paper: Tversky & Kahneman (1973) On the Psychology of Prediction
- Paper: Kahneman & Tversky (1972) Subjective Probability https://doi.org/10.1016/0010-0285(72)90016-3
- Book: Kahneman (2011) Thinking, Fast and Slow
