"""대조실험 (Cowork 검토, 2026-08-18): lcm_sim.py의 동일 적대적 생성기에서
설계기반 보정(DSL, Egami et al. 2023)의 편향을 측정.
인간: easy 0.5% / hard 8% 오류, LLM 계열과 독립 가정(가정임을 명시).
결과: DSL(n=200) 편향 +0.9~+1.1pp — 모든 LCM 변형(+2.2~+4.6pp)보다 작음.
인간 hard-오류율 민감도: 8%→+0.93 / 5%→+0.70 / 3%→+0.62 / 1%→+0.48pp."""
import numpy as np
from lcm_sim import simulate_once, N, PREV
P_HARD = 0.08
def run(h_hard, reps=40):
    out = []
    for rep in range(reps):
        z, y = simulate_once(np.random.default_rng(1000 + rep))
        r = np.random.default_rng(5000 + rep)
        hard = r.random(N) < P_HARD
        e = np.where(hard, r.random(N) < h_hard, r.random(N) < 0.005)
        h = np.where(e, ~z, z).astype(int)
        vote = (y.sum(1) >= 4).astype(int)
        idx = np.random.default_rng(9200 + rep).choice(N, 200, replace=False)
        out.append((1 - vote).mean() + ((1 - h)[idx] - (1 - vote)[idx]).mean())
    v = np.array(out)
    return v.mean(), v.std()
if __name__ == "__main__":
    print(f"true error rate: {1-PREV:.4f}")
    for hh in (0.08, 0.05, 0.03, 0.01):
        m, s = run(hh)
        print(f"human hard-error {hh:.0%}: DSL(n=200) mean={m:.4f} sd={s:.4f} "
              f"bias={(m-(1-PREV))*100:+.2f}pp")
