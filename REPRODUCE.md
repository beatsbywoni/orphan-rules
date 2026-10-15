# REPRODUCE.md — deterministic reproduction of the paper's reported numbers from stored outputs

No API call is required. Everything below runs from files in the public repository (submission version 2026-10-16; `python scripts/reproduce.py` runs steps 2, 4, 9 and 10 and the weighted re-analysis in one go, and step 14 when the two raw files are present) plus, for identifier resolution and the extended clause search only, the raw files in the Zenodo deposit. Steps 1, 3, 5–8, 11–13 and 15 are run or checked by hand as listed.

## Environment (verified 2026-09-16)
Python 3.11.15 · numpy 2.4.4 · pandas 3.0.2 (not required by src/) · scipy 1.17.1 (not required) · matplotlib 3.10.9 (figures only) · requests ≥2.31 (collection only, not needed for reproduction). See `requirements-repro.txt` (re-run 2026-10-16 on Python 3.13.16 / numpy 2.5.3 with identical output).

## Order
| # | Command | Reproduces | Status 2026-09-16 |
|---|---|---|---|
| 1 | `python src/dsl_estimate.py match` (optional; `data/panel/calibration_map.csv` already stored) | 200/200 calibration ↔ population mapping | ✔ |
| 2 | `python src/dsl_estimate.py dsl --scope full`; then `python src/dsl_weighted.py` for the design-weighted 4.25% (1.13–7.37; bootstrap 1.06–7.41), 2.26% (0.44–4.08), 1.88% (0.43–3.33) and `output/tables/weighted/strata_table.csv` (Table S3.3) | 4.5% (1.5–7.6); surrogate 9.5%; spec curve 12.2% / 8.3% / 4.9%; undecidable→delegation 3.0% (0.8–5.2); per-test agreement (Table S2.1 col. 4) | ✔ byte-identical to stored `dsl_results_full.json` |
| 3 | `python src/agreement.py kappa --a data/labels/goldset_labeled_v2.csv --a-col L1_위임인가 --b data/labels/goldset_llm.csv --b-col LLM_L1` | Table 2 row 1: 0.980 (196/200), κ 0.707 (0.41–0.93) | ✔ (bootstrap CI 0.4055–0.9267) |
| 4 | `python src/retest_kappa.py` | Table 2 rows 3–4: L1 κ = 1.00; L2 intersection agreement 1.000 (the script labels the statistic it computes on the aligned sets "정렬집합 κ", not a Cohen's κ); L2 exact set-match κ 0.95 (0.88–1.00; 56/58). The 3-day re-test exact set-match κ 0.67 (0.53–0.80) and primary-form κ 1.00 use the same functions on `data/labels/goldset_retest_0818.csv` (one-off computation, 2026-10-16) | ✔ |
| 5 | Wilson(7, 200) | 3.5% (1.7–7.0) | ✔ |
| 6 | `python src/fulltext_check.py report` | 46.0% (92/200); reverse 1.0% (2/200); 10/10 on correction records | ✔ ; Wilson 39.2–52.9 / 0.3–3.6 / 72.2–100 ✔ |
| 7 | `python src/make_figures.py` | Figure 1 (`fig2_triage.png`), Figure 2 (`fig1_edges.png`) | ✔ regenerated |
| 8 | count `data/edges.jsonl` by 위임구분 | 7,558; 2,089 / 825 / 280 / 4,364; 57.7%; 3.7% | ✔ |
| 9 | `data/labels/findings_D1_triage_v3.csv` T1 column (also printed by `scripts/reproduce.py`) | Table 3: 149 → 7 cross-ministry, 4 annex-only, 138 adjudicated = 61 external / 77 internal; 23.7% = 61/257 | ✔ |
| 10 | `data/labels/claim_check_labeled.csv` `analysis_label` column | Table 4: a 10 / b 7 / c 3 (b-decree 5, b-authorise 1, b-cite 1); superseded a 8 / b 8 / c 4 in `claim_check_labeled_v1_superseded.csv` | ✔ (C10, C11 re-verdicts adopted 2026-09-16; see `docs/claim_check_result.md`) |
| 11 | `data/summary.json` D4 | 45.1% = 116/257 | ✔ |
| 12 | `data/panel/anchor_gate_full.json` | 74 anchors (1.0%), unanimity 60.8% | ✔ |
| 13 | `trunc()` of `src/fulltext_check.py` over `panel_input.csv` | fragments 2,488/7,558 = 32.9%; 636/721 = 88.2%; undecidable-majority flags 512/721 | ✔ |
| 14 | identifier resolution (`src/resolve_rule_ids.py`; needs `data/edges.jsonl` and `data/admrules.jsonl` from the Zenodo deposit; outputs in `output/tables/resolution/`) | 72/280 (25.7%), 194 cumulative, 38/144 (26.4%); **matching sensitivity** (`d1_matching_sensitivity.csv`): D1 211/257 under identifier-only vs 149/257 under identifier-or-title, 62 additional rules not triaged; `rule_resolution_audit.csv` keeps every title candidate (1 link with two candidates among the 208 non-ID links; 3 title collisions among the 257 rules) | ✔ **only with the 257-rule denominator** (훈령·예규·고시·지침); with all 261 rules: 73 / 195 / 37. `resolution_table_auto.csv` is the script's own candidate-cause table; `resolution_table.csv` merges it with the stored preliminary annotations in `data/labels/resolution_annotations.csv` (author_confirmed empty) |
| 15 | `python sim/lcm_sim.py; python sim/lcm_sim2.py; python sim/c1_directional_sim.py; python sim/dsl_counter_sim.py` (~2 min) | Table S4.1 (+0.51/+0.48/+1.01/+1.27; refs +2.19/+2.54) and docs/18 (8.08%, 5.69%, 6.04%, 3.52%, unanimity 0.882, 891 items) | ✔ (`lcm_sim.py`/`lcm_sim2.py` committed in `sim/`) |

## Not reproducible from the *public* repository
- The exact 08-15 API responses can be re-collected only with a law.go.kr key and will differ (corpus drift).
