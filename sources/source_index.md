# Neuroscience Knowledge Base — Source Index

Executable knowledge system covering 5 core mechanisms.

This source index is the canonical source-of-truth map for Neuro-OS. It preserves the instrumental source list for papers, repos, and blogs across:

1. Predictive Processing / Bayesian Brain
2. Hebbian Learning & Synaptic Plasticity
3. Reinforcement Learning / Dopamine / Reward
4. Attention & Saliency
5. Hierarchical Abstraction / Cortex Structure

## 1. Predictive Processing / Bayesian Brain

### Papers
- **The Free-Energy Principle: A Unified Brain Theory** — Karl Friston (2010)  
  URL: https://www.nature.com/articles/nrn2787  
  Key idea: Brains minimize free energy, roughly prediction error plus complexity, to infer causes of sensory input.
- **Surfing Uncertainty** — Andy Clark (2016)  
  URL: https://books.google.com/books/about/Surfing_Uncertainty.html  
  Key idea: The brain is a prediction machine; perception is controlled hallucination.
- **Predictive Coding: A Theoretical and Experimental Review** — Rao & Ballard (1999)  
  URL: https://www.nature.com/articles/nn0199_79  
  Key idea: Hierarchical predictive coding in visual cortex.

### Repos
- https://github.com/BerenMillidge/PredictiveCodingBackprop
- https://github.com/infer-actively/pypc

### Blogs
- https://www.lesswrong.com/posts/4hLcbXaqudM9wSeoa/a-tutorial-on-predictive-coding
- https://aeon.co/essays/the-genius-neuroscientist-who-might-hold-the-key-to-true-ai

## 2. Hebbian Learning & Synaptic Plasticity

### Papers
- **The Organization of Behavior** — Donald Hebb (1949)  
  Key idea: Neurons that fire together wire together.
- **Spike-Timing Dependent Plasticity** — Bi & Poo (1998)  
  URL: https://www.jneurosci.org/content/18/24/10464  
  Key idea: Precise spike timing determines synaptic strengthening or weakening.
- **Equilibrium Propagation** — Scellier & Bengio (2017)  
  URL: https://arxiv.org/abs/1602.05179

### Repos
- https://github.com/Shikhargupta/Spiking-Neural-Network
- https://github.com/brian-team/brian2

### Blogs
- https://towardsdatascience.com/hebbian-learning-theory-2c1beed0f2a3

## 3. Reinforcement Learning / Dopamine / Reward

### Papers
- **Human-Level Control Through Deep Reinforcement Learning** — Mnih et al. (2015)  
  URL: https://www.nature.com/articles/nature14236  
  Key idea: DQN achieves human-level game play; computational bridge to reward-driven learning.
- **A Neural Substrate of Prediction and Reward** — Schultz, Dayan, Montague (1997)  
  URL: https://www.science.org/doi/10.1126/science.275.5306.1593  
  Key idea: Dopamine neurons encode temporal-difference reward prediction errors.
- **Reinforcement Learning: An Introduction** — Sutton & Barto (2018)  
  URL: http://incompleteideas.net/book/the-book-2nd.html

### Repos
- https://github.com/openai/spinningup
- https://github.com/DLR-RM/stable-baselines3

### Blogs
- http://www.scholarpedia.org/article/Reward_signals
- https://spinningup.openai.com/en/latest/spinningup/rl_intro.html

## 4. Attention & Saliency

### Papers
- **Attention Is All You Need** — Vaswani et al. (2017)  
  URL: https://arxiv.org/abs/1706.03762  
  Key idea: Self-attention replaces recurrence; queries, keys, values.
- **Recurrent Models of Visual Attention** — Mnih et al. (2014)  
  URL: https://arxiv.org/abs/1406.6247  
  Key idea: Attention as selective information routing.
- **An Image is Worth 16x16 Words** — Dosovitskiy et al. (2020)  
  URL: https://arxiv.org/abs/2010.11929

### Repos
- https://github.com/google-research/vision_transformer
- https://github.com/jeonsworld/ViT-pytorch

### Blogs
- https://jalammar.github.io/illustrated-transformer/
- https://lilianweng.github.io/posts/2018-06-24-attention/

## 5. Hierarchical Abstraction / Cortex Structure

### Papers
- **A Theory of How Columns in the Neocortex Enable Learning the Structure of the World** — Hawkins et al. (2017)  
  URL: https://www.frontiersin.org/articles/10.3389/fncir.2017.00081/full
- **Hierarchical Models in the Visual Cortex** — Yamins & DiCarlo (2016)  
  URL: https://www.annualreviews.org/doi/10.1146/annurev-neuro-071714-033936
- **Deep Learning** — LeCun, Bengio, Hinton (2015)  
  URL: https://www.nature.com/articles/nature14539
- **Hierarchical Reinforcement Learning with the MAXQ Value Function Decomposition** — Dietterich (2000)  
  URL: https://arxiv.org/abs/cs/9905014

### Repos
- https://github.com/dmakian/feudal_networks
- https://github.com/numenta/nupic

### Blogs
- https://towardsdatascience.com/hierarchical-predictive-coding-85ceee9b9fd0
- https://numenta.com/neuroscience-research/research-publications/papers/
