# Primitive: Expected Value

> Belief OS primitive 4 of 6 | neuro-os personal_epistemic_v1
> Sources: Pascal & Fermat (1654), Bernoulli "Specimen Theoriae Novae de Mensura Sortis" (1738), Kelly (1956)

## 1. One-Sentence Definition
The rational value of an uncertain decision is the probability-weighted sum of its outcomes; vivid stories about a single outcome should not dominate this sum.

## 2. Core Mechanism
```
EV = sum_i p_i * value_i

For repeated bets, log-utility / Kelly:
  optimal_fraction = (p*b - q) / b
  where b = odds, p = win prob, q = 1 - p
```
Step 1: enumerate outcomes. Step 2: assign probabilities. Step 3: assign values. Step 4: multiply and sum.

## 3. Intuition
A 1% chance of $1M is worth $10,000 in expectation; a 99% chance of $5,000 is worth $4,950. A risk-neutral agent prefers the lottery; a risk-averse one with declining marginal utility may not. Either way, *availability* and *vividness* are not in the equation.

## 4. Worked Example
"Should I take this contract?"
- 70% it pays $50k and takes 2 months -> +$35k EV
- 20% it underdelivers, partial pay $20k -> +$4k EV
- 10% it implodes, you eat the cost ($10k) -> -$1k EV
- Sum: $38k EV over 2 months. Compare to opportunity cost.

## 5. AI Analogy
| Reasoning | AI |
|---|---|
| Outcome enumeration | Action space |
| Probability assignment | Q-value |
| Sum p*v | Expected return |
| Risk aversion | Risk-sensitive RL (CVaR, log utility) |

## 6. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Tail neglect | Ignore low-prob, high-magnitude outcomes | "Black swan can't happen" |
| Mode-as-mean | Plan for the most likely outcome only | "It'll probably take 2 weeks" -> ships in 6 |
| Vividness override | Salient single outcome dominates EV | Lottery tickets, fear of flying |
| Single-shot framing | Apply EV to non-repeated bet without considering ruin | Kelly criterion violated |

## 7. Falsification Test
After the decision plays out, your *log* of decisions should show calibration: outcomes you said were 70% should happen ~70% of the time across many decisions.

## 8. Mental Practice
For any ">$1k or >1 day" decision, write three outcomes with probabilities summing to 1, and compute EV explicitly. Don't trust the gut number.

## 9. Connections
- DEPENDS ON: Bayesian Updating (probabilities should be calibrated)
- DEPENDS ON: Base-Rate Reasoning (priors anchor the probabilities)
- CONSTRAINED BY: Second-Order Thinking (downstream effects change the value column)

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 9/10 | One sum |
| Transferability | 10/10 | Any decision under uncertainty |
| Executability | 10/10 | Trivial arithmetic |
| Falsifiability | 9/10 | Calibration is measurable |

## 11. Key Sources
- Paper: Bernoulli (1738/1954) Exposition of a New Theory on the Measurement of Risk
- Paper: Kelly (1956) A New Interpretation of Information Rate
- Book: Taleb (2007) The Black Swan
