"""
Fix test: does a dependence-aware LCM recover the true error rate?
Model: latent truth z in {0,1} x latent difficulty h in {easy,hard}
       => 4 components; tests conditionally independent given (z,h),
       with difficulty-specific error rates per test.
This is the finite-mixture route (Albert & Dodd 2004 family) to absorbing
shared error modes: correlated errors are explained by the shared latent h.
Same data generator as sim 1 (which ALSO has family-shared events beyond h,
so this is a conservative test: the fitted model is still misspecified).
"""
import numpy as np
from lcm_sim import simulate_once, N, PREV  # reuse generator

def lcm4_em(y, iters=500, seed=0):
    n, k = y.shape
    r = np.random.default_rng(seed)
    # components: (z=1,easy) (z=1,hard) (z=0,easy) (z=0,hard)
    pi = np.array([0.85, 0.08, 0.05, 0.02])
    # P(y_k=1 | comp): start near-informative
    th = np.vstack([
        np.full(k, 0.99), np.full(k, 0.70),   # z=1: easy near 1, hard lower
        np.full(k, 0.01), np.full(k, 0.30),   # z=0: easy near 0, hard higher
    ]) + (r.random((4, k)) - .5) * 0.02
    th = np.clip(th, 1e-4, 1 - 1e-4)
    for _ in range(iters):
        logp = np.log(pi)[None, :] + (
            y[:, None, :] * np.log(th)[None, :, :] +
            (1 - y[:, None, :]) * np.log(1 - th)[None, :, :]
        ).sum(2)
        m = logp.max(1, keepdims=True)
        w = np.exp(logp - m); w /= w.sum(1, keepdims=True)
        pi = np.clip(w.mean(0), 1e-6, None); pi /= pi.sum()
        th = np.clip((w.T @ y) / w.sum(0)[:, None], 1e-4, 1 - 1e-4)
    prev = pi[0] + pi[1]
    # guard: components 0,1 must be the 'tests mostly say 1' side
    if th[[0, 1]].mean() < th[[2, 3]].mean():
        prev = 1 - prev
    return prev

REPS = 40
est = []
for rep in range(REPS):
    z, y = simulate_once(np.random.default_rng(1000 + rep))
    est.append(1 - lcm4_em(y, seed=rep))
est = np.array(est)
true_err = 1 - PREV
print(f"true error rate: {true_err:.4f}")
print(f"4-class (truth x difficulty) LCM: mean={est.mean():.4f} sd={est.std():.4f} "
      f"bias={(est.mean()-true_err)*100:+.2f}pp range=[{est.min():.4f},{est.max():.4f}]")

# sanity: what does a *correctly specified* world look like (no shared errors)?
import lcm_sim as s1
def simulate_indep(rng):
    z = rng.random(N) < PREV
    y = np.zeros((N, 7), dtype=int)
    err_all = np.array([.014,.010,.008,.014,.010,.008,.032])  # matched marginals
    for k in range(7):
        e = rng.random(N) < err_all[k]
        y[:, k] = np.where(e, ~z, z).astype(int)
    return z, y
est2 = []
for rep in range(REPS):
    z, y = simulate_indep(np.random.default_rng(2000 + rep))
    p, _, _ = s1.lcm_em(y, seed=rep)
    est2.append(1 - p)
est2 = np.array(est2)
print(f"benchmark, truly independent errors, plain LCM: mean={est2.mean():.4f} "
      f"sd={est2.std():.4f} bias={(est2.mean()-true_err)*100:+.2f}pp")
