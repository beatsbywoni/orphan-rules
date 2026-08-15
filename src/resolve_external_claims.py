#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
resolve_external_claims.py — D1 중 '타부처 법령 근거 주장' 규칙의 커버리지 아티팩트 해소

교육부 소관이 아닌 법령을 근거로 주장하는 D1 규칙에 대해:
  ① 주장 법령명을 법령 목록 API로 검색해 법령ID 확보
  ② 그 법령의 lsDelegated를 호출
  ③ 해당 행정규칙이 위임 대상에 실제로 있는지 확인
→ 있으면 "타부처 위임 확인"(D1 아님, 코퍼스 경계 아티팩트),
  없으면 D1 유지(또는 D4 성격).

출력: data/external_claims_resolution.csv
사용: python src/resolve_external_claims.py   (src/collect_moleg.py 필요)
"""
import csv
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from collect_moleg import (_get, _L, _read_jsonl, _norm, SEARCH_URL, SERVICE_URL,
                           parse_delegated, DATA)

CLAIM = re.compile(r"[「『]\s*([^」』]{2,50}?)\s*[」』]")
LAWISH = re.compile(r"(법|법률|령|규칙|규정)$")


def main():
    laws = _read_jsonl(DATA / "laws.jsonl")
    rules = _read_jsonl(DATA / "admrules.jsonl")
    d1 = list(csv.DictReader(open(DATA / "findings_D1_orphan.csv",
                                  encoding="utf-8-sig")))
    law_names = {_norm(l.get("법령명한글", "")) for l in laws}
    rule_by_id = {str(r["행정규칙일련번호"]): r for r in rules}

    # D1 규칙별 외부 법령 주장 수집
    wanted = {}          # 법령명(norm) -> 원문명
    claims_by_rule = {}  # 규칙일련번호 -> [주장법령명]
    for row in d1:
        rid = str(row["행정규칙일련번호"])
        r = rule_by_id.get(rid)
        head = ((r or {}).get("_조문텍스트") or "")[:1500]
        own = _norm(row["행정규칙명"])
        cl = [c for c in (m.group(1) for m in CLAIM.finditer(head))
              if LAWISH.search(c.strip()) and _norm(c) != own
              and _norm(c) not in law_names]
        if cl:
            claims_by_rule[rid] = list(dict.fromkeys(cl))
            for c in cl:
                wanted.setdefault(_norm(c), c)

    print(f"외부 법령 주장 규칙 {len(claims_by_rule)}건 / 고유 법령명 {len(wanted)}종")

    # ① 법령명 → 법령ID
    resolved = {}   # norm명 -> (법령ID, 정식명) 또는 None
    for i, (key, name) in enumerate(wanted.items(), 1):
        js = _get(SEARCH_URL, {"target": "law", "search": 1, "query": name,
                               "display": 5}, quiet=True)
        body = next(iter(js.values()), {}) if isinstance(js, dict) else {}
        cands = _L(body.get("law")) if isinstance(body, dict) else []
        hit = next((c for c in cands if _norm(c.get("법령명한글")) == key), None) \
            or (cands[0] if cands else None)
        resolved[key] = (hit.get("법령ID"), hit.get("법령명한글")) if hit else None
        if i % 10 == 0:
            print(f"  법령 검색 {i}/{len(wanted)}")

    # ② 법령ID → lsDelegated → 위임 대상 집합
    deleg_cache = {}    # 법령ID -> (대상ID집합, 대상명집합)
    for key, hit in resolved.items():
        if not hit:
            continue
        lid, lname = hit
        if lid in deleg_cache:
            continue
        js = _get(SERVICE_URL, {"target": "lsDelegated", "ID": lid},
                  raw_name=f"deleg_ext_{lid}.json", quiet=True)
        edges = parse_delegated(js, {"법령ID": lid, "법령명한글": lname})
        ids = {str(e["대상ID"]) for e in edges
               if e["대상유형"] == "행정규칙" and e.get("대상ID")}
        names = {_norm(e["대상명"]) for e in edges
                 if e["대상유형"] == "행정규칙" and e.get("대상명")}
        deleg_cache[lid] = (ids, names)
    print(f"lsDelegated 조회 {len(deleg_cache)}건 완료")

    # ③ 판정
    out = []
    for rid, cl in claims_by_rule.items():
        r = rule_by_id[rid]
        rname = _norm(r.get("행정규칙명", ""))
        verdicts = []
        for c in cl:
            hit = resolved.get(_norm(c))
            if not hit:
                verdicts.append((c, "법령검색실패"))
                continue
            lid, lname = hit
            ids, names = deleg_cache.get(lid, (set(), set()))
            if rid in ids or rname in names:
                verdicts.append((c, "타부처위임확인"))
            else:
                verdicts.append((c, "위임없음"))
        confirmed = any(v == "타부처위임확인" for _, v in verdicts)
        out.append({
            "행정규칙일련번호": rid,
            "행정규칙명": r.get("행정규칙명"),
            "종류": r.get("행정규칙종류"),
            "주장법령들": "; ".join(cl)[:250],
            "판정들": "; ".join(f"{c}={v}" for c, v in verdicts)[:300],
            "타부처위임확인": "Y" if confirmed else "",
        })

    path = DATA / "external_claims_resolution.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(out[0].keys()))
        w.writeheader()
        w.writerows(out)
    n_conf = sum(1 for o in out if o["타부처위임확인"])
    print(f"\n저장: {path} ({len(out)}행)")
    print(f"타부처 위임 확인(D1에서 제외할 것): {n_conf}건")
    print(f"위임 미확인(D1 유지): {len(out) - n_conf}건")


if __name__ == "__main__":
    main()
