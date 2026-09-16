"""
Simulation: can a no-gold-standard latent class design recover the metadata
error rate (true non-delegation share among records marked 'delegation')
using K=7 imperfect annotators = 3 Claude tiers + 3 OpenAI tiers + 1 rule-based?

Key threat: within-family conditional dependence (Claude models share errors,
OpenAI models share errors). We test:
  (A) naive CI-LCM on all 7 tests, ignoring dependence
  (B) family-collapsed LCM: majority vote within each LLM family -> 3 quasi-
      independent tests (Claude-consensus, OpenAI-consensus, rules)
Ground truth generation includes 'hard items' where families err together.
"""
import numpy as np

rng = np.random.default_rng(42)

N = 7558           # full edge corpus, annotate everything (LLMs are cheap)
PREV = 0.965       # true share of genuine delegations among recorded ones
                   # (paper's point estimate: 1 - 3.5%)

# --- annotator error model -------------------------------------------------
# families: 0,1,2 = Claude tiers; 3,4,5 = OpenAI tiers; 6 = rule-based
FAMILY = np.array([0, 0, 0, 1, 1, 1, 2])
K = 7

# easy items: near-perfect; hard items (ambiguous clauses, ~8% of corpus):
# elevated, *family-correlated* error
P_HARD = 0.08
# per-test error prob on easy items (sens errors ~ spec errors, kept simple)
ERR_EASY = np.array([0.010, 0.006, 0.004,   # haiku, sonnet, opus
                     0.010, 0.006, 0.004,   # oai small/mid/large
                     0.030])                # rules: worse overall but independent
# on hard items, each *family* draws a shared error event with this prob,
# plus small idiosyncratic error
ERR_HARD_FAMILY = np.array([0.35, 0.35, 0.25])   # claude, oai, rules
ERR_HARD_IDIO   = 0.05

def simulate_once(rng):
    z = rng.random(N) < PREV                      # true label (1=delegation)
    hard = rng.random(N) < P_HARD
    y = np.zeros((N, K), dtype=int)
    # family-shared error events on hard items
    fam_err = np.zeros((N, 3), dtype=bool)
    for f in range(3):
        fam_err[:, f] = hard & (rng.random(N) < ERR_HARD_FAMILY[f])
    for k in range(K):
        f = FAMILY[k]
        idio = np.where(hard,
                        rng.random(N) < ERR_HARD_IDIO,
                        rng.random(N) < ERR_EASY[k])
        err = fam_err[:, f] | idio
        y[:, k] = np.where(err, ~z, z).astype(int)
    return z, y

# --- standard 2-class LCM via EM (conditional independence) ---------------
def lcm_em(y, iters=300, seed=0):
    n, k = y.shape
    r = np.random.default_rng(seed)
    prev = 0.9
    sens = np.full(k, 0.95) + r.random(k) * 0.02   # P(y=1|z=1)
    fpr  = np.full(k, 0.05) + r.random(k) * 0.02   # P(y=1|z=0)
    for _ in range(iters):
        # E-step
        l1 = np.log(prev) + (y * np.log(sens) + (1 - y) * np.log(1 - sens)).sum(1)
        l0 = np.log(1 - prev) + (y * np.log(fpr) + (1 - y) * np.log(1 - fpr)).sum(1)
        m = np.maximum(l1, l0)
        w = np.exp(l1 - m) / (np.exp(l1 - m) + np.exp(l0 - m))  # P(z=1|y)
        # M-step
        prev = w.mean()
        sens = np.clip((w[:, None] * y).sum(0) / w.sum(), 1e-4, 1 - 1e-4)
        fpr  = np.clip(((1 - w)[:, None] * y).sum(0) / (1 - w).sum(), 1e-4, 1 - 1e-4)
    # label-switching guard: class 1 should be the majority-'1' class
    if prev < 0.5:
        prev, sens, fpr = 1 - prev, fpr, sens
    return prev, sens, fpr

def family_collapse(y):
    """majority vote within each 3-model family + rules -> 3 tests"""
    c = (y[:, 0:3].sum(1) >= 2).astype(int)
    o = (y[:, 3:6].sum(1) >= 2).astype(int)
    return np.column_stack([c, o, y[:, 6]])

# --- run -------------------------------------------------------------------
REPS = 40
res = {"naive7": [], "fam3": [], "agree_only": []}
for rep in range(REPS):
    z, y = simulate_once(np.random.default_rng(1000 + rep))
    p7, _, _ = lcm_em(y, seed=rep)
    y3 = family_collapse(y)
    p3, _, _ = lcm_em(y3, seed=rep)
    res["naive7"].append(1 - p7)   # estimated metadata error rate
    res["fam3"].append(1 - p3)
true_err = 1 - PREV

print(f"true metadata error rate: {true_err:.4f}  (i.e., 3.5%)")
for name, v in [("naive 7-test CI-LCM (dependence ignored)", res["naive7"]),
                ("family-collapsed 3-test LCM            ", res["fam3"])]:
    v = np.array(v)
    print(f"{name}: mean={v.mean():.4f}  sd={v.std():.4f}  "
          f"bias={(v.mean()-true_err)*100:+.2f}pp  "
          f"range=[{v.min():.4f},{v.max():.4f}]")

# how much raw disagreement is there to learn from?
z, y = simulate_once(np.random.default_rng(7))
unan = (y.std(1) == 0).mean()
print(f"\nshare of items with unanimous 7/7 agreement: {unan:.3f}")
print(f"items with any disagreement: {int((1-unan)*N)} of {N}")

# --- cost model ------------------------------------------------------------
print("\n--- API cost model (Claude side, per full-corpus pass) ---")
CODEBOOK_TOK = 2500     # cached system prompt (codebook v1.1 + few-shot)
CLAUSE_TOK   = 400      # per-item clause text + instruction
OUT_TOK      = 80       # JSON label + brief rationale
items = 7558
# (input$, output$) per MTok, standard; batch = 50% off; cache read = 10% of input
models = {"Haiku 4.5":  (1, 5), "Sonnet 5":  (2, 10), "Opus 5":  (5, 25)}
total = 0
for m, (ci, co) in models.items():
    fresh = items * CLAUSE_TOK / 1e6 * ci
    cache = items * CODEBOOK_TOK / 1e6 * ci * 0.10
    out   = items * OUT_TOK   / 1e6 * co
    cost  = (fresh + cache + out) * 0.5          # batch API
    total += cost
    print(f"  {m:10s}: ${cost:6.2f}  (batch + cached codebook)")
print(f"  Claude total, 1 run x 3 models: ${total:.2f}")
print(f"  + 3-run consistency on 500-item subsample: ~${total*2*500/7558:.2f}")
