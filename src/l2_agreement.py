#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""l2_agreement.py — reproduce the form-label (L2) agreement figures of Table 2 / Table S1.1 (added 2026-10-16).

Scoring (author ↔ GPT-4o second annotator):
  * items: the 196 calibration records on which the L1 (delegation) label agreed;
  * author form set = L2_위임된법형식 ∪ L2_병존형식 (full recorded set, co-listed and out-of-list forms included);
    an empty author set (undecidable items) is scored as {해당없음};
  * exact set match → Cohen's κ with 2,000-resample bootstrap (functions from retest_kappa.py);
  * intersection agreement (registered criterion) reported as a raw rate only.
Also prints: the closed-value-list variant (out-of-list forms dropped) for comparison, the constant marker extractor's L1 κ,
and the August (3-day) re-test L2 figures (exact set match and primary form).
Run from the repository root: python src/l2_agreement.py
"""
import csv, sys
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))
from retest_kappa import as_set, agreement_stats  # noqa: E402

CLOSED = {"대통령령", "부령", "고시", "훈령", "예규", "조례", "교육규칙", "미특정", "해당없음"}
orig = {r["id"]: r for r in csv.DictReader(open(ROOT / "data/labels/goldset_labeled_v2.csv", encoding="utf-8-sig"))}
llm = {r["id"]: r for r in csv.DictReader(open(ROOT / "data/labels/goldset_llm.csv", encoding="utf-8-sig"))}

def author_set(i, closed_only=False):
    s = as_set(orig[i]["L2_위임된법형식"]) | as_set(orig[i].get("L2_병존형식", ""))
    if closed_only: s = frozenset(x for x in s if x in CLOSED)
    return s if s else frozenset({"해당없음"})

ids = [i for i in orig if orig[i]["L1_위임인가"].strip() == llm[i]["LLM_L1"].strip()]
def fmt(st): return f"n={st['n']} agree={st['agree']:.4f} kappa={st['kappa']:.4f} CI=({st['ci'][0]:.3f},{st['ci'][1]:.3f})"
full = agreement_stats([(author_set(i), as_set(llm[i]["LLM_L2"])) for i in ids], "L2 exact, full form sets")
inter = agreement_stats([(author_set(i), as_set(llm[i]["LLM_L2"])) for i in ids], "L2 intersection", intersection=True)
closed = agreement_stats([(author_set(i, True), as_set(llm[i]["LLM_L2"])) for i in ids], "L2 exact, closed list only")
print("author ↔ GPT-4o, L1-concordant items")
print("  exact set match, full recorded sets (REPORTED):", fmt(full), "| disagreements:", [ids[k] for k, _, _ in full["disagreements"]])
print("  intersection agreement (registered criterion, raw rate):", f"{inter['agree']:.4f}")
print("  exact set match, closed value list only (comparison):", fmt(closed))

# marker extractor: constant 'delegation' prediction vs author L1
pairs = [(orig[i]["L1_위임인가"].strip(), "위임") for i in orig]
m = agreement_stats(pairs, "marker L1")
print("author ↔ marker extractor, L1:", f"agree={m['agree']:.3f} kappa={m['kappa']:.3f} (observed = chance agreement; κ is 0, not undefined)")

# August (3-day) re-test, L2
aug = list(csv.DictReader(open(ROOT / "data/labels/goldset_retest_0818.csv", encoding="utf-8-sig")))
ids2 = [r["id"] for r in aug if orig[r["id"]]["L1_위임인가"].strip() == "위임" and r["L1_위임인가"].strip() == "위임"]
by = {r["id"]: r for r in aug}
ex = agreement_stats([(author_set(i), as_set(by[i]["L2_위임된법형식"])) for i in ids2], "Aug L2 exact")
pr = agreement_stats([(as_set(orig[i]["L2_위임된법형식"]), as_set(by[i]["L2_위임된법형식"])) for i in ids2], "Aug L2 primary")
it = agreement_stats([(author_set(i), as_set(by[i]["L2_위임된법형식"])) for i in ids2], "Aug L2 inter", intersection=True)
print("August re-test, L2 (both passes delegation):")
print("  exact set match:", fmt(ex)); print("  primary form only:", fmt(pr)); print("  intersection agreement (raw):", f"{it['agree']:.4f}")
