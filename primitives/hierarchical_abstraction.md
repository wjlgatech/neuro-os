# Primitive: Hierarchical Abstraction

> Concept 5 of 5 | neuro-os
> Sources: Hawkins et al. (2017), Yamins & DiCarlo (2016), LeCun/Bengio/Hinton (2015), Numenta HTM repo, FeUdal Networks repo

## 1. One-Sentence Definition
The cortex organizes intelligence as a hierarchy of abstraction levels, where each level receives concrete patterns from below and sends abstract predictions downward - enabling generalization from specifics to universals.

## 2. Core Mechanism
```
Hierarchy of abstraction (cortex and deep networks):

Level 5: Concepts/Goals         ["animal" / task objective]
    ^  top-down predictions (priors)
    |  bottom-up errors
Level 4: Object categories      ["dog shape" / feature maps]
    ^
    |
Level 3: Parts/features         ["ears, snout" / edges+shapes]
    ^
    |
Level 2: Local patterns          ["orientations" / Gabor filters]
    ^
    |
Level 1: Raw input               [pixels / photoreceptors]

Each level: COMPRESSES information, ABSTRACTS invariants, PREDICTS lower level
```

## 3. Key Equation
```
Layer-wise abstraction (feedforward):
  h^(l) = f(W^(l) * h^(l-1) + b^(l))

Hierarchical predictive coding (Rao & Ballard):
  prediction at level l: mu^(l) = g(r^(l+1))
  error at level l: e^(l) = r^(l) - mu^(l)
  update: dr^(l)/dt = -e^(l) + (dg/dr)^T * e^(l-1)

HTM (Hawkins): each column = mini-sequence predictor
  active_columns(t) = f(input(t), context(t-1))
```

## 4. Intuition
Your brain doesn't store "the letter A written in red on white paper." It stores: 1) pixels -> edges -> shapes -> letter "A" -> word -> meaning. Each level is invariant to the variations below. This is why you recognize "A" in any font, color, or size: the hierarchy abstracts away irrelevant variation.

## 5. Real-World Example
Listening to a symphony: your auditory cortex processes vibrations -> notes -> chords -> phrases -> musical ideas -> emotional narrative. Each level compresses the previous and becomes invariant to its specific details. You can recognize Beethoven's 5th even hummed off-key.

## 6. AI Analogy
| Brain | AI |
|---|---|
| Primary sensory cortex | First conv/embed layer |
| Association cortex | Middle transformer layers |
| Prefrontal cortex | Final output layers |
| Cortical columns | Attention heads |
| Top-down predictions | Cross-attention, conditioning |
| Hierarchical RL (sub-goals) | Options framework / FeUdal Networks |

```python
import torch.nn as nn

# Simple hierarchy: 3 abstraction levels
class HierarchicalNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.level1 = nn.Linear(784, 256)   # pixels -> edges
        self.level2 = nn.Linear(256, 64)    # edges -> shapes
        self.level3 = nn.Linear(64, 10)     # shapes -> digit
        self.relu = nn.ReLU()
    
    def forward(self, x):
        h1 = self.relu(self.level1(x))   # level 1 representation
        h2 = self.relu(self.level2(h1))  # level 2 representation
        h3 = self.level3(h2)             # final classification
        return h3, h1, h2  # return all levels for inspection
```
Brain-inspired hierarchy: https://github.com/numenta/nupic
Hierarchical RL: https://github.com/dmakian/feudal_networks

## 7. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Hierarchy too shallow | Misses abstractions | Linear models; underfitting |
| Hierarchy too deep | Gradients vanish, abstractions collapse | Very deep nets without skip connections |
| Level mismatch | Wrong abstraction for the task | Using pixel-level features for semantics |
| Brittle hierarchy | Abstractions don't transfer | Overfit models; brain damage disrupting one level |

## 8. Mental Practice
Take any complex idea and practice "hierarchy drilling":
1. What is the most concrete, specific instance? (pixel level)
2. What pattern does it exemplify? (edge level)
3. What principle does that pattern reflect? (shape level)
4. What universal law underlies the principle? (concept level)

## 9. Connections
- UNIFIES ALL: every mechanism (PC, Hebb, RL, Attention) operates across hierarchical levels
- ORGANIZED BY: Predictive Processing (top-down = predictions, bottom-up = errors)
- LEARNED VIA: Hebbian Learning at each level
- OPTIMIZED BY: RL with hierarchical options (sub-goals at each level)
- GATED BY: Attention at each level of hierarchy

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 8/10 | "Abstract invariants layer by layer" |
| Transferability | 9/10 | Brain, CNNs, transformers, RL, linguistics |
| Executability | 8/10 | Core of all deep learning |
| Falsifiability | 7/10 | Layer-wise lesion studies possible |

## 11. Key Sources
- Paper: Hawkins et al. (2017) Neocortex columns: https://www.frontiersin.org/articles/10.3389/fncir.2017.00081/full
- Paper: Yamins & DiCarlo (2016) Visual hierarchy: https://www.annualreviews.org/doi/10.1146/annurev-neuro-071714-033936
- Paper: LeCun, Bengio, Hinton (2015) Deep Learning: https://www.nature.com/articles/nature14539
- Paper: Dietterich (2000) MAXQ hierarchical RL: https://arxiv.org/abs/cs/9905014
- Repo: Numenta HTM: https://github.com/numenta/nupic
- Repo: FeUdal Networks (hierarchical RL): https://github.com/dmakian/feudal_networks
- Blog: https://towardsdatascience.com/hierarchical-predictive-coding-85ceee9b9fd0
- Blog: Numenta research: https://numenta.com/neuroscience-research/research-publications/papers/
