# Orphan Rules

**Auditing a government's delegation-linkage metadata against the statutory text (Korea, Ministry of Education)** — code, annotation data, panel outputs, and codebook.

> Paper under review (target: *Government Information Quarterly*; title "When the record is not the law: Auditing delegation metadata in Korea's national legal information system"). Statistical and doctrinal detail is in the manuscript's Supplementary material S1–S5, generated from files in this repository. The study treats the government's delegation-linkage records as a classifier of the source language the service marks as delegating, audits them against a probability-sampled human calibration set and a registered panel of machine annotators, reads the provisions cited by 20 selected rules, and uses 89 close-read court decisions, constitutional decisions and official interpretations as a *reference set* that attests the doctrinal test the screen mechanizes. The reference set (labelled `oracle` in file names and code, for historical reasons) is not a performance test of the screen; its recall is not measured.
>
> **Submission version 2026-10-16** (supersedes 2026-10-15; manuscript retargeted 2026-10-17 with no change to any analysis file, see `docs/deviation_log.md` R-2026-10-17-1). See `MANIFEST.md` for the frozen file list with SHA-256 hashes and `REPRODUCE.md` for the number-by-number reproduction table. `python scripts/reproduce.py` regenerates the reported estimates from stored outputs without network access; with the two raw files from the Zenodo deposit in `data/` it also re-runs identifier resolution and the matching-sensitivity tables.
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
| `src/resolve_rule_ids.py` | Identifier resolution of the 280 rule-directed links (direct ID match, title match, unresolved) with 257- and 261-rule denominators; `rule_resolution_audit.csv` (one row per link, every title candidate preserved, no version equivalence asserted); `d1_matching_sensitivity.csv` (one row per rule: D1 is 211/257 under identifier-only matching and 149/257 under the published identifier-or-title rule; the 62 additional rules were never triaged and carry no label); the 38 unresolved targets carry *candidate* causes, the script's own in `resolution_table_auto.csv` and the stored preliminary annotations (`data/labels/resolution_annotations.csv`) merged in `resolution_table.csv` (`author_confirmed` empty where not verified). Requires the raw deposit; outputs in `output/tables/resolution/` |
| `scripts/reproduce.py` | One command that regenerates the reported estimates from stored outputs (no network) |
| `scripts/build_audit_states.py` | Post-registration (2026-10-17). Assigns each of the 280 rule-directed links and each of the 257 rules an audit state from files already in this repository, records where the open question sits (source record, study scope, matching, collection, legal reading), what inference the state licenses and does not, and a next action; adds no label and changes none. Outputs in `output/tables/audit_states/` (`link_states.csv`, `rule_states.csv`, `state_summary.csv`, `case_traces.csv` for C06, C10, C11). An implementation example of Table 5 of the paper, not a gold standard or legal diagnosis |
| `src/anchors.py` | Anchor-gate evaluation against the calibration set |
| `src/fulltext_check.py` | Full-text re-verification of calibration records (the full-text check reported in Supplementary material S2 and S3; "Sect. 8.4" in earlier drafts) |
| `src/resolve_external_claims.py` | Cross-ministry resolution of claimed statutory bases for orphan-rule candidates |
| `src/llm_annotate.py` | LLM second annotator (OpenAI-compatible endpoint), with repeat runs and self-consistency reporting |
| `src/agreement.py` | Cohen's κ, Fleiss' κ / Krippendorff's α, sample-size calculator (no dependencies) |
| `src/l2_agreement.py` | Form-label (L2) agreement of Table 2 / S1.1 with the scoring scope stated (L1-concordant items, full recorded form sets), the closed-list comparison, the constant marker extractor's κ and the August re-test figures (2026-10-16) |
| `src/retest_kappa.py`, `src/make_retest_workbook.py` | Intra-annotator re-test: blank-form generation and agreement computation. The registered intersection criterion aligns overlapping form-label sets before comparison; the script reports that figure as an aligned-set statistic, not as a Cohen's κ, and gives exact set-match κ alongside (output in `docs/sept_retest_result.md`) |
| `src/triage_panel.py`, `docs/triage_rubric_T1_v1.md` | Machine-panel replication of the rule-level triage under a frozen, hashed rubric (post-registration analysis) |
| `src/claim_check.py`, `docs/claim_check_result.md` | Clause-level reading of the provisions cited by the 20 externally-directed orphan rules that the automatic extraction placed in the MOE-instrument stratum (post-registration analysis). Current labels (Table 4: a 10 / b 7 / c 3) in `data/labels/claim_check_labeled.csv`, with `original_label`, `proposed_label` (post-registration re-reading assisted by a generative model), `analysis_label`, `status` and `decision_basis` per row; the earlier file (a 8 / b 8 / c 4) is kept as `claim_check_labeled_v1_superseded.csv`; `evidence_location`, `evidence_text`, `text_version_basis` and `original_memo_status` link each row to its evidence and say which text was read (column dictionary in `docs/claim_check_result.md`); `output/tables/clause_reading_C01_C20.csv` is the *preliminary* record of the 2026-09-16 re-reading (generative assistant: extended search scope, found wording, preliminary verdicts), whose empty `저자_확인_여부` column is left as it was; the author's decisions are recorded in the label file and linked back through `linked_final_status` |
| `sim/lcm_sim.py`, `sim/lcm_sim2.py`, `sim/c1_directional_sim.py`, `sim/dsl_counter_sim.py` | Pre-registration contrast experiment (SI S4): synthetic generator with family-correlated errors, latent class fits, directional human-error injection, design-based counter-simulation — 40 replications, fixed seeds |
| `src/make_public.py` | The script that built this bundle — manifest, scrub table, and the identifier check that gates release; since 2026-10-16 it also blanks the author fields in the document properties of xlsx/docx files and scans inside those containers |
| `codebook/annotation_guideline.md` | Annotation codebook v1.1 (delegation clauses L1–L4; orphan-rule triage T1; oracle reading O1–O8), with its own revision note |
| `docs/deviation_log.md` | Every departure from the preregistration, with date and rationale |
| `data/labels/` | All human and LLM annotations, released in full (per Braun 2024's reporting recommendations): 200-clause calibration set + LLM annotations, 89 screened court decisions, 149-rule orphan triage in **both** adjudicated versions, cross-ministry resolution, and the August re-test |
| `data/panel/` | The preregistered seven-test panel: `manifest.json` (models, parameters, system-prompt SHA-256), `state.json` (batch identifiers and per-run counts), `system_prompt.txt`, per-test labels for the pilot, self-consistency, and full runs, the anchor gate and estimator outputs, and the full-text check of S2 and S3 (called Sect. 8.4 in earlier drafts) including its superseded first pass |
| `data/summary.json` | Detection summary for the Ministry of Education pilot (275 statutes/decrees, 261 administrative rules, 7,558 delegation edges) |
| `output/tables/` | Agreement tables (`table6_agreement.csv`, current, regenerated 2026-10-16 from `src/l2_agreement.py` and `src/retest_kappa.py`; `table7_audit_SUPERSEDED_2026-08.csv` is the August summary kept as a historical artefact, its wording is stronger than the manuscript's and must not be read as current); `weighted/` (design-weighted estimates, Table S3.3 strata table, sensitivity files), `resolution/` (identifier resolution), `audit_states/` (audit states, 2026-10-17), `clause_reading_C01_C20.csv` |

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
