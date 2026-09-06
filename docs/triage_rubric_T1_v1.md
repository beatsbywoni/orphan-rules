# Triage rubric T1 v1.0 — external direction of an administrative rule

**Frozen before any machine call. SHA-256 of this file is printed by `src/triage_panel.py`
at run time and recorded with the outputs. This is a machine-readable restatement of
codebook v1.1's T1 test (released with the repository); the judgement criterion is
unchanged.**

## Question

Does this administrative rule (훈령·예규·고시·지침), by its own text, set requirements,
standards, sanctions, or entitlements for actors **outside the administrative
organisation** — for example private schools and their operators, publishers,
accredited or designated private institutions, students, parents, or individual
teachers and public servants in their personal legal position (status, pay,
obligations)?

## Labels

- `externally-directed` — the rule's operative provisions purport to bind, burden,
  or entitle actors outside the issuing administration, or individual persons in
  their own legal position. Indicators: application or designation requirements for
  private entities; standards whose addressees are private actors; sanction or
  fine-aggravation criteria; entitlement or subsidy conditions for external
  recipients; curricula binding schools; pay, allowance, or service-obligation
  rules for individual teachers or public servants.
- `internal` — the rule organises the administration's own work only: internal
  reporting lines, committee operation, document handling, delegation of authority
  between administrative organs, performance evaluation of subordinate agencies as
  organs (not of individuals' legal position), budget execution procedure.
- `undecidable` — the text provided is insufficient to decide (for example, the
  operative content is entirely in an attachment that is not included).

## Decision rules

1. Judge from the rule text provided, not from the rule's title alone.
2. A rule that is mostly internal but contains at least one operative provision
   directed at external actors or individuals' legal position is
   `externally-directed`.
3. Rules addressing public servants **as individuals** (pay steps, allowances,
   mandatory service, disciplinary standards) are `externally-directed`;
   rules addressing subordinate **organs as organs** are `internal`.
4. Do not consider whether the rule has a statutory basis; that is a separate
   question. Judge only the direction of its operative content.
5. Answer in strict JSON: `{"label": "externally-directed" | "internal" |
   "undecidable", "reason": "<one sentence, in Korean or English>"}`.
