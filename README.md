# Orphan Rules

**Auditing a government's delegation-linkage metadata against the statutory text (Korea, Ministry of Education)** — code, annotation data, panel outputs, and codebook.

> Paper under review (target: *Computer Law & Security Review*; title "Rules without recorded authority: Auditing a government's delegation-linkage metadata against the statutory text in Korea"). Statistical and doctrinal detail is in the manuscript's Supplementary material S1–S5, generated from files in this repository. The study treats the government's delegation-linkage records as a classifier of the source language the service marks as delegating, audits them against a probability-sampled human calibration set and a registered panel of machine annotators, reads the provisions cited by 20 selected rules, and uses 89 close-read court decisions, constitutional decisions and official interpretations as a *reference set* that attests the doctrinal test the screen mechanizes. The reference set (labelled `oracle` in file names and code, for historical reasons) is not a performance test of the screen; its recall is not measured.
>
> **Submission version 2026-10-15.** See `MANIFEST.md` for the frozen file list with SHA-256 hashes and `REPRODUCE.md` for the number-by-number reproduction table. `python scripts/reproduce.py` regenerates the reported estimates from stored outputs without network access.
>
> **Anonymized for double-blind review.** The licence holder, the preregistration identifier, and the API account name are masked in this copy; they are restored on acceptance. Nothing else is withheld.

## Two tiers

| | Where | What | Size |
|---|---|---|---|
| **This repository** | here | Code, the full annotation record, all panel outputs, codebook, deviation log | ~22 MB |
| **Archival deposit** | Zenodo DOI (at submission) | Raw API responses (`data/raw/`), panel request payloads (`data/panel/req_*.jsonl`), consolidated corpus files | ~430 MB |

The split is by size, not by selectivity. The reproduction target defined in the paper — the *outputs* of the seven-test panel — is in this repository, in full. The request payloads that produced them are in the deposit because they are an order of magnitude larger and add nothing a reader cannot reconstruct from the inputs and the archived system prompt.

## What is in here

| Path | Contents |
|---|---|
| `src/collect_moleg.py` | Full pipeline against the Ministry of Government Legislation open API (law.go.kr): corpus collection, delegation-edge extraction, defect detection (D1/D1a/D2/D4), stratified gold-set sampling, court-decision screening. Note: D4 is implemented with `all(...)` (a rule counts only when none of its extracted instrument-level basis claims matches a recorded edge); D1a is an instrument-level heuristic; the `조항호목` field is stored as `대상조항호목` but locates the link text and has not been verified as the target provision — all three are stated as such in the manuscript |
| `src/panel_annotate.py` | Seven-test annotator panel: batch submission to two vendor families, strict-JSON parsing with one retry, self-consistency runs |
| `src/dsl_estimate.py` | Registered (unweighted) design-based estimator with the calibration sample, plus the preregistered sensitivity specifications (majority vote, latent class variants). `extreme()` recodes the *panel's* undecidable verdicts only; human labels are unchanged |
| `src/dsl_weighted.py` | Post-registration design-weighted re-analysis (stratified difference estimator, normal and stratified-bootstrap intervals, strata table, weighted tipping points, shared-error and sentence-group sensitivity). The six single-record strata are pooled into one collapsed group for resampling and variance (an approximation; see S3). Outputs in `output/tables/weighted/` |
| `src/resolve_rule_ids.py` | Identifier resolution of the 280 rule-directed links (direct ID match, title match, unresolved) with 257- and 261-rule denominators; the 38 unresolved targets carry *candidate* causes assigned from titles/years (`author_confirmed` empty where not verified). Requires the raw deposit; outputs in `output/tables/resolution/` |
| `scripts/reproduce.py` | One command that regenerates the reported estimates from stored outputs (no network) |
| `src/anchors.py` | Anchor-gate evaluation against the calibration set |
| `src/fulltext_check.py` | Full-text re-verification of triage candidates (Sect. 8.4) |
| `src/resolve_external_claims.py` | Cross-ministry resolution of claimed statutory bases for orphan-rule candidates |
| `src/llm_annotate.py` | LLM second annotator (OpenAI-compatible endpoint), with repeat runs and self-consistency reporting |
| `src/agreement.py` | Cohen's κ, Fleiss' κ / Krippendorff's α, sample-size calculator (no dependencies) |
| `src/retest_kappa.py`, `src/make_retest_workbook.py` | Intra-annotator re-test: blank-form generation and agreement computation |
| `src/triage_panel.py`, `docs/triage_rubric_T1_v1.md` | Machine-panel replication of the rule-level triage under a frozen, hashed rubric (post-registration analysis) |
| `src/claim_check.py`, `docs/claim_check_result.md` | Clause-level reading of the provisions cited by the 20 externally-directed orphan rules that the automatic extraction placed in the MOE-instrument stratum (post-registration analysis). Current labels (Table 4: a 10 / b 7 / c 3) in `data/labels/claim_check_labeled.csv`, with `original_label`, `proposed_label` (post-registration re-reading assisted by a generative model), `analysis_label`, `status` and `decision_basis` per row; the earlier file (a 8 / b 8 / c 4) is kept as `claim_check_labeled_v1_superseded.csv`; evidence per case in `output/tables/clause_reading_C01_C20.csv` |
| `sim/lcm_sim.py`, `sim/lcm_sim2.py`, `sim/c1_directional_sim.py`, `sim/dsl_counter_sim.py` | Pre-registration contrast experiment (SI S4): synthetic generator with family-correlated errors, latent class fits, directional human-error injection, design-based counter-simulation — 40 replications, fixed seeds |
| `src/make_public.py` | The script that built this bundle — manifest, scrub table, and the identifier check that gates release |
| `codebook/annotation_guideline.md` | Annotation codebook v1.1 (delegation clauses L1–L4; orphan-rule triage T1; oracle reading O1–O8), with its own revision note |
| `docs/deviation_log.md` | Every departure from the preregistration, with date and rationale |
| `data/labels/` | All human and LLM annotations, released in full (per Braun 2024's reporting recommendations): 200-clause calibration set + LLM annotations, 89 screened court decisions, 149-rule orphan triage in **both** adjudicated versions, cross-ministry resolution, and the August re-test |
| `data/panel/` | The preregistered seven-test panel: `manifest.json` (models, parameters, system-prompt SHA-256), `state.json` (batch identifiers and per-run counts), `system_prompt.txt`, per-test labels for the pilot, self-consistency, and full runs, the anchor gate and estimator outputs, and the Sect. 8.4 full-text check including its superseded first pass |
| `data/summary.json` | Detection summary for the Ministry of Education pilot (275 statutes/decrees, 261 administrative rules, 7,558 delegation edges) |
| `output/tables/` | Agreement and audit tables; `weighted/` (design-weighted estimates, Table S3.3 strata table, sensitivity files), `resolution/` (identifier resolution), `clause_reading_C01_C20.csv` |

## Reproduction

Two levels, as defined in the paper.

**Deterministic.** The archived panel outputs in `data/panel/`, the calibration labels in `data/labels/`, and the seeded estimator code reproduce the reported estimates without any API access: `python scripts/reproduce.py` (see `REPRODUCE.md` for which command yields which number). This is the designated reproduction target. Identifier resolution (`src/resolve_rule_ids.py`) additionally needs `data/edges.jsonl` and `data/admrules.jsonl` from the raw deposit.

**Re-collection.** Re-querying the legislation API and re-running the panel requires API keys and is *not* expected to yield identical outputs: the corpus changes after the pinned snapshot, and model versions are not guaranteed to persist.

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export MOLEG_OC=<your NLIC open-API key>   # https://open.law.go.kr

python src/collect_moleg.py smoke       # service diagnostics
python src/collect_moleg.py laws        # statutes & decrees (org filter)
python src/collect_moleg.py admrules    # administrative rules incl. body text
python src/collect_moleg.py delegation  # delegation edges (lsDelegated)
python src/collect_moleg.py detect      # D1/D1a/D2/D4 detection
python src/collect_moleg.py goldset --n 200 --pilot 0.5
python src/collect_moleg.py oracle      # court-decision screening (reference set)
```

Convenience wrappers are in `scripts/`.

## Notes on the API

The implementation documents several behaviours of the law.go.kr open API that are easy to get wrong (see comments in `src/collect_moleg.py`); the first is stated in the service manual (open.law.go.kr/LSO/openApi/openApiManual.do), the others are not: the majority class of the delegation metadata is mere citation (인용법령) and must be excluded; the `detc` list endpoint returns items under a capitalized key; body text of administrative rules may arrive as a list of strings; case-law search requires full-text mode (`search=2`).

A service outage on 2026-08-22 returned HTTP 404 with a maintenance page for every request, which is easy to misread as an account problem. `collect_moleg.py` detects the maintenance page and exits with a distinct code rather than letting the caller conclude the API key was revoked.

## License

Code: MIT (see `LICENSE`). Annotation labels and memos: CC BY 4.0. Underlying legislative texts and court decisions are Korean public-sector works served by the National Law Information Center open API; they are redistributed here only in excerpt form for research documentation, with source links in each record.
