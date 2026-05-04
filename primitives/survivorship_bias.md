# Primitive: Survivorship Bias

> Belief OS primitive 6 of 6 | neuro-os personal_epistemic_v1
> Sources: Wald (1943) on aircraft armor, Brown et al. "Survivorship Bias in Performance Studies" (1992)

## 1. One-Sentence Definition
The visible sample is the population filtered by selection — failures are invisible, so any pattern detected in survivors must be discounted by the (unknown) selection rate.

## 2. Core Mechanism
```
observed_pattern = true_pattern * P(survive | true_pattern) /
                   P(survive)

If P(survive | trait) is high, the trait will appear over-represented
in survivors even if it has no causal effect on success.
```

## 3. Intuition
Abraham Wald looked at WW2 bombers returning with bullet holes mostly in the wings and fuselage. The Air Force wanted to armor those spots. Wald said: armor the spots that *aren't* hit on returners — those are the planes that didn't come back.

The data was filtered by survival; the policy that ignored the filter would have killed more pilots.

## 4. Worked Example
"Successful founders dropped out of college." (Gates, Jobs, Zuckerberg, Ellison.)
- Visible class: billionaire founders (~10).
- Reference class: people who dropped out of college to start a company (~millions).
- Conditional rate: P(success | dropped out) is essentially zero. The dropout signal is informative *given* they made it; it is not predictive *before* they tried.

## 5. AI Analogy
| Reasoning | AI |
|---|---|
| Visible sample | Training set |
| Filter | Selection bias / sampling distribution |
| Hidden failures | Out-of-distribution data |
| Inverse-propensity weighting | Causal-inference correction |

## 6. Failure Cases
| Mode | Description | Example |
|---|---|---|
| "Be like X" advice | Pattern-match to visible winners, ignore failed copies | Hustle culture, founder mythology |
| Backtest illusion | Strategy works on companies that still exist | Survivorship-biased index |
| Mentor selection | Only ask people who succeeded what worked | "Confounded by talent + luck" |
| Trial-result reporting | Only successful experiments get published | File-drawer problem |

## 7. Falsification Test
Before drawing a lesson from a visible success, list at least three *failed* attempts at the same strategy and check that the success rate is meaningfully above the failure rate.

## 8. Mental Practice
When reading a "X did Y, you should too" piece, reflexively ask: "what is the denominator?" If the author cannot supply it, treat the conclusion as a story, not evidence.

## 9. Connections
- VIOLATES: Base-Rate Reasoning (the reference class is the visible class, which is wrong)
- DISTORTS: Bayesian Updating (the likelihood is computed on a filtered sample)
- ENABLED BY: Falsifiability failure (the hypothesis was never tested against failures)

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 9/10 | "Where are the missing planes?" |
| Transferability | 10/10 | Any inference from a selected sample |
| Executability | 9/10 | Ask "what's the denominator?" |
| Falsifiability | 8/10 | The unobserved sample is the test |

## 11. Key Sources
- Note: Wald (1943) Memorandum on the Armor of Aircraft (SRG, Columbia)
- Paper: Brown et al. (1992) Survivorship Bias in Performance Studies https://doi.org/10.1093/rfs/5.4.553
- Book: Mlodinow (2008) The Drunkard's Walk
