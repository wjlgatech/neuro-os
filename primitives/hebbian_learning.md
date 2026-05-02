# Primitive: Hebbian Learning

> Concept 2 of 5 | neuro-os
> Sources: Hebb (1949), Bi & Poo (1998) STDP, Brian2 simulator repo, Spiking-Neural-Network repo

## 1. One-Sentence Definition
Synaptic connections strengthen when neurons fire together and weaken when they don't - the biological basis of all learning and memory.

## 2. Core Mechanism
```
 Neuron A fires ----> Neuron B fires  =>  synapse A->B STRENGTHENS
 Neuron A fires ----> Neuron B silent =>  synapse A->B WEAKENS

STDP (Spike-Timing Dependent Plasticity):
  pre fires BEFORE post  (+Dt) => Long-Term Potentiation (LTP) => +weight
  pre fires AFTER post   (-Dt) => Long-Term Depression (LTD)  => -weight
  |Dt| determines magnitude of change
```

## 3. Key Equation
```
Basic Hebb rule:
  dW/dt = lr * pre_activity * post_activity

STDP rule:
  dW = A+ * exp(-|dt|/tau+)  if dt > 0  (pre before post = LTP)
  dW = -A- * exp(-|dt|/tau-) if dt < 0  (post before pre = LTD)

Oja rule (normalized Hebb - prevents unlimited growth):
  dW = lr * (x*y - y^2 * W)
```

## 4. Intuition
"Neurons that fire together, wire together." Your brain physically rewires itself based on which neurons activate simultaneously. Every time you practice a skill, you're literally changing your neural architecture.

## 5. Real-World Example
Learning to ride a bike: repeatedly co-activating balance neurons + motor neurons + visual neurons strengthens those connections until the coordination becomes automatic. The physical trace is synaptic weight changes across millions of synapses.

## 6. AI Analogy
| Brain | AI |
|---|---|
| Synaptic weight change | Weight update (gradient descent) |
| Hebb rule | Unsupervised Hebbian learning |
| STDP | Spike-based temporal credit assignment |
| LTP/LTD | Positive/negative gradient |
| Oja rule | PCA via neural network |

```python
# Basic Hebbian update
def hebb_update(W, pre, post, lr=0.01):
    return W + lr * np.outer(post, pre)  # outer product

# Oja rule (normalized - won't blow up)
def oja_update(W, pre, post, lr=0.01):
    return W + lr * (np.outer(post, pre) - (post**2)[:, None] * W)
```

## 7. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Runaway potentiation | Unlimited growth, all weights max out | Without normalization |
| Catastrophic forgetting | New learning overwrites old | Standard gradient descent |
| Spurious correlations | Wrong co-activations wire | Trauma (pain + context) |
| Hebbian trap | Local minima from correlation-only learning | No error signal = no task-relevant learning |

## 8. Code Experiment
```python
import numpy as np
import matplotlib.pyplot as plt

# STDP learning window
dt = np.linspace(-50, 50, 200)  # time difference in ms
tau_plus, tau_minus = 20, 20
A_plus, A_minus = 0.01, 0.01

dW = np.where(dt > 0,
    A_plus * np.exp(-dt/tau_plus),    # LTP
    -A_minus * np.exp(dt/tau_minus))   # LTD

print(f"Max LTP: {dW.max():.4f} at dt={dt[dW.argmax()]:.0f}ms")
print(f"Max LTD: {dW.min():.4f} at dt={dt[dW.argmin()]:.0f}ms")
# Run with Brian2 for full spiking simulation
```
Repo (full spiking sim): https://github.com/brian-team/brian2
Repo (STDP examples): https://github.com/Shikhargupta/Spiking-Neural-Network

## 9. Mental Practice
After learning anything new, immediately use it in 2-3 different contexts. Each application is a Hebbian co-activation that strengthens the memory trace.

## 10. Connections
- IMPLEMENTS: Weight updates in Predictive Processing (PE drives Hebbian updates)
- GENERALIZED BY: Reinforcement Learning (reward-modulated Hebb = 3-factor rule)
- ORGANIZED INTO: Hierarchy (Hebb operates locally at each level)
- GATED BY: Attention (only attended stimuli get strong Hebbian updates)

## 11. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 9/10 | "Fire together, wire together" |
| Transferability | 9/10 | Brain, ML, memory, skill learning |
| Executability | 10/10 | Trivial to implement, Brian2 available |
| Falsifiability | 8/10 | STDP curves measurable experimentally |

## 12. Key Sources
- Book: The Organization of Behavior - Hebb (1949) [foundational]
- Paper: Bi & Poo (1998) STDP: https://www.jneurosci.org/content/18/24/10464
- Paper: Scellier & Bengio (2017): https://arxiv.org/abs/1602.05179
- Repo: Brian2 spiking NN simulator: https://github.com/brian-team/brian2
- Repo: STDP examples: https://github.com/Shikhargupta/Spiking-Neural-Network
- Blog: https://towardsdatascience.com/hebbian-learning-theory-2c1beed0f2a3
