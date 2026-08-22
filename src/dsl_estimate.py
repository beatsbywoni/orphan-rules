#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dsl_estimate.py — Phase 3: 설계기반 주 추정 + 사양 곡선 (OSF 등록 osf.io/[OSF registration; identifier withheld for double-blind review] §1 이행)

주 추정량 (등록 §1, 변경 불가):
  p̂ = mean_N(대리 오류지표) + mean_n(인간 지표 − 대리 지표)
  대리 지표 = K=7 패널 다수결의 1{L1 ≠ 위임},  보정표본 n=200 (2026-08-15 동결)
  95% CI = 차이항 분산 기반 (모집단 항은 전수라 표집분산 0)

감도분석 (사양 곡선; 어떤 것도 주 추정량을 대체할 수 없음):
  (a) 무보정 다수결  (b) 계열축약 3검사 독립 LCM  (c) 4-클래스 의존 LCM
  (+) T7 제외 6검사 DSL — deviation_log D-2의 강건성 약속

사용
  python src/dsl_estimate.py match                # 보정표본 G#### ↔ 전수 P#### 매핑
  python src/dsl_estimate.py dsl --scope full     # 주 추정 + 사양 곡선 + 일치도 표
  python src/dsl_estimate.py dsl --scope pilot    # 파이프라인 예행 (파일럿 라벨)
"""

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PANEL = DATA / "panel"

TESTS = [f"T{i}" for i in range(1, 8)]
MATCH_KEYS = ["상위법령명", "상위조문번호", "조문문장", "대상명", "API_위임구분"]
# goldset의 열 이름은 동일. panel_input의 API_위임구분도 동일 열명.


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _key(row):
    return tuple((row.get(k) or "").strip() for k in MATCH_KEYS)


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - h) / d, (c + h) / d)


# ---------------------------------------------------------------- match
def cmd_match(args):
    gold = _read(DATA / "goldset_to_label.csv")
    pop = _read(PANEL / "panel_input.csv")
    pool = defaultdict(list)
    for r in pop:
        pool[_key(r)].append(r["id"])
    out, misses, ambiguous = [], 0, 0
    for g in gold:
        ids = pool.get(_key(g), [])
        if not ids:
            misses += 1
            out.append({"gold_id": g["id"], "panel_id": "", "n_candidates": 0})
            continue
        if len(ids) > 1:
            ambiguous += 1
        out.append({"gold_id": g["id"], "panel_id": ids.pop(0),
                    "n_candidates": len(ids) + 1})
    path = PANEL / "calibration_map.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["gold_id", "panel_id", "n_candidates"])
        w.writeheader(); w.writerows(out)
    print(f"매핑 {len(out)}건 → {path}  (미매칭 {misses}, 복수후보 {ambiguous})")
    if misses:
        print("※ 미매칭이 있으면 dsl 단계가 중단됩니다. 원인 확인 필요.")


# ---------------------------------------------------------------- LCM (감도)
def lcm2_em(y, iters=300, seed=0):
    """2-클래스 독립 LCM (EM, 순수 파이썬). y: list[tuple[int,...]] (0/1)."""
    rng = random.Random(seed)
    k = len(y[0])
    pi = 0.9
    th1 = [0.95 + rng.random() * 0.02 for _ in range(k)]   # P(y=1|z=1)
    th0 = [0.03 + rng.random() * 0.02 for _ in range(k)]   # P(y=1|z=0)
    for _ in range(iters):
        s_w = 0.0; s_wy = [0.0] * k; s_vy = [0.0] * k; n = len(y)
        for row in y:
            l1 = math.log(pi + 1e-12); l0 = math.log(1 - pi + 1e-12)
            for j, v in enumerate(row):
                l1 += math.log(th1[j] if v else 1 - th1[j])
                l0 += math.log(th0[j] if v else 1 - th0[j])
            m = max(l1, l0)
            w = math.exp(l1 - m) / (math.exp(l1 - m) + math.exp(l0 - m))
            s_w += w
            for j, v in enumerate(row):
                if v:
                    s_wy[j] += w; s_vy[j] += (1 - w)
        pi = min(max(s_w / n, 1e-6), 1 - 1e-6)
        for j in range(k):
            th1[j] = min(max(s_wy[j] / max(s_w, 1e-9), 1e-4), 1 - 1e-4)
            th0[j] = min(max(s_vy[j] / max(n - s_w, 1e-9), 1e-4), 1 - 1e-4)
    # z=1 = '검사들이 주로 1' 쪽 정렬
    if sum(th1) < sum(th0):
        pi = 1 - pi
    return pi


def lcm4_em(y, iters=300, seed=0):
    """4-클래스 (진리×난이도) 혼합 EM — lcm_sim2.py 이식 (순수 파이썬)."""
    rng = random.Random(seed)
    k = len(y[0])
    pi = [0.85, 0.08, 0.05, 0.02]
    base = [(0.99,), (0.70,), (0.01,), (0.30,)]
    th = [[min(max(b[0] + (rng.random() - .5) * 0.02, 1e-4), 1 - 1e-4)
           for _ in range(k)] for b in base]
    for _ in range(iters):
        s_w = [0.0] * 4
        s_wy = [[0.0] * k for _ in range(4)]
        for row in y:
            ls = []
            for c in range(4):
                l = math.log(pi[c] + 1e-12)
                for j, v in enumerate(row):
                    l += math.log(th[c][j] if v else 1 - th[c][j])
                ls.append(l)
            m = max(ls)
            ws = [math.exp(l - m) for l in ls]
            tot = sum(ws)
            for c in range(4):
                w = ws[c] / tot
                s_w[c] += w
                for j, v in enumerate(row):
                    if v:
                        s_wy[c][j] += w
        n = len(y)
        pi = [min(max(s / n, 1e-6), None or 1) for s in s_w]
        t = sum(pi); pi = [p / t for p in pi]
        for c in range(4):
            for j in range(k):
                th[c][j] = min(max(s_wy[c][j] / max(s_w[c], 1e-9), 1e-4), 1 - 1e-4)
    prev = pi[0] + pi[1]
    if (sum(th[0]) + sum(th[1])) < (sum(th[2]) + sum(th[3])):
        prev = 1 - prev
    return prev


# ---------------------------------------------------------------- dsl
def _err(l1):
    """오류지표: 1{L1 ≠ 위임} (인용·판단불가 = 비위임; 등록 RQ1과 동일)."""
    return 0 if l1 == "위임" else 1


def cmd_dsl(args):
    scope = args.scope
    labels = {}
    for t in TESTS:
        p = PANEL / f"labels_{t}_{scope}.csv"
        if not p.exists():
            sys.exit(f"{p} 없음.")
        labels[t] = {r["id"]: r[f"{t}_L1"] for r in _read(p)}
    ids = sorted(labels["T1"].keys())
    N = len(ids)

    def majority(rid, tests):
        votes = [_err(labels[t].get(rid, "판단불가")) for t in tests]
        return 1 if sum(votes) * 2 > len(votes) else 0

    surr = {rid: majority(rid, TESTS) for rid in ids}
    surr_mean = sum(surr.values()) / N

    # 보정표본
    gold = {r["id"]: r for r in _read(DATA / "goldset_labeled_v2.csv")}
    if scope == "full":
        cmap = {r["gold_id"]: r["panel_id"] for r in _read(PANEL / "calibration_map.csv")}
        if any(not v for v in cmap.values()):
            sys.exit("calibration_map에 미매칭 존재 — match 단계 확인.")
    else:
        cmap = {gid: gid for gid in gold}   # 파일럿: 같은 id 공간

    diffs = []
    for gid, g in gold.items():
        gl = (g.get("L1_위임인가") or "").strip()
        if not gl:
            continue
        h = _err(gl)
        s = surr[cmap[gid]] if cmap[gid] in surr else None
        if s is None:
            sys.exit(f"보정표본 {gid}→{cmap[gid]} 대리 라벨 없음.")
        diffs.append(h - s)
    n = len(diffs)
    corr = sum(diffs) / n
    p_hat = surr_mean + corr
    var_d = sum((d - corr) ** 2 for d in diffs) / (n - 1)
    se = math.sqrt(var_d / n)
    ci = (p_hat - 1.96 * se, p_hat + 1.96 * se)

    # 사양 곡선 — LCM 입력은 lcm_sim과 동일하게 '위임 지표'(다수 클래스=1)로 정렬:
    # y=1{위임}, prev=P(진짜 위임) 추정 → 오류율 = 1 − prev.
    maj_only = surr_mean
    y7 = [tuple(1 - _err(labels[t][rid]) for t in TESTS) for rid in ids]
    fam = []
    for rid in ids:
        a = 1 - majority(rid, ["T1", "T2", "T3"])
        o = 1 - majority(rid, ["T4", "T5", "T6"])
        r7 = 1 - _err(labels["T7"][rid])
        fam.append((a, o, r7))
    lcm3 = lcm2_em(fam, seed=1)
    lcm4 = lcm4_em(y7, seed=1)
    # 강건성: T7 제외 6검사 DSL (deviation_log D-2)
    surr6 = {rid: majority(rid, TESTS[:6]) for rid in ids}
    corr6 = sum((_err((gold[g].get("L1_위임인가") or "").strip() or "판단불가")
                 - surr6[cmap[g]]) for g in gold
                if (gold[g].get("L1_위임인가") or "").strip()) / n
    dsl6 = sum(surr6.values()) / N + corr6

    # 극단 대치 (판단불가 → 위임 / 비위임). 등록 missing-data 조항: *주 추정치를*
    # 양 극단에서 재계산해 구간을 보고한다 → 대리 평균과 DSL을 모두 산출.
    def extreme(as_err):
        def s_(rid):
            v = [(_err(labels[t][rid]) if labels[t][rid] != "판단불가" else as_err)
                 for t in TESTS]
            return 1 if sum(v) * 2 > len(v) else 0
        sm = sum(s_(r) for r in ids) / N
        dd = [(_err((gold[g].get("L1_위임인가") or "").strip()) - s_(cmap[g]))
              for g in gold if (gold[g].get("L1_위임인가") or "").strip()]
        cc = sum(dd) / len(dd)
        vv = sum((x - cc) ** 2 for x in dd) / (len(dd) - 1)
        se_ = math.sqrt(vv / len(dd))
        return {"surrogate": round(sm, 5), "dsl": round(sm + cc, 5),
                "ci95": [round(sm + cc - 1.96 * se_, 5), round(sm + cc + 1.96 * se_, 5)]}
    ext = {"undecidable_as_delegation": extreme(0),
           "undecidable_as_nondelegation": extreme(1)}

    # 검사별 일치도 (보정표본)
    per_test = {}
    for t in TESTS:
        k_agree = 0
        for gid, g in gold.items():
            gl = (g.get("L1_위임인가") or "").strip()
            if not gl:
                continue
            k_agree += _err(gl) == _err(labels[t].get(cmap[gid], "판단불가"))
        lo, hi = wilson(k_agree, n)
        per_test[t] = {"agree": k_agree / n, "wilson95": [round(lo, 4), round(hi, 4)]}

    res = {
        "scope": scope, "N": N, "n_calibration": n,
        "primary_DSL": {"estimate": round(p_hat, 5), "se": round(se, 5),
                        "ci95": [round(ci[0], 5), round(ci[1], 5)],
                        "surrogate_mean": round(surr_mean, 5),
                        "correction": round(corr, 5)},
        "spec_curve": {"majority_uncorrected": round(maj_only, 5),
                       "family_collapsed_LCM3": round(1 - lcm3, 5),
                       "dependence_LCM4": round(1 - lcm4, 5),
                       "DSL_excl_T7": round(dsl6, 5)},
        "undecidable_extremes": ext,
        "per_test_agreement": per_test,
    }
    out = PANEL / f"dsl_results_{scope}.json"
    out.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"\n→ {out}")
    spread = [res["spec_curve"][k] for k in res["spec_curve"]] + [res["primary_DSL"]["estimate"]]
    if max(spread) - min(spread) > 0.02:
        print("※ 사양곡선-주추정 괴리 >2pp — 등록 §4: 발견으로 보고(추정량 교체 금지).")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("match").set_defaults(func=cmd_match)
    d = sub.add_parser("dsl")
    d.add_argument("--scope", choices=["pilot", "full"], default="full")
    d.set_defaults(func=cmd_dsl)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
