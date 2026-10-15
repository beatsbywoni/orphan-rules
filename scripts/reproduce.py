#!/usr/bin/env python3
"""reproduce.py — regenerate the paper's reported estimates from stored outputs only (no network, no API key).

Run from the repository root:  python scripts/reproduce.py

Steps (all deterministic; see REPRODUCE.md for the full list of numbers each one yields):
  1. src/dsl_estimate.py dsl --scope full   -> registered unweighted DSL estimate 4.54% (1.51–7.57), spec curve, undecidable sensitivity
  2. src/dsl_weighted.py                    -> design-weighted (stratified) estimates: 4.25% (1.13–7.37; bootstrap 1.06–7.41),
                                               human-only weighted 2.26% (0.44–4.08), panel-undecidable-as-delegation 1.88% (0.43–3.33),
                                               strata table (Table S3.3), weighted tipping points, shared-error and sentence-group sensitivity
  3. src/retest_kappa.py                    -> intra-annotator re-test agreement (Table 2)
  3b. src/l2_agreement.py                   -> form-label agreement (Table 2 row 2 / S1.1), scoring scope stated
  4. counts from data/labels/claim_check_labeled.csv (analysis_label)      -> Table 4: a 10 / b 7 / c 3
  5. counts from data/labels/findings_D1_triage_v3.csv                     -> Table 3: 149 -> 7 / 4 / 138 = 61 + 77
  6. (only if data/edges.jsonl and data/admrules.jsonl from the Zenodo deposit are present) src/resolve_rule_ids.py
                                               -> identifier resolution 72/280, 194 cumulative, 38/144; matching sensitivity 211 vs 149
Figures: python src/make_figures.py (requires matplotlib).
"""
import subprocess, sys, csv, json
from collections import Counter
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
def run(*args):
    print("\n$ python", *args); subprocess.run([sys.executable, *args], cwd=ROOT, check=True)
run("src/dsl_estimate.py", "dsl", "--scope", "full")
run("src/dsl_weighted.py")
run("src/retest_kappa.py")
run("src/l2_agreement.py")
rows = list(csv.DictReader(open(ROOT / "data/labels/claim_check_labeled.csv", encoding="utf-8-sig")))
print("\nTable 4 (claim_check analysis_label):", dict(Counter(r["analysis_label"] for r in rows)))
w = list(csv.DictReader(open(ROOT / "output/tables/weighted/weighted_estimates.csv", encoding="utf-8-sig")))
for r in w[:2] + [x for x in w if x["specification"].startswith("undecidable→delegation") and x["weighting"].startswith("strat")]:
    print(f'{r["specification"]:45s} {r["weighting"]:28s} {float(r["estimate"])*100:.2f}% ({float(r["ci95_normal_lo"])*100:.2f}–{float(r["ci95_normal_hi"])*100:.2f})')
tri = list(csv.DictReader(open(ROOT / "data/labels/findings_D1_triage_v3.csv", encoding="utf-8-sig")))
t1 = Counter(r["T1_규범성격"] for r in tri)
print(f"\nTable 3 (findings_D1_triage_v3 T1): {len(tri)} candidates -> cross-ministry {t1.get('해당없음(타부처위임)', 0)} / annex-only {t1.get('', 0)} / "
      f"adjudicated {t1.get('대외구속지향', 0) + t1.get('내부관리', 0)} = external {t1.get('대외구속지향', 0)} + internal {t1.get('내부관리', 0)}; "
      f"23.7% = {t1.get('대외구속지향', 0)}/257 = {100 * t1.get('대외구속지향', 0) / 257:.1f}%")
if (ROOT / "data/edges.jsonl").exists() and (ROOT / "data/admrules.jsonl").exists():
    run("src/resolve_rule_ids.py")
else:
    print("\n[skipped] src/resolve_rule_ids.py: data/edges.jsonl and data/admrules.jsonl (Zenodo deposit) not present")
print("\nDone. Compare against REPRODUCE.md.")
