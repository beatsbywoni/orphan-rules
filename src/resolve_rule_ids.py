#!/usr/bin/env python3
# NOTE (2026-10-15): requires data/edges.jsonl and data/admrules.jsonl from the Zenodo raw deposit (not in this repository).
# Outputs resolution_stages.csv (280 links / 144 distinct targets, 257- and 261-rule denominators) and resolution_table.csv
# (38 unresolved targets with CANDIDATE causes assigned from titles/years; author_confirmed is empty where not individually verified).
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
with open(OUT / "resolution_table.csv", "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out), Counter(r["category_AI_preliminary"] for r in out))
print("edges among unresolved:", sum(r["n_edges"] for r in out))
