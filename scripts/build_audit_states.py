#!/usr/bin/env python3
"""build_audit_states.py: assign every rule-directed link and every administrative rule an audit state.

Post-registration (2026-10-17). Reads only files already in the repository; adds no label and changes none.

Inputs
  output/tables/resolution/rule_resolution_audit.csv   280 rule-directed links (matching result per link)
  output/tables/resolution/resolution_table.csv        38 unmatched targets with candidate causes (not confirmed)
  output/tables/resolution/d1_matching_sensitivity.csv 257 rules (matching result per rule)
  data/labels/findings_D1_triage_v3.csv                triage of the 149 rules without a matched record
  data/labels/claim_check_labeled.csv                  reading of the provisions cited by 20 rules

Outputs (output/tables/audit_states/)
  link_states.csv   one row per link (unit: recorded link, n = 280)
  rule_states.csv   one row per rule (unit: administrative rule, n = 257)
  state_summary.csv counts per unit and state
  case_traces.csv   C06, C10, C11: what the evidence changed and what it leaves open

Each state records WHERE the open question sits, using one of five origins:
  source_record   the government's linkage records as collected
  study_scope     the boundary of the collected corpus (one ministry, current instruments)
  matching        the study's identifier/title matching rule
  collection      content the interface did not return (attachments)
  legal_reading   a question of legal interpretation the study did not decide
The output is an implementation example of the audit states in Table 5 of the paper. It is not a gold standard,
not a legal diagnosis, and not a measure of anyone's error rate.
"""
import csv
from collections import Counter, OrderedDict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "output/tables/audit_states"
AUDIT_DATE = "2026-08-15"


def read(path):
    with open(ROOT / path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def write(name, rows, fields):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / name, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


# ---------------------------------------------------------------- link level (n = 280)
LINK_STATES = OrderedDict([
    ("direct_id", dict(
        state="L1 identifier match", origin="",
        licensed="the two instruments are linked within the collected corpus",
        not_licensed="that the target provision, version or subject matter is covered",
        next_action="none for linkage; provision and scope review only if authority is at issue")),
    ("title_candidate", dict(
        state="L2 single title candidate", origin="matching",
        licensed="a candidate link to one current rule",
        not_licensed="that the candidate is the same instrument and version",
        next_action="check identity and version against the rule's amendment history")),
    ("title_candidate_ambiguous", dict(
        state="L3 several title candidates", origin="matching",
        licensed="the link points to one of several current rules",
        not_licensed="which one",
        next_action="resolve the candidates by version history")),
    ("unresolved", dict(
        state="L4 no match in the collected corpus", origin="study_scope or source_record (not confirmed)",
        licensed="the recorded identifier does not match a current rule of this ministry in the 2026-08-15 collection",
        not_licensed="that the link is broken or wrong; the target may be another ministry's rule or an earlier edition",
        next_action="check the candidate cause (other ministry, earlier edition, renamed rule) against the source system")),
])

links = read("output/tables/resolution/rule_resolution_audit.csv")
causes = {}
for r in read("output/tables/resolution/resolution_table.csv"):
    for tid in r["target_ids_recorded"].split("|"):
        causes[tid.strip()] = r["category_annotated"] or r["category_auto"]

link_rows = []
for r in links:
    s = LINK_STATES[r["stage"]]
    link_rows.append(dict(
        link_index=r["link_index"], unit="link", source_law=r["source_law"], source_article=r["source_article"],
        recorded_target_id=r["recorded_target_id"], recorded_target_title=r["recorded_target_title"],
        audit_date=AUDIT_DATE, direct_id_match="yes" if r["stage"] == "direct_id" else "no",
        title_candidate_count=r["title_candidate_count"], version_checked=r["legal_version_verified"],
        state=s["state"], origin_of_open_question=s["origin"],
        candidate_cause_unconfirmed=causes.get(r["recorded_target_id"], "") if r["stage"] == "unresolved" else "",
        inference_licensed=s["licensed"], inference_not_licensed=s["not_licensed"], next_action=s["next_action"],
        evidence="output/tables/resolution/rule_resolution_audit.csv#link_index=" + r["link_index"],
    ))
LINK_FIELDS = list(link_rows[0].keys())
write("link_states.csv", link_rows, LINK_FIELDS)

# ---------------------------------------------------------------- predecessor screens (automatic, unconfirmed)
import difflib, re


def norm_title(s):
    s = re.sub(r"\(.*?\)|[「」『』]", "", s)
    s = re.sub(r"(19|20)\d\d\s*년도?|제?\d+\s*차|\d+", "", s)
    return re.sub(r"[\s·ㆍ.,]", "", s)


def sim(a, b):
    a, b = norm_title(a), norm_title(b)
    if not a or not b:
        return 0.0
    if a in b or b in a:
        return 1.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def cited_instruments(c):
    names = set()
    for field in ("D4_주장법령(자동)", "evidence_provision"):
        for part in re.split(r"[;；]", c.get(field) or ""):
            m = re.match(r"\s*([^\d(\[]+?)\s*(제\d|\[|\(|$)", part)
            if m and m.group(1).strip():
                names.add(m.group(1).strip())
    return names


UNMATCHED = [l for l in link_rows if l["state"].startswith("L4")]
SIM_ALL = 0.85   # title-only screen over all rules without a matched record
SIM_CITED = 0.6  # screen restricted to links whose source is the instrument the rule cites


def screen_similar_title(title):
    hits = [(l["link_index"], l["recorded_target_title"], round(sim(title, l["recorded_target_title"]), 2)) for l in UNMATCHED]
    return [h for h in hits if h[2] >= SIM_ALL]


def screen_cited_source(title, c):
    srcs = cited_instruments(c)
    hits = [(l["link_index"], l["source_law"] + " " + l["source_article"], l["recorded_target_title"], round(sim(title, l["recorded_target_title"]), 2))
            for l in UNMATCHED if l["source_law"] in srcs]
    return [h for h in hits if h[3] >= SIM_CITED]


# ---------------------------------------------------------------- rule level (n = 257)
sens = read("output/tables/resolution/d1_matching_sensitivity.csv")
triage = {r["행정규칙일련번호"]: r for r in read("data/labels/findings_D1_triage_v3.csv")}
reading = {r["행정규칙일련번호"]: r for r in read("data/labels/claim_check_labeled.csv")}

R = OrderedDict([
    ("R1", ("R1 linked by identifier", "",
            "at least one recorded link reaches the rule",
            "that the link covers every article of the rule",
            "provision-level review only where an article's authority is at issue")),
    ("R2", ("R2 linked by title candidate only", "matching",
            "a candidate record exists under the title rule",
            "that the record and the rule are the same instrument and version; not triaged",
            "verify identity and version; triage if the candidate fails")),
    ("R3", ("R3 delegation found in another ministry's records", "study_scope",
            "the rule is linked outside the one-ministry corpus",
            "an omission in the government's records",
            "none for linkage")),
    ("R4", ("R4 content in attachments not returned", "collection",
            "nothing about the rule's direction or authority",
            "any classification",
            "obtain the attachment text, then triage")),
    ("R5", ("R5 internal housekeeping (author classification)", "",
            "the rule does not, by its own text, address actors outside the administration",
            "that no delegation could be relevant to any article",
            "none for authority tracing; classification is contestable for personnel rules")),
    ("R6a", ("R6a delegating language found in the cited provision", "source_record or matching (not distinguished)",
             "the cited provision contains delegating language, and no record matched to this rule under the study's matching rule",
             "that the delegation covers this rule's subject matter or existed when the rule issued",
             "add or check the link at source; legal review of scope and timing")),
    ("R6b", ("R6b no delegating language in the cited provision", "legal_reading",
             "the provision the rule cites does not delegate under the reading rule",
             "that the rule lacks authority; uncited provisions were not searched",
             "legal review for uncited bases")),
    ("R6c", ("R6c undecidable within the corpus", "study_scope",
             "the deciding text, if any, lies outside the collected corpus",
             "anything about authority",
             "read the external instrument")),
    ("R7", ("R7 externally directed, cited provision not read", "not assessed",
            "no record matched to the rule under the study's matching rule",
            "whether the gap lies in the source records, the matching, the corpus boundary or the law",
            "read the cited provision; query other ministries' records if the claimed basis is theirs")),
])

rule_rows = []
for r in sens:
    rid = r["rule_id"]
    t = triage.get(rid)
    c = reading.get(rid)
    if r["D1_id_or_title"] == "0":
        code = "R1" if r["D1_id_only"] == "0" else "R2"
    else:
        t1 = (t or {}).get("T1_규범성격", "")
        if t1 == "해당없음(타부처위임)":
            code = "R3"
        elif t1 == "":
            code = "R4"
        elif t1 == "내부관리":
            code = "R5"
        elif c is not None:
            code = {"a": "R6a", "b": "R6b", "c": "R6c"}[c["analysis_label"]]
        else:
            code = "R7"
    st, origin, lic, notlic, nxt = R[code]
    rule_rows.append(dict(
        rule_id=rid, unit="rule", rule_title=r["rule_title"], rule_type=r["rule_type"], audit_date=AUDIT_DATE,
        matched_by_identifier="yes" if r["D1_id_only"] == "0" else "no",
        matched_by_title_only="yes" if (r["D1_id_only"] == "1" and r["D1_id_or_title"] == "0") else "no",
        triage_label=(t or {}).get("T1_규범성격", "not triaged" if r["D1_id_or_title"] == "1" else "not applicable") or "no article text",
        basis_claim_category=(t or {}).get("근거주장범주_자동", ""),
        reading_id=c["id"] if c else "", reading_label=c["analysis_label"] if c else "",
        reading_status=c["status"] if c else "", version_checked="not_assessed",
        cause_confirmed="no", state=st, origin_of_open_question=origin,
        unmatched_link_similar_title="|".join(f"link {h[0]}: {h[1]} ({h[2]})" for h in screen_similar_title(r["rule_title"]))
            if r["D1_id_or_title"] == "1" else "",
        unmatched_link_from_cited_source="|".join(f"link {h[0]} from {h[1]}: {h[2]} ({h[3]})" for h in screen_cited_source(r["rule_title"], c))
            if c else "",
        inference_licensed=lic, inference_not_licensed=notlic, next_action=nxt,
        evidence=";".join(x for x in [
            "output/tables/resolution/d1_matching_sensitivity.csv",
            "data/labels/findings_D1_triage_v3.csv#" + t["id"] if t else "",
            "data/labels/claim_check_labeled.csv#" + c["id"] if c else ""] if x),
    ))
RULE_FIELDS = list(rule_rows[0].keys())
write("rule_states.csv", rule_rows, RULE_FIELDS)

# ---------------------------------------------------------------- summary
summary = []
lc = Counter(r["state"] for r in link_rows)
for k, v in LINK_STATES.items():
    summary.append(dict(unit="link (n=280)", state=v["state"], n=lc[v["state"]], origin_of_open_question=v["origin"]))
uc = Counter(r["candidate_cause_unconfirmed"] for r in link_rows if r["state"].startswith("L4"))
for cause, n in sorted(uc.items(), key=lambda x: -x[1]):
    summary.append(dict(unit="link (n=280)", state="  L4 by candidate cause (unconfirmed): " + cause, n=n, origin_of_open_question=""))
rc = Counter(r["state"] for r in rule_rows)
for k, v in R.items():
    summary.append(dict(unit="rule (n=257)", state=v[0], n=rc[v[0]], origin_of_open_question=v[1]))
for k, v in R.items():
    rows_k = [x for x in rule_rows if x["state"] == v[0]]
    a = sum(1 for x in rows_k if x["unmatched_link_similar_title"])
    if a:
        summary.append(dict(unit="rule (n=257)", state=f"  {v[0][:3].strip()} with an unmatched link of similar title (screen, unconfirmed)", n=a, origin_of_open_question="matching / identifier currency"))
b = [x for x in rule_rows if x["unmatched_link_from_cited_source"]]
for x in b:
    pass
summary.append(dict(unit="rule (n=257)", state="  read rules (R6) with an unmatched link from the cited instrument to a similar title (screen, unconfirmed)",
                    n=len(b), origin_of_open_question="matching / identifier currency"))
summary.append(dict(unit="rule (n=257)", state="    of which R6a", n=sum(1 for x in b if x["state"].startswith("R6a")), origin_of_open_question=""))
write("state_summary.csv", summary, ["unit", "state", "n", "origin_of_open_question"])

# ---------------------------------------------------------------- case traces
claims = {r["id"]: r for r in read("data/labels/claim_check_labeled.csv")}
TRACE = {
    "C10": ("The cited decree article had been deleted; its successor (effective 2025-12-02) contains delegating language. "
            "Label b -> a (record omission as of the audit date).",
            "The rule issued on 2025-10-17, before the successor article took effect; the trace establishes nothing about "
            "authority at issuance, nor that the successor covers the rule's subject matter."),
    "C11": ("The delegating language sits in the annex (별표 1) of the cited decree article. Label c -> a.",
            "The annex was read outside the collected corpus and its version date was not recorded."),
    "C06": ("An uncited statute (Korea Student Aid Foundation Act) contains ministerial delegations. Label stays b under the "
            "reading rule; the candidate is recorded, not counted.",
            "Whether the uncited provisions cover the rule is a legal question the study did not decide."),
}
trace_rows = []
for cid, (changed, open_) in TRACE.items():
    c = claims[cid]
    rr = next(x for x in rule_rows if x["rule_id"] == c["행정규칙일련번호"])
    trace_rows.append(dict(
        case=cid, rule_id=c["행정규칙일련번호"], rule_title=c["행정규칙명"], rule_issued=c["발령일자"],
        original_label=c["original_label"], adopted_label=c["analysis_label"], status=c["status"],
        audit_state=rr["state"], evidence_provision=c["evidence_provision"], text_version_basis=c["text_version_basis"],
        what_the_evidence_changed=changed, what_remains_open=open_,
        evidence="data/labels/claim_check_labeled.csv#" + cid + " (evidence_text, decision_basis, text_version_basis)",
    ))
write("case_traces.csv", trace_rows, list(trace_rows[0].keys()))

# ---------------------------------------------------------------- report
print("Audit states (post-registration, 2026-10-17); inputs unchanged")
for s in summary:
    print(f'  {s["unit"]:14s} {s["state"]:72s} {s["n"]:>4}  {s["origin_of_open_question"]}')
assert sum(lc.values()) == 280 and sum(rc.values()) == 257
assert rc[R["R6a"][0]] == 10 and rc[R["R6b"][0]] == 7 and rc[R["R6c"][0]] == 3
assert rc[R["R2"][0]] == 62 and rc[R["R3"][0]] == 7 and rc[R["R4"][0]] == 4 and rc[R["R5"][0]] == 77
print("read rules with an unmatched link from the cited instrument to a similar title:",
      ", ".join(f'{x["reading_id"]} ({x["state"][:3]})' for x in b))
print("checks passed: 280 links, 257 rules; 10/7/3, 62, 7, 4, 77 reproduced")
