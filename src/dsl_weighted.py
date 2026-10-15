#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
dsl_weighted.py — design-weighted re-analysis (added 2026-10-15; originally task_a_weighted.py, 2026-09-16)
층화 설계에 맞는 차이추정량(가중), 정규근사·층화 부트스트랩 CI, 가중 사양곡선,
가중 tipping-point, 공유 오류 민감도, 문장군 단위 민감도.

등록된 주 추정치(비가중 4.5%, 1.5–7.6)는 변경하지 않고 재생성·병기만 한다.
유료 API 호출 없음 — 저장된 패널 출력(data/panel/labels_T*_full.csv)만 사용.
"""
import csv, json, math, random, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"; PANEL = DATA / "panel"
OUT = ROOT / "output" / "tables" / "weighted"; OUT.mkdir(parents=True, exist_ok=True)
TESTS = [f"T{i}" for i in range(1, 8)]
SEED_BOOT = 20260916; B = 2000

def rd(p): return list(csv.DictReader(open(p, encoding="utf-8-sig", newline="")))
def err(l1): return 0 if l1 == "위임" else 1
def skey(api, form): return (api, form or "없음")

# ---------- population
pop = rd(PANEL / "panel_input.csv")
N = len(pop)
pop_stratum = {r["id"]: skey(r["API_위임구분"], r["자동추출_위임형식"]) for r in pop}
Nh = Counter(pop_stratum.values())
labels = {t: {r["id"]: r[f"{t}_L1"] for r in rd(PANEL / f"labels_{t}_full.csv")} for t in TESTS}
ids = sorted(labels["T1"])
assert len(ids) == N == 7558

def majority(rid, tests, undec_as=None):
    v = []
    for t in tests:
        l = labels[t].get(rid, "판단불가")
        v.append(err(l) if (undec_as is None or l != "판단불가") else undec_as)
    return 1 if sum(v) * 2 > len(v) else 0

# ---------- calibration sample
gold = rd(DATA / "labels" / "goldset_labeled_v2.csv")
cmap = {r["gold_id"]: r["panel_id"] for r in rd(PANEL / "calibration_map.csv")}
cal = []
for g in gold:
    gl = g["L1_위임인가"].strip()
    assert gl
    pid = cmap[g["id"]]
    st = skey(g["API_위임구분"], g["자동추출_위임형식"])
    assert pop_stratum[pid] == st, (g["id"], pid)
    cal.append({"gid": g["id"], "pid": pid, "stratum": st, "y": err(gl), "human_L1": gl,
                "sentence": g["조문문장"].strip(), "law": g["상위법령명"], "art": g["상위조문번호"]})
n = len(cal); assert n == 200
nh = Counter(c["stratum"] for c in cal)

# ---------- A1 strata table
rows = []
for st in sorted(Nh, key=lambda k: -Nh[k]):
    w = Nh[st] / N
    rows.append({"stratum_api_link_type": st[0], "stratum_prescribed_form": st[1],
                 "N_h": Nh[st], "n_h": nh.get(st, 0), "W_h=N_h/N": round(w, 6),
                 "pi_h=n_h/N_h": round(nh.get(st, 0) / Nh[st], 6),
                 "weight_per_record=N_h/(N*n_h)": round(w / nh[st], 6) if nh.get(st) else "",
                 "unweighted_per_record=1/n": round(1 / n, 6),
                 "oversampled_x3": "Y" if st[1] in ("미특정", "없음") else "",
                 "census(N_h=1)": "Y" if Nh[st] == 1 else ""})
with open(OUT / "strata_table.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)

# ---------- estimators
def surrogate(tests=TESTS, undec_as=None):
    return {rid: majority(rid, tests, undec_as) for rid in ids}

def collapse_groups(min_n=2):
    """분산 추정용 층 병합: n_h < min_n 인 층을 하나의 병합층으로. 점추정은 원 층 그대로."""
    grp = {}
    for st in Nh:
        grp[st] = st if nh.get(st, 0) >= min_n else ("collapsed_rare", "")
    return grp

GRP = collapse_groups()

def strat_diff(y_of, m_of, cal_rows=cal, weighted=True):
    """층화 차이추정: M̄ + Σ W_h d̄_h ; 분산 Σ W_h²(1−n_h/N_h)s²_h/n_h (병합층 사용)."""
    Mbar = sum(m_of[rid] for rid in ids) / N
    d = defaultdict(list)
    for c in cal_rows:
        d[c["stratum"]].append(y_of(c) - m_of[c["pid"]])
    if weighted:
        corr = sum((Nh[st] / N) * (sum(v) / len(v)) for st, v in d.items())
    else:
        allv = [x for v in d.values() for x in v]
        corr = sum(allv) / len(allv)
    # variance
    if weighted:
        gd = defaultdict(list); gN = Counter();
        for st, v in d.items():
            g = GRP[st]; gd[g].extend(v)
        for st in Nh:
            gN[GRP[st]] += Nh[st]
        var = 0.0
        for g, v in gd.items():
            k = len(v);
            if k < 2: continue
            mu = sum(v) / k; s2 = sum((x - mu) ** 2 for x in v) / (k - 1)
            fpc = 1 - k / gN[g]
            var += (gN[g] / N) ** 2 * fpc * s2 / k
    else:
        allv = [x for v in d.values() for x in v]; k = len(allv); mu = sum(allv) / k
        var = sum((x - mu) ** 2 for x in allv) / (k - 1) / k
    se = math.sqrt(var)
    return {"Mbar": Mbar, "corr": corr, "est": Mbar + corr, "se": se,
            "ci_lo": Mbar + corr - 1.96 * se, "ci_hi": Mbar + corr + 1.96 * se}

def strat_boot(y_of, m_of, cal_rows=cal, weighted=True, B=B, seed=SEED_BOOT):
    rng = random.Random(seed)
    Mbar = sum(m_of[rid] for rid in ids) / N
    bystr = defaultdict(list)
    for c in cal_rows: bystr[c["stratum"]].append(c)
    # 부트스트랩 재표집은 병합층 안에서(n_h=1 층은 재표집 불가)
    bygrp = defaultdict(list); gN = Counter()
    for st, v in bystr.items(): bygrp[GRP[st]].extend(v)
    for st in Nh: gN[GRP[st]] += Nh[st]
    ests = []
    for _ in range(B):
        corr = 0.0
        for g, v in bygrp.items():
            samp = [rng.choice(v) for _ in v]
            if weighted:
                if g[0] == "collapsed_rare":
                    # 병합층: 병합 가중치 × 병합 표본평균
                    corr += (gN[g] / N) * sum(y_of(c) - m_of[c["pid"]] for c in samp) / len(samp)
                else:
                    corr += (Nh[g] / N) * sum(y_of(c) - m_of[c["pid"]] for c in samp) / len(samp)
            else:
                corr += sum(y_of(c) - m_of[c["pid"]] for c in samp) / n
        ests.append(Mbar + corr)
    ests.sort()
    return ests[int(0.025 * B)], ests[int(0.975 * B) - 1]

def strat_mean(y_of, cal_rows=cal):
    """인간 라벨 단독 가중 유병률 + 설계 분산."""
    by = defaultdict(list)
    for c in cal_rows: by[c["stratum"]].append(y_of(c))
    est = sum((Nh[st] / N) * sum(v) / len(v) for st, v in by.items())
    gd = defaultdict(list); gN = Counter()
    for st, v in by.items(): gd[GRP[st]].extend(v)
    for st in Nh: gN[GRP[st]] += Nh[st]
    var = 0.0
    for g, v in gd.items():
        k = len(v)
        if k < 2: continue
        mu = sum(v) / k; s2 = sum((x - mu) ** 2 for x in v) / (k - 1)
        var += (gN[g] / N) ** 2 * (1 - k / gN[g]) * s2 / k
    se = math.sqrt(var)
    return est, se, est - 1.96 * se, est + 1.96 * se

def wilson(k, nn, z=1.96):
    p = k / nn; d = 1 + z * z / nn; c = p + z * z / (2 * nn)
    h = z * math.sqrt(p * (1 - p) / nn + z * z / (4 * nn * nn))
    return (c - h) / d, (c + h) / d

Y = lambda c: c["y"]
M7 = surrogate(); M6 = surrogate(TESTS[:6])
M7_ud = surrogate(undec_as=0); M7_un = surrogate(undec_as=1)

res = []
def add(name, weighted, m_of, y_of=Y, note=""):
    r = strat_diff(y_of, m_of, weighted=weighted)
    lo, hi = strat_boot(y_of, m_of, weighted=weighted)
    res.append({"specification": name, "weighting": "stratified (N_h/N)" if weighted else "unweighted (registered)",
                "surrogate_mean_Mbar": round(r["Mbar"], 5), "correction": round(r["corr"], 5),
                "estimate": round(r["est"], 5), "se_normal": round(r["se"], 5),
                "ci95_normal_lo": round(r["ci_lo"], 5), "ci95_normal_hi": round(r["ci_hi"], 5),
                "ci95_boot_lo": round(lo, 5), "ci95_boot_hi": round(hi, 5),
                "numerator_denominator": f"Mbar={sum(m_of.values())}/{N}; corr from n={n} calibration records",
                "note": note})
    return r

r_unw = add("DSL primary (K=7 majority)", False, M7, note="등록 주 추정치 재생성(변경 없음)")
r_w = add("DSL primary (K=7 majority)", True, M7)
add("DSL excl. T7 (K=6)", False, M6); add("DSL excl. T7 (K=6)", True, M6)
add("undecidable→delegation (extreme)", False, M7_ud); add("undecidable→delegation (extreme)", True, M7_ud)
add("undecidable→non-delegation (extreme = registered convention)", False, M7_un); add("undecidable→non-delegation (extreme = registered convention)", True, M7_un)
# human-only prevalence
k_h = sum(c["y"] for c in cal)
wl, wh = wilson(k_h, n)
res.append({"specification": "human-only prevalence (calibration sample)", "weighting": "unweighted (Wilson)",
            "surrogate_mean_Mbar": "", "correction": "", "estimate": round(k_h / n, 5), "se_normal": "",
            "ci95_normal_lo": round(wl, 5), "ci95_normal_hi": round(wh, 5), "ci95_boot_lo": "", "ci95_boot_hi": "",
            "numerator_denominator": f"{k_h}/{n}", "note": "Section 4.4 sample bound 3.5% (1.7–7.0)"})
he, hse, hlo, hhi = strat_mean(Y)
# bootstrap for human-only weighted
rng = random.Random(SEED_BOOT); bystr = defaultdict(list)
for c in cal: bystr[c["stratum"]].append(c)
bygrp = defaultdict(list); gN = Counter()
for st, v in bystr.items(): bygrp[GRP[st]].extend(v)
for st in Nh: gN[GRP[st]] += Nh[st]
bs = []
for _ in range(B):
    e = 0.0
    for g, v in bygrp.items():
        samp = [rng.choice(v) for _ in v]
        e += (gN[g] / N) * sum(c["y"] for c in samp) / len(samp)
    bs.append(e)
bs.sort()
res.append({"specification": "human-only prevalence (calibration sample)", "weighting": "stratified (N_h/N)",
            "surrogate_mean_Mbar": "", "correction": "", "estimate": round(he, 5), "se_normal": round(hse, 5),
            "ci95_normal_lo": round(max(hlo, 0), 5), "ci95_normal_hi": round(hhi, 5),
            "ci95_boot_lo": round(bs[int(0.025 * B)], 5), "ci95_boot_hi": round(bs[int(0.975 * B) - 1], 5),
            "numerator_denominator": f"{k_h}/{n} records, weighted by N_h/(N n_h)", "note": "design-based CI (collapsed rare strata)"})
# population-level spec-curve items unaffected by weighting (census)
dsl = json.load(open(PANEL / "dsl_results_full.json"))
for k, v in dsl["spec_curve"].items():
    if k.startswith("DSL"): continue
    res.append({"specification": f"spec curve: {k}", "weighting": "n/a (population census, no calibration term)",
                "surrogate_mean_Mbar": "", "correction": "", "estimate": v, "se_normal": "", "ci95_normal_lo": "",
                "ci95_normal_hi": "", "ci95_boot_lo": "", "ci95_boot_hi": "",
                "numerator_denominator": f"N={N}", "note": "from data/panel/dsl_results_full.json (unchanged)"})
with open(OUT / "weighted_estimates.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(res[0])); w.writeheader(); w.writerows(res)

# ---------- A3(d) tipping point, weighted
disc = [c for c in cal if c["y"] != M7[c["pid"]]]
def wrec(c): return Nh[c["stratum"]] / (N * nh[c["stratum"]])
pat = defaultdict(list)
for c in disc: pat[c["sentence"]].append(c)
tip = []
def est_after(flip_set):
    y_of = lambda c: (1 - c["y"]) if c["gid"] in flip_set else c["y"]
    return strat_diff(y_of, M7, weighted=False)["est"], strat_diff(y_of, M7, weighted=True)["est"]
pop_sentence = Counter(r["조문문장"].strip() for r in pop)
for s, cs in sorted(pat.items(), key=lambda kv: -len(kv[1])):
    fl = {c["gid"] for c in cs}
    eu, ew = est_after(fl)
    tip.append({"direction": "author over-called delegation (human=delegation, panel=non)" if cs[0]["y"] == 0 else "author under-called delegation",
                "sentence_pattern": s, "records_in_calibration": len(cs), "strata": "; ".join(f"{c['stratum'][0]}/{c['stratum'][1]}" for c in cs),
                "identical_sentences_in_population": pop_sentence[s],
                "shift_per_record_unweighted_pp": 0.5, "shift_per_record_weighted_pp": "; ".join(f"{100*wrec(c):.3f}" for c in cs),
                "estimate_unweighted": round(eu, 5), "estimate_weighted": round(ew, 5)})
# all discordant
eu, ew = est_after({c["gid"] for c in disc if c["y"] == 0})
tip.append({"direction": "author over-called delegation — ALL discordant delegation calls flipped", "sentence_pattern": "(all)",
            "records_in_calibration": sum(1 for c in disc if c["y"] == 0), "strata": "", "identical_sentences_in_population": "",
            "shift_per_record_unweighted_pp": 0.5, "shift_per_record_weighted_pp": "", "estimate_unweighted": round(eu, 5), "estimate_weighted": round(ew, 5)})
# reverse: all 7 human non-delegation calls wrong
nond = [c for c in cal if c["y"] == 1]
eu, ew = est_after({c["gid"] for c in nond})
tip.append({"direction": "author under-called delegation — ALL 7 non-delegation calls flipped", "sentence_pattern": "(all 7)",
            "records_in_calibration": len(nond), "strata": "; ".join(f"{c['stratum'][0]}/{c['stratum'][1]}" for c in nond),
            "identical_sentences_in_population": "", "shift_per_record_unweighted_pp": 0.5,
            "shift_per_record_weighted_pp": "; ".join(f"{100*wrec(c):.3f}" for c in nond), "estimate_unweighted": round(eu, 5), "estimate_weighted": round(ew, 5)})
for c in nond:
    eu, ew = est_after({c["gid"]})
    tip.append({"direction": "author under-called delegation (single record)", "sentence_pattern": c["sentence"], "records_in_calibration": 1,
                "strata": f"{c['stratum'][0]}/{c['stratum'][1]}", "identical_sentences_in_population": pop_sentence[c["sentence"]],
                "shift_per_record_unweighted_pp": 0.5 if M7[c["pid"]] == 1 else -0.5,
                "shift_per_record_weighted_pp": f"{100*wrec(c):.3f}", "estimate_unweighted": round(eu, 5), "estimate_weighted": round(ew, 5)})
with open(OUT / "tipping_weighted.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(tip[0])); w.writeheader(); w.writerows(tip)

# ---------- A4 shared-error sensitivity
conc_del = [c for c in cal if c["y"] == 0 and M7[c["pid"]] == 0]
conc_non = [c for c in cal if c["y"] == 1 and M7[c["pid"]] == 1]
sh_u_del = len(conc_del) / n; sh_w_del = sum(wrec(c) for c in conc_del)
sh_u_non = len(conc_non) / n; sh_w_non = sum(wrec(c) for c in conc_non)
se_rows = []
for p in (0.005, 0.01, 0.02, 0.05):
    se_rows.append({"assumed_shared_error_rate_in_concordant_records": p, "direction": "both wrongly call delegation (true = non-delegation) → estimate rises",
                    "concordant_records_affected": f"{len(conc_del)}/{n} concordant-delegation records (weighted share {sh_w_del:.4f})",
                    "expected_shift_unweighted_pp": round(100 * p * sh_u_del, 3), "expected_shift_weighted_pp": round(100 * p * sh_w_del, 3),
                    "estimate_unweighted": round(r_unw["est"] + p * sh_u_del, 5), "estimate_weighted": round(r_w["est"] + p * sh_w_del, 5),
                    "note": "sensitivity analysis, not an error-rate estimate"})
    se_rows.append({"assumed_shared_error_rate_in_concordant_records": p, "direction": "both wrongly call non-delegation (true = delegation) → estimate falls",
                    "concordant_records_affected": f"{len(conc_non)}/{n} concordant-non-delegation records (weighted share {sh_w_non:.4f})",
                    "expected_shift_unweighted_pp": round(-100 * p * sh_u_non, 3), "expected_shift_weighted_pp": round(-100 * p * sh_w_non, 3),
                    "estimate_unweighted": round(r_unw["est"] - p * sh_u_non, 5), "estimate_weighted": round(r_w["est"] - p * sh_w_non, 5),
                    "note": "sensitivity analysis, not an error-rate estimate"})
with open(OUT / "shared_error_sensitivity.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(se_rows[0])); w.writeheader(); w.writerows(se_rows)

# ---------- A5 sentence-group sensitivity
groups = defaultdict(list)
for c in cal: groups[c["sentence"]].append(c)
sizes = Counter(len(v) for v in groups.values())
sg = []
for s, cs in groups.items():
    fl = {c["gid"] for c in cs}
    eu, ew = est_after(fl)
    sg.append({"sentence": s, "group_size": len(cs), "human_labels": "/".join(sorted(set(c["human_L1"] for c in cs))),
               "panel_majority_err": "/".join(str(M7[c["pid"]]) for c in cs), "discordant_in_group": sum(1 for c in cs if c["y"] != M7[c["pid"]]),
               "identical_sentences_in_population": pop_sentence[s],
               "estimate_if_whole_group_flipped_unweighted": round(eu, 5), "estimate_if_whole_group_flipped_weighted": round(ew, 5),
               "leaves_1.7–7.0_unweighted": "Y" if (eu < 0.017 or eu > 0.070) else "", "leaves_1.7–7.0_weighted": "Y" if (ew < 0.017 or ew > 0.070) else ""})
sg.sort(key=lambda r: -abs(r["estimate_if_whole_group_flipped_unweighted"] - r_unw["est"]))
with open(OUT / "sentence_group_sensitivity.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sg[0])); w.writeheader(); w.writerows(sg)

summary = {"N": N, "n": n, "n_strata": len(Nh), "collapsed_strata_for_variance": [f"{k[0]}/{k[1]}" for k in Nh if GRP[k][0] == "collapsed_rare"],
           "unweighted_primary": {k: round(v, 5) for k, v in r_unw.items()}, "weighted_primary": {k: round(v, 5) for k, v in r_w.items()},
           "discordant": len(disc), "concordant_delegation": len(conc_del), "concordant_nondelegation": len(conc_non),
           "sentence_groups": len(groups), "group_size_distribution": dict(sorted(sizes.items())),
           "groups_that_flip_outside_1.7-7.0_unweighted": sum(1 for r in sg if r["leaves_1.7–7.0_unweighted"]),
           "groups_that_flip_outside_1.7-7.0_weighted": sum(1 for r in sg if r["leaves_1.7–7.0_weighted"]),
           "A6_diff_pp": round(100 * (r_w["est"] - r_unw["est"]), 3),
           "A6_within_0.5pp": abs(r_w["est"] - r_unw["est"]) <= 0.005,
           "A6_CIs_overlap": not (r_w["ci_hi"] < r_unw["ci_lo"] or r_unw["ci_hi"] < r_w["ci_lo"])}
json.dump(summary, open(OUT / "task_a_summary.json", "w"), ensure_ascii=False, indent=2)
print(json.dumps(summary, ensure_ascii=False, indent=2))
