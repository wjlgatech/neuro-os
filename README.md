# neuro-os

> **Executable Neuroscience Knowledge OS** - A cognitive compiler for your mind

A structured knowledge system distilling 5 core brain mechanisms into executable primitives, experiments, evaluations, and a knowledge graph.

## Philosophy

You are not building a neuroscience dataset.
You are building **a cognitive compiler for your own mind.**

Every concept must:
- Be explainable in 60 seconds
- Be implementable in code
- Change how you think

## Structure

```
neuro-os/
  primitives/          <- 5 core mechanism files (START HERE)
    predictive_processing.md
    hebbian_learning.md
    reinforcement_learning.md
    attention.md
    hierarchical_abstraction.md
  README.md
  .gitignore
```

## The 5 Core Mechanisms

| # | Concept | 1-Sentence Definition | Eval Score |
|---|---|---|---|
| 1 | **Predictive Processing** | Brain minimizes prediction error to model the world | 10/10 |
| 2 | **Hebbian Learning** | Neurons that fire together wire together | 9/10 |
| 3 | **Reinforcement Learning** | Dopamine = temporal difference prediction error | 9/10 |
| 4 | **Attention** | Selectively route information by relevance | 8/10 |
| 5 | **Hierarchical Abstraction** | Cortex organizes intelligence as abstraction layers | 8/10 |

## Knowledge Graph

```
Predictive Processing
  USES -> Attention (precision-weighting: which errors matter?)
  IMPLEMENTED BY -> Hebbian Learning (PE drives synaptic weight updates)
  BIASED BY -> Reinforcement Learning (reward shapes prediction priors)
  ORGANIZED ACROSS -> Hierarchy (top-down predictions, bottom-up errors)

Hebbian Learning
  IMPLEMENTS -> Weight changes in Predictive Processing
  GENERALIZED BY -> RL (reward-modulated Hebb = 3-factor learning rule)

Reinforcement Learning
  BIOLOGICAL BASIS -> Dopamine = TD prediction error (Schultz 1997)
  SCALES WITH -> Hierarchy (options framework, sub-goals)

Attention
  BIOLOGICAL -> Thalamic gating, prefrontal top-down control
  AI ANALOG -> Transformer self-attention (Q, K, V)

Hierarchy
  UNIFIES ALL -> every mechanism operates across levels
```

## Each Primitive Contains

1. One-sentence definition
2. Core mechanism diagram (ASCII)
3. Key equation
4. Intuition
5. Real-world example
6. AI analogy + code
7. Failure cases
8. Code experiment
9. Mental practice
10. Connections to other primitives
11. Evaluation scores
12. Key sources (papers, repos, blogs)

## Sources Distilled

**Papers:** Friston (Free Energy), Clark (Surfing Uncertainty), Bi & Poo (STDP), Schultz (Dopamine), Mnih (DQN), Vaswani (Attention Is All You Need), Hawkins (Neocortex columns), LeCun/Bengio/Hinton (Deep Learning)

**Blogs:** Jay Alammar (Illustrated Transformer), Lilian Weng (Attention? Attention!), LessWrong (Predictive Coding Tutorial), Scholarpedia (Reward signals), OpenAI Spinning Up

**Repos:** pypc, PredictiveCodingBackprop, Brian2, Spiking-Neural-Network, OpenAI Spinning Up, Stable-Baselines3, Vision Transformer, Numenta HTM, FeUdal Networks

## Eval Metrics

| Metric | Question |
|---|---|
| **Compression** | Can you reduce it to 1 idea? |
| **Transferability** | Does it apply to brain, AI, and life? |
| **Executability** | Can you implement or test it? |
| **Falsifiability** | Can you design an experiment that breaks it? |

## Quick Start

1. Read primitives in order (1→5)
2. For each: write the definition from memory, implement the code experiment
3. Find 1 real-world example in your day
4. Connect it to the concept above and below in the hierarchy

---

*Built as part of CompanyOS neuroscience knowledge system.*  
*"A small set of generative principles that rewrite how you think."*
