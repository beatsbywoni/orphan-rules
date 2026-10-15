#!/usr/bin/env python3
# NOTE (2026-10-15): requires data/edges.jsonl and data/admrules.jsonl from the Zenodo raw deposit (not in this repository).
# Outputs (all in output/tables/resolution/):
#   resolution_stages.csv        280 links / 144 distinct targets, 257- and 261-rule denominators
#   resolution_table_auto.csv    38 unresolved targets with CANDIDATE causes assigned by this script from titles/years
#   resolution_table.csv         the same 38 rows merged with data/labels/resolution_annotations.csv (preliminary annotations,
#                                2026-09-16, generative assistant; still candidate causes; author_confirmed empty where not verified)
#   rule_resolution_audit.csv    (2026-10-16) one row per rule-directed link: recorded ID/title, direct-ID match, ALL title candidates
#                                (one-to-many preserved), stage; no legal/version equivalence is asserted
#   d1_matching_sensitivity.csv  (2026-10-16) one row per scoped rule: D1 under identifier-only vs identifier-or-title matching,
#                                with the published T1 triage label; rules flagged only under identifier-only matching are
#                                not_previously_triaged (no label is assigned here)
# -*- coding: utf-8 -*-
"""task_b_resolution.py — 작업 B: 식별자 해석 단계표 + 미해결 38 고유 대상 원인 분류 (AI 예비)."""
import json, re, csv, difflib
from collections import Counter, defaultdict
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; OUT = ROOT / "output" / "tables" / "resolution"; OUT.mkdir(parents=True, exist_ok=True)
def norm(s): return re.sub(r"\s+", "", str(s or "")).replace("ㆍ", "").replace("·", "")
edges = [json.loads(l) for l in open(ROOT / "data/edges.jsonl", encoding="utf-8")]
rules = [json.loads(l) for l in open(ROOT / "data/admrules.jsonl", encoding="utf-8")]
TYPES = ("훈령", "예규", "고시", "지침")
scoped = [r for r in rules if any(t in str(r.get("행정규칙종류", "")) for t in TYPES)]
assert len(scoped) == 257 and len(rules) == 261
ids = {str(r["행정규칙일련번호"]): r for r in scoped}; names = {norm(r["행정규칙명"]): r for r in scoped}
ids_all = {str(r["행정규칙일련번호"]): r for r in rules}; names_all = {norm(r["행정규칙명"]): r for r in rules}
re_ = [e for e in edges if e["대상유형"] == "행정규칙"]; assert len(re_) == 280

def stage(e, ids, names):
    if str(e.get("대상ID")) in ids: return "id"
    if norm(e.get("대상명")) in names: return "title"
    return "unresolved"
rows = []
for denom, I, Nm in (("257 scoped rules (훈령·예규·고시·지침) — paper basis", ids, names), ("261 all MOE rules incl. 공고·기타", ids_all, names_all)):
    st = Counter(stage(e, I, Nm) for e in re_)
    # distinct targets by normalized title
    byname = defaultdict(list)
    for e in re_: byname[norm(e["대상명"])].append(e)
    dst = Counter()
    for nm, es in byname.items():
        s = "id" if any(str(e.get("대상ID")) in I for e in es) else ("title" if nm in Nm else "unresolved")
        dst[s] += 1
    for unit, c, tot in (("link records (edges)", st, len(re_)), ("distinct targets (normalized title)", dst, len(byname))):
        rows.append({"denominator_rule_list": denom, "unit": unit, "input": tot, "stage1_current_serial_id_match": c["id"],
                     "stage2_title_match_ADDITIONAL": c["title"], "cumulative_resolved": c["id"] + c["title"],
                     "unresolved": c["unresolved"], "pct_id": round(100 * c["id"] / tot, 1), "pct_cum": round(100 * (c["id"] + c["title"]) / tot, 1),
                     "pct_unresolved": round(100 * c["unresolved"] / tot, 1)})
with open(OUT / "resolution_stages.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
for r in rows: print(r)
# id-matched titles all equal current titles?
print("id-matched edges whose title != current title:", sum(1 for e in re_ if str(e.get("대상ID")) in ids and norm(e["대상명"]) not in names))
print("distinct 대상ID among 280:", len(set(str(e["대상ID"]) for e in re_)))

# ---- B2 unresolved distinct targets (paper basis: 257)
byname = defaultdict(list)
for e in re_: byname[norm(e["대상명"])].append(e)
OTHER = {"고용노동부": "고용노동부", "문화체육관광부": "문화체육관광부", "건강검진실시기준": "보건복지부", "암검진실시기준": "보건복지부",
         "본인일부부담금": "보건복지부", "사회보장급여": "보건복지부", "질병관리청장": "질병관리청", "청소년": "여성가족부",
         "한국표준산업분류": "통계청", "국가직무능력표준": "고용노동부", "인문정신문화": "문화체육관광부", "인문학": "문화체육관광부"}
out = []
all_titles = [r["행정규칙명"] for r in rules]
for nm, es in sorted(byname.items()):
    if any(str(e.get("대상ID")) in ids for e in es) or nm in names: continue
    title = es[0]["대상명"]
    cand = difflib.get_close_matches(nm, list(names_all.keys()), n=2, cutoff=0.55)
    cand_t = [names_all[c]["행정규칙명"] + f" ({names_all[c]['행정규칙종류']}, 시행 {names_all[c].get('시행일자')})" for c in cand]
    if nm in names_all:
        cat = "excluded type (공고 등) — resolves in the 261-list"; reason = f"현행 목록에 있으나 종류={names_all[nm]['행정규칙종류']} 로 257 범위 밖"
    elif re.match(r"^\(?\d{4}", nm) or re.search(r"\d{4}(학년도|년도|년)", nm) or re.match(r"^\(제\d+차\)", nm):
        cat = "repealed year-specific notification (연도별 고시)"; reason = "제명에 연도/학년도/차수 — 매년 새 고시로 대체되어 현행 목록에 없음"
    elif any(k in nm for k in OTHER):
        m = next(k for k in OTHER if k in nm); cat = f"other ministry's rule ({OTHER[m]})"; reason = f"제명/주제가 타 부처 소관({m}) — 교육부 현행 목록 대상 아님"
    elif cand:
        cat = "renamed/superseded MOE rule (candidate current title found)"; reason = "유사 제명의 현행 규칙 존재 — 개명·전면개정 후 링크 미갱신 가능성"
    else:
        cat = "other (no current MOE rule of similar title)"; reason = "현행 교육부 규칙 중 유사 제명 없음 — 폐지 또는 개명 여부 저자 확인 필요"
    out.append({"target_title_as_recorded": title, "n_edges": len(es), "target_ids_recorded": "|".join(sorted(set(str(e["대상ID"]) for e in es))),
                "source_laws": "|".join(sorted(set(e["상위법령명"] for e in es))), "source_articles": "|".join(sorted(set(f"{e['상위법령명']} 제{e['상위조문번호']}조" for e in es)))[:300],
                "category_AI_preliminary": cat, "reason": reason, "closest_current_titles": " ; ".join(cand_t), "author_confirmed": ""})
with open(OUT / "resolution_table_auto.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out), Counter(r["category_AI_preliminary"] for r in out))
print("edges among unresolved:", sum(r["n_edges"] for r in out))
# ---- merge with stored preliminary annotations (kept as a separate input so the automatic table stays reproducible)
ANN = ROOT / "data/labels/resolution_annotations.csv"
ann = {r["target_title_as_recorded"]: r for r in csv.DictReader(open(ANN, encoding="utf-8-sig"))} if ANN.exists() else {}
merged = []
for r in out:
    a = ann.get(r["target_title_as_recorded"], {})
    m = {"target_title_as_recorded": r["target_title_as_recorded"], "n_edges": r["n_edges"], "target_ids_recorded": r["target_ids_recorded"],
         "source_laws": r["source_laws"], "source_articles": r["source_articles"],
         "category_auto": r["category_AI_preliminary"], "reason_auto": r["reason"], "closest_current_titles_auto": r["closest_current_titles"],
         "category_annotated": a.get("category_annotated", ""), "reason_annotated": a.get("reason_annotated", ""),
         "closest_current_titles_annotated": a.get("closest_current_titles_annotated", ""), "annotation_source": a.get("annotation_source", ""),
         "author_confirmed": a.get("author_confirmed", "")}
    merged.append(m)
with open(OUT / "resolution_table.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(merged[0])); w.writeheader(); w.writerows(merged)
print("annotated rows merged:", sum(1 for m in merged if m["category_annotated"]), "author_confirmed:", sum(1 for m in merged if m["author_confirmed"]))

# ---- (2026-10-16) link-level audit table: one row per rule-directed link, all title candidates preserved
names_multi = defaultdict(list)
for r in scoped: names_multi[norm(r["행정규칙명"])].append(r)
audit = []
for i, e in enumerate(re_, 1):
    tid = str(e.get("대상ID")); nm = norm(e.get("대상명"))
    id_rule = ids.get(tid)
    cands = names_multi.get(nm, [])
    if id_rule is not None: stg = "direct_id"
    elif len(cands) == 1: stg = "title_candidate"
    elif len(cands) > 1: stg = "title_candidate_ambiguous"
    else: stg = "unresolved"
    audit.append({"link_index": i, "source_law": e["상위법령명"], "source_article": e["상위조문번호"], "recorded_target_id": tid,
                  "recorded_target_title": e["대상명"], "normalized_title": nm,
                  "direct_id_match_rule": tid if id_rule is not None else "",
                  "direct_id_match_current_title": id_rule["행정규칙명"] if id_rule is not None else "",
                  "title_candidate_ids": "|".join(str(c["행정규칙일련번호"]) for c in cands),
                  "title_candidate_effective_dates": "|".join(str(c.get("시행일자", "")) for c in cands),
                  "title_candidate_count": len(cands),
                  "id_also_matches_a_title_candidate": "yes" if (id_rule is not None and tid in {str(c["행정규칙일련번호"]) for c in cands}) else ("no" if id_rule is not None else ""),
                  "stage": stg, "legal_version_verified": "not_assessed"})
with open(OUT / "rule_resolution_audit.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(audit[0])); w.writeheader(); w.writerows(audit)
print("rule_resolution_audit.csv:", len(audit), Counter(a["stage"] for a in audit))

# ---- (2026-10-16) rule-level matching sensitivity: identifier-only vs identifier-or-title (the published D1 rule, collect_moleg.py detect)
deleg_ids = {str(e.get("대상ID")) for e in re_ if e.get("대상ID")}
deleg_names = {norm(e.get("대상명")) for e in re_ if e.get("대상명")}
tri = {str(r["행정규칙일련번호"]): r for r in csv.DictReader(open(ROOT / "data/labels/findings_D1_triage_v3.csv", encoding="utf-8-sig"))}
sens = []
for r in scoped:
    rid = str(r["행정규칙일련번호"]); nm = norm(r["행정규칙명"])
    id_hits = sum(1 for e in re_ if str(e.get("대상ID")) == rid)
    title_hits = sum(1 for e in re_ if norm(e.get("대상명")) == nm)
    d1_id = int(rid not in deleg_ids); d1_both = int(rid not in deleg_ids and nm not in deleg_names)
    t = tri.get(rid)
    sens.append({"rule_id": rid, "rule_title": r["행정규칙명"], "rule_type": r.get("행정규칙종류"), "rule_effective_date": r.get("시행일자"),
                 "direct_id_edge_count": id_hits, "title_edge_count": title_hits,
                 "title_shared_with_other_scoped_rule": "yes" if len(names_multi[nm]) > 1 else "no",
                 "D1_id_only": d1_id, "D1_id_or_title": d1_both,
                 "published_T1": (t or {}).get("T1_규범성격", ""),
                 "triage_status": ("triaged (findings_D1_triage_v3)" if t else ("not_previously_triaged" if d1_id else "matched under both specifications"))})
with open(OUT / "d1_matching_sensitivity.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(sens[0])); w.writeheader(); w.writerows(sens)
c_id = sum(s["D1_id_only"] for s in sens); c_both = sum(s["D1_id_or_title"] for s in sens)
print(f"d1_matching_sensitivity.csv: D1 id-only {c_id}/257, id-or-title {c_both}/257, additional under id-only {c_id - c_both},",
      Counter(s["triage_status"] for s in sens), "collision rules:", sum(1 for s in sens if s["title_shared_with_other_scoped_rule"] == "yes"))
assert c_both == len(tri) and set(s["rule_id"] for s in sens if s["D1_id_or_title"]) == set(tri)
