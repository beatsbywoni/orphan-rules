# Orphan Rules

**Court-validated detection of administrative rules lacking delegation authority in Korea's legal hierarchy** — code, annotation data, panel outputs, and codebook.

> Paper under review (target: *Artificial Intelligence and Law*). This repository accompanies a computational-legal study that formalizes delegation defects in the Korean legal order as well-formedness violations on a typed delegation graph, audits the government's own delegation-linkage metadata against statutory text, and validates defect detection against published court decisions that actually denied effect to administrative rules.
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
| `src/collect_moleg.py` | Full pipeline against the Ministry of Government Legislation open API (law.go.kr): corpus collection, delegation-edge extraction, defect detection (D1/D1a/D2/D4), stratified gold-set sampling, court-decision oracle screening |
| `src/panel_annotate.py` | Seven-test annotator panel: batch submission to two vendor families, strict-JSON parsing with one retry, self-consistency runs |
| `src/dsl_estimate.py` | Design-based estimator with the calibration sample, plus the preregistered sensitivity specifications (majority vote, latent class variants) |
| `src/anchors.py` | Anchor-gate evaluation against the calibration set |
| `src/fulltext_check.py` | Full-text re-verification of triage candidates (Sect. 8.4) |
| `src/resolve_external_claims.py` | Cross-ministry resolution of claimed statutory bases for orphan-rule candidates |
| `src/llm_annotate.py` | LLM second annotator (OpenAI-compatible endpoint), with repeat runs and self-consistency reporting |
| `src/agreement.py` | Cohen's κ, Fleiss' κ / Krippendorff's α, sample-size calculator (no dependencies) |
| `src/retest_kappa.py`, `src/make_retest_workbook.py` | Intra-annotator re-test: blank-form generation and agreement computation |
| `src/make_public.py` | The script that built this bundle — manifest, scrub table, and the identifier check that gates release |
| `codebook/annotation_guideline.md` | Annotation codebook v1.1 (delegation clauses L1–L4; orphan-rule triage T1; oracle reading O1–O8), with its own revision note |
| `docs/deviation_log.md` | Every departure from the preregistration, with date and rationale |
| `data/labels/` | All human and LLM annotations, released in full (per Braun 2024's reporting recommendations): 200-clause calibration set + LLM annotations, 89 screened court decisions, 149-rule orphan triage in **both** adjudicated versions, cross-ministry resolution, and the August re-test |
| `data/panel/` | The preregistered seven-test panel: `manifest.json` (models, parameters, system-prompt SHA-256), `state.json` (batch identifiers and per-run counts), `system_prompt.txt`, per-test labels for the pilot, self-consistency, and full runs, the anchor gate and estimator outputs, and the Sect. 8.4 full-text check including its superseded first pass |
| `data/summary.json` | Detection summary for the Ministry of Education pilot (275 statutes/decrees, 261 administrative rules, 7,558 delegation edges) |
| `output/tables/` | Agreement and audit tables |

## Reproduction

Two levels, as defined in the paper.

**Deterministic.** The archived panel outputs in `data/panel/`, together with the seeded estimator code, reproduce every number in the paper without any API access. This is the designated reproduction target.

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
python src/collect_moleg.py oracle      # court-decision screening
```

Convenience wrappers are in `scripts/`.

## Notes on the API

The implementation documents several undocumented behaviours of the law.go.kr open API that are easy to get wrong (see comments in `src/collect_moleg.py`): the majority class of the delegation metadata is mere citation (인용법령) and must be excluded; the `detc` list endpoint returns items under a capitalized key; body text of administrative rules may arrive as a list of strings; case-law search requires full-text mode (`search=2`).

A service outage on 2026-08-22 returned HTTP 404 with a maintenance page for every request, which is easy to misread as an account problem. `collect_moleg.py` detects the maintenance page and exits with a distinct code rather than letting the caller conclude the API key was revoked.

## License

Code: MIT (see `LICENSE`). Annotation labels and memos: CC BY 4.0. Underlying legislative texts and court decisions are Korean public-sector works served by the National Law Information Center open API; they are redistributed here only in excerpt form for research documentation, with source links in each record.
