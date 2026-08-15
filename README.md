# Orphan Rules

**Court-validated detection of administrative rules lacking delegation authority in Korea's legal hierarchy** — code, annotation data, and codebook.

> Paper in preparation (target: *Artificial Intelligence and Law*). This repository accompanies a computational-legal study that formalizes delegation defects in the Korean legal order as well-formedness violations on a typed delegation graph, audits the government's own delegation-linkage metadata against statutory text, and validates defect detection against published court decisions that actually denied effect to administrative rules.

## What is in here

| Path | Contents |
|---|---|
| `src/collect_moleg.py` | Full pipeline against the Ministry of Government Legislation open API (law.go.kr): corpus collection, delegation-edge extraction, defect detection (D1/D1a/D2/D4), stratified gold-set sampling, court-decision oracle screening |
| `src/resolve_external_claims.py` | Cross-ministry resolution of claimed statutory bases for orphan-rule candidates |
| `src/llm_annotate.py` | LLM second annotator (OpenAI-compatible endpoint), with repeat runs and self-consistency reporting |
| `src/agreement.py` | Cohen's κ, Fleiss' κ / Krippendorff's α, sample-size calculator (no dependencies) |
| `codebook/annotation_guideline.md` | Annotation codebook v1.1 (delegation clauses L1–L4; orphan-rule triage T1; oracle reading O1–O8) |
| `data/labels/` | All human and LLM annotations, released in full (per Braun 2024's reporting recommendations): 200-clause calibration set + LLM annotations, 89 screened court decisions, 149-rule orphan triage, cross-ministry resolution |
| `data/summary.json` | Detection summary for the Ministry of Education pilot (275 statutes/decrees, 261 administrative rules, 7,558 delegation edges) |
| `output/tables/` | Agreement and audit tables |

Raw API responses are archived locally (`data/raw/`, not in this repository) and will be deposited with a version-pinned (MST) snapshot on Zenodo/OSF at submission.

## Pipeline

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

## License

Code: MIT (see `LICENSE`). Annotation labels and memos: CC BY 4.0. Underlying legislative texts and court decisions are Korean public-sector works served by the National Law Information Center open API; they are redistributed here only in excerpt form for research documentation, with source links in each record.
