# Primitive: Reinforcement Learning (Dopamine)

> Concept 3 of 5 | neuro-os
> Sources: Schultz/Dayan/Montague (1997), Mnih et al. DQN (2015), Sutton & Barto (2018), OpenAI Spinning Up repo, Stable-Baselines3 repo

## 1. One-Sentence Definition
The brain learns by predicting rewards and updating behavior based on the difference between expected and actual reward - dopamine IS the temporal difference prediction error signal.

## 2. Core Mechanism
```
Agent <---> Environment
  |    observes state s_t
  |    takes action a_t
  |    receives reward r_t
  |    observes next state s_{t+1}
  v
Update: delta = r_t + gamma*V(s_{t+1}) - V(s_t)  [TD error]
Dopamine neurons FIRE = delta > 0 (better than expected)
Dopamine neurons PAUSE = delta < 0 (worse than expected)
Dopamine neurons BASELINE = delta = 0 (as expected)
```

## 3. Key Equation
```
Temporal Difference (TD) error:
  delta_t = r_t + gamma * V(s_{t+1}) - V(s_t)

Value update:
  V(s_t) <- V(s_t) + alpha * delta_t

Q-learning:
  Q(s,a) <- Q(s,a) + alpha * [r + gamma * max_a' Q(s',a') - Q(s,a)]

Policy gradient (REINFORCE):
  theta <- theta + alpha * grad_theta log pi(a|s) * R
```

## 4. Intuition
Dopamine doesn't signal pleasure - it signals prediction error. If something is better than expected, dopamine spikes. If exactly as expected, no signal. If worse, it dips. Over time, the dopamine spike moves backward in time to the earliest reliable predictor of reward - this IS temporal difference learning.

## 5. Real-World Example
Pavlov's dogs: initially dopamine fires when food arrives. After conditioning, it fires when the bell rings (the predictor). The dopamine response has traveled backward in time to the earliest cue - exactly what TD learning predicts.

## 6. AI Analogy
| Brain | AI |
|---|---|
| Dopamine neuron firing | TD error signal (delta) |
| Reward circuit | Reward function r(s,a) |
| Value function (what is this state worth?) | V(s) or Q(s,a) |
| Policy (what to do in each state) | pi(a|s) |
| Prefrontal cortex | Policy network |
| Striatum | Value network |

```python
# Minimal TD learning
def td_update(V, s, s_next, reward, alpha=0.1, gamma=0.9):
    td_error = reward + gamma * V[s_next] - V[s]
    V[s] += alpha * td_error
    return V, td_error
```

## 7. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Reward hacking | Optimize proxy instead of true goal | Video game exploits; misaligned AI |
| Sparse reward | No signal to learn from | Hard exploration problems |
| Catastrophic forgetting | New tasks erase old policies | Without replay buffer |
| Dopamine dysregulation | Wrong prediction error signals | Addiction (hijacked RL); depression |

## 8. Code Experiment
```python
import numpy as np

# Q-learning on simple grid world
class SimpleRL:
    def __init__(self, n_states=10, n_actions=2):
        self.Q = np.zeros((n_states, n_actions))
    
    def update(self, s, a, r, s_next, alpha=0.1, gamma=0.9):
        td_error = r + gamma * self.Q[s_next].max() - self.Q[s, a]
        self.Q[s, a] += alpha * td_error
        return td_error
    
    def act(self, s, epsilon=0.1):
        if np.random.random() < epsilon:
            return np.random.randint(self.Q.shape[1])  # explore
        return self.Q[s].argmax()  # exploit

agent = SimpleRL()
# Run episodes and watch Q-values converge
```
Full implementations:
- OpenAI Spinning Up: https://github.com/openai/spinningup
- Stable-Baselines3: https://github.com/DLR-RM/stable-baselines3

## 9. Mental Practice
For 1 week: after each decision, score it as +1 (better than expected), 0 (as expected), -1 (worse). Notice where your internal dopamine system fires. Are your reward predictions calibrated?

## 10. Connections
- BIOLOGICAL BASIS: Dopamine = TD prediction error signal (Schultz 1997)
- SCALES WITH: Hierarchy (options framework, sub-goals, feudal RL)
- MODULATES: Hebbian Learning (reward-modulated 3-factor rule)
- BIASES: Predictive Processing (reward shapes prediction priors)

## 11. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 9/10 | Dopamine = TD error |
| Transferability | 10/10 | Brain, AI, behavior, addiction, motivation |
| Executability | 10/10 | Many clean implementations available |
| Falsifiability | 9/10 | Dopamine spike timing measurable |

## 12. Key Sources
- Paper: Schultz et al. (1997) Dopamine = reward PE: https://www.science.org/doi/10.1126/science.275.5306.1593
- Paper: Mnih et al. (2015) DQN: https://www.nature.com/articles/nature14236
- Book: Sutton & Barto RL textbook: http://incompleteideas.net/book/the-book-2nd.html
- Blog: Scholarpedia reward signals: http://www.scholarpedia.org/article/Reward_signals
- Blog: Spinning Up intro: https://spinningup.openai.com/en/latest/spinningup/rl_intro.html
- Repo: OpenAI Spinning Up: https://github.com/openai/spinningup
- Repo: Stable-Baselines3: https://github.com/DLR-RM/stable-baselines3
