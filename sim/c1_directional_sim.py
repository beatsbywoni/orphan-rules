"""C1 (v1.1 §2.2): 인간 방향 편향 대칭 검증. 동일 생성기, 40반복, 시드 고정.
방향 A = hard층에서 진짜 오류를 delegation으로 오판(지시서 지정 방향, 과소추정 위험)
방향 B = hard층에서 진짜 위임을 error로 오판(DSL에 더 불리한 방향, 추가 수행)
결과 (2026-08-18):
  A d=5%: +0.51pp / A d=8%: +0.48pp / B d=5%: +1.01pp / B d=8%: +1.27pp
  vs 계열축약 LCM +2.19pp, 4-클래스(의존) LCM +2.54pp
판정: ① DSL 우위 (모든 방향·수준에서 최악 +1.27pp < LCM 최선 +2.19pp) → 하이브리드 확정.
"""
import numpy as np
from lcm_sim import simulate_once, N, PREV, lcm_em, family_collapse
from lcm_sim2 import lcm4_em
P_HARD = 0.08
TRUE = 1 - PREV

def human_directional(z, direction, d, rng):
    hard = rng.random(N) < P_HARD
    h = z.astype(int).copy()
    if direction == "A":
        flip = hard & (~z) & (rng.random(N) < d); h[flip] = 1
    else:
        flip = hard & z & (rng.random(N) < d); h[flip] = 0
    e = (~hard) & (rng.random(N) < 0.005); h[e] = 1 - h[e]
    return h

if __name__ == "__main__":
    print(f"true error rate: {TRUE:.4f}")
    for direction in ("A", "B"):
        for d in (0.05, 0.08):
            est = []
            for rep in range(40):
                z, y = simulate_once(np.random.default_rng(1000 + rep))
                h = human_directional(z, direction, d, np.random.default_rng(6000 + rep))
                vote = (y.sum(1) >= 4).astype(int)
                idx = np.random.default_rng(9200 + rep).choice(N, 200, replace=False)
                est.append((1 - vote).mean() + ((1 - h)[idx] - (1 - vote)[idx]).mean())
            v = np.array(est)
            print(f"dir {direction} d={d:.0%}: DSL bias={(v.mean()-TRUE)*100:+.2f}pp (sd {v.std():.4f})")
