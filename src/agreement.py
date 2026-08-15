#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
agreement.py — 어노테이터 일치도 및 표본크기 계산 (의존성 없음)

트랙 A(변호사)·트랙 B(무변호사) 양쪽에서 씁니다.

사용
----
  # 두 라벨 파일 간 Cohen's κ (inter 또는 intra)
  python src/agreement.py kappa \
      --a data/goldset_to_label.csv --a-col L1_위임인가 \
      --b data/goldset_llm.csv      --b-col LLM_L1

  # 3인 이상 → Fleiss' κ / Krippendorff's α
  python src/agreement.py alpha \
      --files data/goldset_to_label.csv:L1_위임인가 \
              data/goldset_llm.csv:LLM_L1 \
              data/goldset_peer.csv:L1_위임인가

  # 골드셋 크기 정당화
  python src/agreement.py samplesize --half-width 0.07

보고 규범 (Braun 2024, AI&Law 32(3) 권고)
  ① 어노테이터 풀(인원·전문성)  ② 항목당 독립 어노테이터 수
  ③ 표준화된 IAA 지표          ④ 불일치 처리 절차
  ⑤ 골드 라벨과 함께 원본 개별 어노테이션 전량 공개
"""

import argparse
import csv
import math
import random
from collections import Counter, defaultdict
from pathlib import Path


# ---------------------------------------------------------------- I/O

def load(path, col, key="id"):
    """CSV → {id: label}. 빈 라벨은 제외."""
    out = {}
    with open(path, encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            if col not in row:
                raise SystemExit(f"'{col}' 열이 {path} 에 없습니다. "
                                 f"있는 열: {list(row.keys())}")
            v = (row.get(col) or "").strip()
            k = (row.get(key) or "").strip()
            if v and k:
                out[k] = v
    return out


def _paired(a, b):
    common = sorted(set(a) & set(b))
    return [a[k] for k in common], [b[k] for k in common], common


# ---------------------------------------------------------------- Cohen κ

def cohen_kappa(x, y):
    n = len(x)
    if n == 0:
        return None, None, None
    labels = sorted(set(x) | set(y))
    obs = sum(1 for i in range(n) if x[i] == y[i]) / n
    cx, cy = Counter(x), Counter(y)
    exp = sum((cx[l] / n) * (cy[l] / n) for l in labels)
    kappa = (obs - exp) / (1 - exp) if exp < 1 else 1.0
    return kappa, obs, labels


def bootstrap_ci(x, y, fn=cohen_kappa, B=2000, seed=1, alpha=0.05):
    rng = random.Random(seed)
    n = len(x)
    vals = []
    for _ in range(B):
        idx = [rng.randrange(n) for _ in range(n)]
        k, _, _ = fn([x[i] for i in idx], [y[i] for i in idx])
        if k is not None and not math.isnan(k):
            vals.append(k)
    if not vals:
        return None, None
    vals.sort()
    lo = vals[int((alpha / 2) * len(vals))]
    hi = vals[min(len(vals) - 1, int((1 - alpha / 2) * len(vals)))]
    return lo, hi


def confusion(x, y):
    labels = sorted(set(x) | set(y))
    m = defaultdict(int)
    for a, b in zip(x, y):
        m[(a, b)] += 1
    return labels, m


def interpret(k):
    if k is None:
        return "-"
    for thr, txt in ((0.81, "almost perfect"), (0.61, "substantial"),
                     (0.41, "moderate"), (0.21, "fair"), (0.0, "slight")):
        if k >= thr:
            return txt
    return "poor"


def cmd_kappa(args):
    a = load(args.a, args.a_col, args.key)
    b = load(args.b, args.b_col, args.key)
    x, y, ids = _paired(a, b)
    if not x:
        raise SystemExit("공통 id로 짝지어진 라벨이 없습니다. --key 를 확인하십시오.")
    k, obs, labels = cohen_kappa(x, y)
    lo, hi = bootstrap_ci(x, y, B=args.boot)

    print(f"\n비교 대상")
    print(f"  A: {args.a} [{args.a_col}]")
    print(f"  B: {args.b} [{args.b_col}]")
    print(f"\n짝지어진 항목 n = {len(x)}   (A만 {len(a)-len(x)}, B만 {len(b)-len(x)})")
    print(f"단순일치도  = {obs:.4f}")
    print(f"Cohen's κ   = {k:.4f}   [95% CI {lo:.4f}, {hi:.4f}]   ({interpret(k)})")

    labels, m = confusion(x, y)
    w = max(6, max(len(str(l)) for l in labels) + 1)
    print("\n혼동행렬 (행=A, 열=B)")
    print(" " * w + "".join(f"{str(l):>{w}}" for l in labels))
    for r in labels:
        print(f"{str(r):>{w}}" + "".join(f"{m[(r,c)]:>{w}}" for c in labels))

    dis = [(i, xa, yb) for i, xa, yb in zip(ids, x, y) if xa != yb]
    print(f"\n불일치 {len(dis)}건" + (" (상위 15건)" if len(dis) > 15 else ""))
    for i, xa, yb in dis[:15]:
        print(f"  {i}: A={xa} / B={yb}")
    if args.out and dis:
        with open(args.out, "w", encoding="utf-8-sig", newline="") as f:
            w2 = csv.writer(f)
            w2.writerow(["id", "A", "B"])
            w2.writerows(dis)
        print(f"\n불일치 전량 저장: {args.out}")
        print("→ 이 파일을 논문 부록으로 공개하십시오 (Braun 2024 권고 ⑤).")


# ---------------------------------------------------------------- Krippendorff α

def krippendorff_alpha_nominal(coder_maps):
    """명목척도 Krippendorff's α. coder_maps = [{id: label}, ...]"""
    units = defaultdict(list)
    for cm in coder_maps:
        for k, v in cm.items():
            units[k].append(v)
    units = {k: v for k, v in units.items() if len(v) >= 2}
    if not units:
        return None, 0
    n_total = sum(len(v) for v in units.values())

    Do = 0.0
    for vals in units.values():
        m = len(vals)
        pairs = sum(1 for i in range(m) for j in range(m)
                    if i != j and vals[i] != vals[j])
        Do += pairs / (m - 1)
    Do /= n_total

    allv = [v for vals in units.values() for v in vals]
    c = Counter(allv)
    De = (n_total - sum(cnt * (cnt - 1) / (n_total - 1) for cnt in c.values())) \
        if n_total > 1 else 0
    De /= 1
    alpha = 1 - (Do / (De / n_total * n_total / n_total)) if De else None
    # 표준형: alpha = 1 - Do/De  (Do, De 모두 unit 평균 불일치)
    De2 = 0.0
    for l1 in c:
        for l2 in c:
            if l1 != l2:
                De2 += c[l1] * c[l2]
    De2 /= (n_total * (n_total - 1)) if n_total > 1 else 1
    alpha = 1 - (Do / De2) if De2 else None
    return alpha, len(units)


def cmd_alpha(args):
    maps = []
    for spec in args.files:
        if ":" not in spec:
            raise SystemExit(f"형식은 파일:열 입니다 — {spec}")
        path, col = spec.rsplit(":", 1)
        maps.append(load(path, col, args.key))
        print(f"  로드 {path} [{col}] → {len(maps[-1])}건")
    a, nu = krippendorff_alpha_nominal(maps)
    print(f"\n2인 이상 코딩된 항목 = {nu}")
    print(f"Krippendorff's α (nominal) = {a:.4f}   ({interpret(a)})")
    print("\n참고 실측치 — AI&Law 게재작")
    print("  Habernal et al.(2023) α_u 0.70대→0.80대")
    print("  Yamada et al.(2024)   α 0.43~0.65  ← 이 수치로도 게재됨")
    print("  Braun(2024) 29개 데이터셋 평균: Cohen κ 0.76 / Fleiss κ 0.68 / α 최고 0.78")


# ---------------------------------------------------------------- 표본크기

def cmd_samplesize(args):
    z = 1.959964
    h = args.half_width
    p = args.p
    n = (z ** 2) * p * (1 - p) / (h ** 2)
    n_fin = n
    if args.population:
        N = args.population
        n_fin = n / (1 + (n - 1) / N)
    print(f"\n비율 추정의 95% 신뢰구간 반폭 ±{h:.3f} 를 얻기 위한 표본크기")
    print(f"  가정 비율 p = {p}  (0.5 = 최악의 경우, 가장 보수적)")
    print(f"  필요 n = {math.ceil(n)}")
    if args.population:
        print(f"  유한모집단 보정 (N={args.population}) → n = {math.ceil(n_fin)}")
    print("\n참고표")
    for hh in (0.03, 0.05, 0.07, 0.10, 0.15):
        nn = (z ** 2) * 0.25 / (hh ** 2)
        print(f"  ±{hh:.0%} → n ≈ {math.ceil(nn)}")
    print("\n논문 문구 예시:")
    print(f'  "The gold subsample of n={math.ceil(n_fin if args.population else n)}')
    print(f'   was drawn by simple random sampling, sized to estimate accuracy')
    print(f'   within ±{h:.0%} at the 95% confidence level."')
    print("\n선례: Adedjouma et al. (RE'14) — \"We randomly chose 10% of the pages\"")
    print("      Egami et al. (NeurIPS 2023) — 확률표집 gold 표본으로 DSL 보정")


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="cmd", required=True)

    k = s.add_parser("kappa", help="두 라벨 간 Cohen's κ")
    k.add_argument("--a", required=True)
    k.add_argument("--a-col", required=True, dest="a_col")
    k.add_argument("--b", required=True)
    k.add_argument("--b-col", required=True, dest="b_col")
    k.add_argument("--key", default="id")
    k.add_argument("--boot", type=int, default=2000)
    k.add_argument("--out", default="data/disagreements.csv")

    a = s.add_parser("alpha", help="3인 이상 Krippendorff's α")
    a.add_argument("--files", nargs="+", required=True, metavar="파일:열")
    a.add_argument("--key", default="id")

    n = s.add_parser("samplesize", help="골드셋 크기 정당화")
    n.add_argument("--half-width", type=float, default=0.07, dest="half_width")
    n.add_argument("--p", type=float, default=0.5)
    n.add_argument("--population", type=int, default=None)

    args = p.parse_args()
    globals()[f"cmd_{args.cmd}"](args)


if __name__ == "__main__":
    main()
