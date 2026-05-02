# Primitive: Attention & Saliency

> Concept 4 of 5 | neuro-os
> Sources: Vaswani et al. "Attention Is All You Need" (2017), Jay Alammar "The Illustrated Transformer", Lilian Weng "Attention? Attention!", Vision Transformer repo, ViT-pytorch repo

## 1. One-Sentence Definition
Attention is the brain's mechanism for selectively routing information - deciding which inputs are worth processing deeply and which to ignore, controlling what gets through to conscious processing.

## 2. Core Mechanism
```
Biological attention:           AI attention (Transformer):
  Thalamus gates signals           Query (Q) = what am I looking for?
  Prefrontal top-down control      Key (K) = what does each input offer?
  Only attended signals reach       Value (V) = actual content to retrieve
  cortical processing              
                                   Score = softmax(Q * K^T / sqrt(d))
  "spotlight" model:               Output = Score * V
  high-res center + low-res surround
```

**Scaled dot-product attention:**
```
Attention(Q,K,V) = softmax(Q*K^T / sqrt(d_k)) * V
```

## 3. Key Equation
```
Self-attention score for position i attending to position j:
  score(i,j) = q_i . k_j / sqrt(d_k)
  weight(i,j) = softmax(score(i,j)) over all j
  output_i = sum_j weight(i,j) * v_j

Multi-head attention:
  MultiHead(Q,K,V) = Concat(head_1,...,head_h) * W_O
  head_i = Attention(Q*W_Q_i, K*W_K_i, V*W_V_i)
```

## 4. Intuition
You can't process everything at full depth. Attention is the brain's solution: maintain low-res awareness of everything while focusing high-res processing on what matters. In AI transformers, every token attends to every other token and decides how much to borrow from each.

"When encoding the word 'it', attention lets the model connect 'it' back to 'animal' 5 words earlier." - Jay Alammar

## 5. Real-World Example
Reading this sentence: your eyes (and brain) don't equally process every letter. You jump to content words, skip function words, occasionally re-attend to resolve ambiguity. This selective routing IS attention - you allocate cognitive resources dynamically based on relevance.

## 6. AI Analogy
| Brain | AI (Transformer) |
|---|---|
| Thalamic gating | Attention mask |
| Saliency / relevance | Attention score |
| Working memory (what I'm tracking) | Query (Q) |
| Long-term memory content | Key-Value (K, V) pairs |
| Multi-focal attention | Multi-head attention |
| Prefrontal top-down | Cross-attention (decoder attends to encoder) |

```python
import numpy as np

def scaled_dot_product_attention(Q, K, V):
    d_k = Q.shape[-1]
    scores = Q @ K.T / np.sqrt(d_k)  # dot product, scaled
    weights = np.exp(scores) / np.exp(scores).sum(axis=-1, keepdims=True)  # softmax
    return weights @ V, weights  # output + attention map

# Q, K, V shape: (seq_len, d_k)
Q = np.random.randn(5, 64)  # 5 tokens, 64-dim queries
K = np.random.randn(5, 64)  # 5 keys
V = np.random.randn(5, 64)  # 5 values
output, attn_map = scaled_dot_product_attention(Q, K, V)
print(f"Attention map shape: {attn_map.shape}")  # (5, 5)
print(f"Each row sums to: {attn_map.sum(axis=1)}")  # all 1.0
```
Full ViT implementation: https://github.com/google-research/vision_transformer
Attention visualization: https://github.com/jeonsworld/ViT-pytorch

## 7. Failure Cases
| Mode | Description | Example |
|---|---|---|
| Attention collapse | Attends only to one token | Degenerate heads in transformers |
| Distraction | Wrong things are salient | Pop-out effects; click-bait |
| Attention overload | Too many salient signals | Anxiety; context window overflow |
| Inattentional blindness | Miss obvious things | Gorilla experiment; prompt injection |

## 8. Mental Practice
During your next conversation, notice where your attention is: on the speaker's words, their tone, the room, your phone? Practice deliberately redirecting attention like a spotlight. How does changing what you attend to change what you perceive?

## 9. Connections
- GATING: Predictive Processing (attention weights prediction errors by precision/importance)
- SELECTIVE UPDATING: Hebbian Learning (attended stimuli get stronger synaptic updates)
- MODULATED BY: Reinforcement Learning (reward-predictive stimuli become more salient)
- HIERARCHICAL: each layer of hierarchy has its own attention mechanism

## 10. Evaluation
| Metric | Score | Reason |
|---|---|---|
| Compression | 8/10 | "Selectively route information" |
| Transferability | 9/10 | Vision, language, memory, task-switching |
| Executability | 10/10 | Core of every transformer; trivial to implement |
| Falsifiability | 9/10 | Attention maps are visualizable |

## 11. Key Sources
- Paper: Vaswani et al. (2017) Attention Is All You Need: https://arxiv.org/abs/1706.03762
- Paper: Mnih et al. (2014) Recurrent Visual Attention: https://arxiv.org/abs/1406.6247
- Paper: ViT (2020): https://arxiv.org/abs/2010.11929
- Blog: The Illustrated Transformer - Jay Alammar: https://jalammar.github.io/illustrated-transformer/
- Blog: Attention? Attention! - Lilian Weng: https://lilianweng.github.io/posts/2018-06-24-attention/
- Repo: Vision Transformer: https://github.com/google-research/vision_transformer
- Repo: ViT-pytorch (attention viz): https://github.com/jeonsworld/ViT-pytorch
