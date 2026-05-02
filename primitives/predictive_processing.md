# Primitive: Predictive Processing

> Concept 1 of 5 | neuro-os
> Sources: Friston (2010), Clark (2016), Rao & Ballard (1999), pypc repo, PredictiveCodingBackprop repo

## 1. One-Sentence Definition
The brain is a prediction machine that continuously models the world and updates based on prediction error (actual minus expected).

## 2. Core Mechanism
```
[Higher Cortex] --top-down prediction--> [Sensors]
      ^                                       |
      |        <--prediction error (PE)--      |
 [Update model] <-- minimize surprise F -- [Reality]
```
Flow: predict -> observe -> compute error -> update model -> repeat (~100ms)

## 3. Key Equation
```
Free Energy: F = prediction_error + model_complexity
= -log P(data|model) + KL[q(hidden)||p(hidden)]
```
Minimize F = minimize surprise = accurate + efficient model

## 4. Intuition
Brain bets on the future then checks if it won. It builds a world model so good it rarely gets surprised.
"Perception is controlled hallucination" - Andy Clark

## 5. Real-World Example
Reaching for a coffee mug: brain predicts full/warm -> hand finds lighter than expected -> prediction error fires -> model updates in ~50ms below consciousness.

## 6. AI Analogy
| Brain | AI |
|---|---|
| Prediction error | Loss function |
| Model update | Backpropagation |
| Generative model | VAE decoder |
| Free energy | ELBO |
| Prior belief | Regularization |

Closest architecture: Variational Autoencoder
```python
loss = -E[log p(x|z)] + KL[q(z|x) || p(z)]  # IS the free energy principle
```

## 7. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Hallucination | Prior too strong, PE ignored | Schizophrenia; LLM confabulation |
| Rigidity | Model never updates | OCD; confirmation bias |
| Over-updating | Every noise triggers full update | Anxiety; adversarial attacks |

## 8. Code Experiment
```python
import numpy as np

def pc_step(prediction, reality, lr=0.1):
    pe = reality - prediction
    return prediction + lr * pe, pe

true_signal = np.sin(np.linspace(0, 4*np.pi, 200))
prediction, errors = np.zeros(200), []
for t in range(1, 200):
    prediction[t], pe = pc_step(prediction[t-1], true_signal[t])
    errors.append(abs(pe))
print(f"Error reduced: {(1-errors[-1]/errors[0])*100:.1f}%")  # ~90%+
```
Repo: https://github.com/infer-actively/pypc
Paper code: https://github.com/BerenMillidge/PredictiveCodingBackprop

## 9. Mental Practice
Before meetings: write one prediction. After: note the error. Update your model.

## 10. Connections
- USES: Attention (which errors matter - precision weighting)
- IMPLEMENTED BY: Hebbian Learning (PE drives synaptic updates)
- BIASED BY: Reinforcement Learning (reward shapes prediction priors)
- ORGANIZED ACROSS: Hierarchy (top-down predictions, bottom-up errors)

## 11. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 10/10 | Minimize prediction error |
| Transferability | 10/10 | Brain, AI, perception, emotion |
| Executability | 9/10 | Implementable as VAE |
| Falsifiability | 7/10 | Hard to isolate experimentally |

## 12. Key Sources
- Paper: https://www.nature.com/articles/nrn2787 (Friston 2010)
- Book: Surfing Uncertainty - Andy Clark (2016)
- Paper: https://www.nature.com/articles/nn0199_79 (Rao & Ballard 1999)
- Blog: https://www.lesswrong.com/posts/4hLcbXaqudM9wSeoa/
- Blog: https://aeon.co/essays/the-genius-neuroscientist-who-might-hold-the-key-to-true-ai
- Repo: https://github.com/infer-actively/pypc
- Repo: https://github.com/BerenMillidge/PredictiveCodingBackprop
