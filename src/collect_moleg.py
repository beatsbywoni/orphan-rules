#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
collect_moleg.py — 법제처 국가법령정보 Open API 수집 · 위임그래프 · 결함탐지 · 오라클 구축
v3 — 2026-08-14. 실제 API 응답으로 전 구간 구조 검증 완료.

논문: "Orphan Rules: Court-Validated Detection of Administrative Rules
       Lacking Delegation Authority in Korea's Legal Hierarchy" (AI & Law 투고)

파이프라인
---------
  smoke       권한·응답구조 진단
  casecheck   worked example — 오라클 하급심 판결 1건(인천지법 2025구합50834) 재현
  laws        교육부 소관 법령 수집        → data/laws.jsonl
  admrules    교육부 소관 행정규칙 수집    → data/admrules.jsonl
  delegation  위임 간선 전수 조회          → data/edges.jsonl
  detect      결함 탐지 D1/D1a/D2/D4       → data/findings_*.csv
  goldset     라벨링용 층화표본 추출       → data/goldset_to_label.csv
  oracle      판례·헌재·해석례 스크리닝    → data/oracle_to_label.csv

검증된 사실 (2026-08-14 실측)
---------------------------
* 전체 현행법령 5,607 / 교육부(org=1342000) 법령 273, 행정규칙 261
* lsDelegated 경로: lsDelegated.법령.위임조문정보[].{조정보, 위임정보}
  - 최상위에 행정규칙/자치법규 섹션 없음. 구분은 위임정보.위임구분 값.
  - 하위 키: 위임법령조문정보 / 위임행정규칙조문정보 / 위임자치법규조문정보
  - 항목 필드: 라인텍스트, 링크텍스트, 조항호목 (가이드의 밑줄 표기는 실제로 없음)
  - 위임구분·위임법령제목·일련번호가 병렬 배열 또는 콤마결합 문자열로 옴
* ★ 위임구분 최다값이 '인용법령'(437+/40건 표본). 단순 인용이므로 반드시 제외.
* ★ 검색어의 공백은 AND로 동작: "대외적 구속력" 587 → "대외적 구속력 훈령" 73
* 판례는 search=2(본문검색) 필수. search=1로는 거의 0건.
* 판례 대법원 org=400201 / 하급심 400202
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

import requests

# ---------------------------------------------------------------- 설정

OC = os.environ.get("MOLEG_OC", "test")
SEARCH_URL = "https://www.law.go.kr/DRF/lawSearch.do"
SERVICE_URL = "https://www.law.go.kr/DRF/lawService.do"
SLEEP = 0.4
TIMEOUT = 30
MAX_DISPLAY = 100
MINISTRY_CODE = os.environ.get("MOLEG_ORG", "1342000")   # 교육부

DATA = Path("data")
RAW = DATA / "raw"
for d in (DATA, RAW):
    d.mkdir(exist_ok=True)

SESSION = requests.Session()
SESSION.headers.update({"User-Agent": "orphan-rules-research/0.3"})

DELEGATION_KINDS = {"시행령", "시행규칙", "위임행정규칙", "위임자치법규"}
ADMRULE_TYPES = ("훈령", "예규", "고시", "지침")

LIST_ROOT = {"law": "LawSearch", "eflaw": "LawSearch", "admrul": "AdmRulSearch",
             "ordin": "OrdinSearch", "prec": "PrecSearch", "detc": "DetcSearch",
             "expc": "ExpcSearch"}
LIST_ITEM = {"law": "law", "eflaw": "law", "admrul": "admrul", "ordin": "ordin",
             "prec": "prec", "detc": "Detc", "expc": "expc"}
# ★ 실측(2026-08-15): detc 목록의 항목 키는 대문자 'Detc'. 소문자 'detc'로 읽으면
#   totalCnt=615인데 0건으로 수집되는 무증상 실패가 난다.


# ---------------------------------------------------------------- 저수준

def _get(url, params, raw_name=None, quiet=False):
    params = dict(params)
    params.setdefault("OC", OC)
    params.setdefault("type", "JSON")
    for attempt in range(4):
        try:
            r = SESSION.get(url, params=params, timeout=TIMEOUT)
            r.raise_for_status()
            text = r.text
            if raw_name:
                (RAW / raw_name).write_text(text, encoding="utf-8")
            time.sleep(SLEEP)
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                if not quiet:
                    sys.stderr.write(
                        f"[warn] JSON 아님 (target={params.get('target')}). "
                        f"서비스 미신청 가능. 앞 160자: {text[:160]}\n")
                return None
        except requests.RequestException as e:
            wait = 2 ** attempt
            sys.stderr.write(f"[retry {attempt+1}/4] {e} — {wait}s\n")
            time.sleep(wait)
    return None


def _L(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _split_kinds(v):
    out = []
    for item in _L(v):
        out.extend([s.strip() for s in str(item).split(",") if s.strip()])
    return out


def _norm(s):
    return re.sub(r"\s+", "", str(s or "")).replace("ㆍ", "").replace("·", "")


def _strip_tags(s):
    return re.sub(r"<[^>]*>", " ", str(s or "")).replace("&nbsp;", " ")


def paginate(target, extra=None, limit=None, quiet=False):
    extra = extra or {}
    root, itemkey = LIST_ROOT.get(target), LIST_ITEM.get(target, target)
    page, total, out = 1, None, []
    while True:
        params = {"target": target, "display": MAX_DISPLAY, "page": page}
        params.update(extra)
        js = _get(SEARCH_URL, params,
                  raw_name=f"list_{target}_{page:04d}.json" if not quiet else None,
                  quiet=quiet)
        if js is None:
            break
        body = js.get(root) if root and root in js else next(iter(js.values()), None)
        if not isinstance(body, dict):
            break
        if total is None:
            total = int(body.get("totalCnt") or 0)
            if not quiet:
                print(f"  [{target}] totalCnt = {total}")
        items = _L(body.get(itemkey))
        if not items:      # 항목 키 대소문자 변형 폴백 (예: detc → Detc)
            for alt in (itemkey.capitalize(), itemkey.upper(), itemkey.lower()):
                items = _L(body.get(alt))
                if items:
                    break
        if not items:
            break
        out.extend(items)
        if not quiet:
            print(f"  [{target}] page {page} → {len(out)}/{total}")
        if (total and len(out) >= total) or (limit and len(out) >= limit):
            break
        page += 1
    return out[:limit] if limit else out


# ---------------------------------------------------------------- smoke

def cmd_smoke(args):
    print(f"OC = {OC} / org = {MINISTRY_CODE}\n")
    checks = [
        ("법령 목록", SEARCH_URL, {"target": "law", "display": 1}),
        ("행정규칙 목록", SEARCH_URL,
         {"target": "admrul", "org": MINISTRY_CODE, "nw": 1, "display": 1}),
        ("판례(본문검색)", SEARCH_URL,
         {"target": "prec", "search": 2, "query": "법규명령", "display": 1}),
        ("헌재결정례", SEARCH_URL,
         {"target": "detc", "search": 2, "query": "법규명령", "display": 1}),
        ("법령해석례", SEARCH_URL,
         {"target": "expc", "search": 2, "query": "법규명령", "display": 1}),
        ("자치법규", SEARCH_URL, {"target": "ordin", "display": 1}),
        ("위임법령(교육공무원법)", SERVICE_URL,
         {"target": "lsDelegated", "ID": "001616"}),
    ]
    bad = []
    for name, url, p in checks:
        js = _get(url, p, raw_name=f"smoke_{p['target']}.json")
        if js is None:
            print(f"  ✗ {name}")
            bad.append(name)
            continue
        body = next(iter(js.values()), {})
        total = body.get("totalCnt") if isinstance(body, dict) else None
        print(f"  ✓ {name}" + (f" — totalCnt={total}" if total is not None else ""))
    if bad:
        print("\n실패:", ", ".join(bad))
        print("open.law.go.kr → OPEN API 활용신청 에서 해당 서비스를 추가 체크하십시오.")
    else:
        print("\n전 서비스 정상.")


# ---------------------------------------------------------------- laws / admrules

def cmd_laws(args):
    print(f"현행법령 수집 (org={MINISTRY_CODE}) …")
    rows = paginate("law", extra={"org": MINISTRY_CODE})
    _write_jsonl(DATA / "laws.jsonl", rows)
    k = defaultdict(int)
    for r in rows:
        k[r.get("법령구분명", "?")] += 1
    print("  법형식 분포:", dict(k))


def cmd_admrules(args):
    print(f"행정규칙 목록 수집 (org={MINISTRY_CODE}, 현행) …")
    rows = paginate("admrul", extra={"org": MINISTRY_CODE, "nw": 1})
    k = defaultdict(int)
    for r in rows:
        k[r.get("행정규칙종류", "?")] += 1
    print("  종류 분포:", dict(k))

    print("본문 수집 …")
    out = []
    for i, r in enumerate(rows, 1):
        rid = r.get("행정규칙일련번호")
        if not rid:
            continue
        js = _get(SERVICE_URL, {"target": "admrul", "ID": rid},
                  raw_name=f"admrul_{rid}.json")
        body = next(iter(js.values()), {}) if isinstance(js, dict) else {}
        m = dict(r)
        m["_본문"] = body
        m["_조문텍스트"] = _flatten_text(body)
        out.append(m)
        if i % 25 == 0:
            print(f"  {i}/{len(rows)}")
    _write_jsonl(DATA / "admrules.jsonl", out)


TEXT_KEYS = {"조문내용", "항내용", "호내용", "목내용", "별표내용", "내용"}


def _flatten_text(o, acc=None):
    if acc is None:
        acc = []
    if isinstance(o, dict):
        for k, v in o.items():
            if k in TEXT_KEYS:
                _collect_str(v, acc)   # str뿐 아니라 list[str]·중첩 구조도 수집
            else:
                _flatten_text(v, acc)
    elif isinstance(o, list):
        for v in o:
            _flatten_text(v, acc)
    return "\n".join(acc)


def _collect_str(v, acc):
    """TEXT_KEYS 값 아래의 모든 문자열을 수집 (조문내용이 list[str]로 오는 경우 대응)."""
    if isinstance(v, str):
        acc.append(v)
    elif isinstance(v, list):
        for x in v:
            _collect_str(x, acc)
    elif isinstance(v, dict):
        for x in v.values():
            _collect_str(x, acc)


# ---------------------------------------------------------------- delegation

def cmd_delegation(args):
    laws = _read_jsonl(DATA / "laws.jsonl")
    if not laws:
        sys.exit("laws.jsonl 없음. 먼저 `laws` 실행.")
    print(f"위임법령 조회 {len(laws)}건 …")
    edges = []
    for i, law in enumerate(laws, 1):
        lid = law.get("법령ID")
        if not lid:
            continue
        js = _get(SERVICE_URL, {"target": "lsDelegated", "ID": lid},
                  raw_name=f"deleg_{lid}.json")
        edges.extend(parse_delegated(js, law))
        if i % 20 == 0:
            print(f"  {i}/{len(laws)} — 간선 {len(edges)}")
    _write_jsonl(DATA / "edges.jsonl", edges)
    c = defaultdict(int)
    for e in edges:
        c[e["위임구분"]] += 1
    print("  위임구분 분포:", dict(c))


FORM_PATTERNS = [
    ("대통령령", re.compile(r"대통령령")),
    ("부령",     re.compile(r"(총리령|[가-힣]{1,8}부령)")),
    ("고시",     re.compile(r"고시")),
    ("훈령",     re.compile(r"훈령")),
    ("예규",     re.compile(r"예규")),
    ("조례",     re.compile(r"조례|교육규칙")),
    ("미특정",   re.compile(r"(장관|청장|위원장|교육감|관청)이?\s*(정하|지정하)")),
]


def _extract_form(*texts):
    blob = " ".join(t for t in texts if t)
    for label, pat in FORM_PATTERNS:
        if pat.search(blob):
            return label
    return None


def parse_delegated(js, law):
    edges = []
    if not isinstance(js, dict):
        return edges
    sec = (js.get("lsDelegated") or {}).get("법령") or {}
    src_id, src_name = law.get("법령ID"), law.get("법령명한글")

    for item in _L(sec.get("위임조문정보")):
        jo = item.get("조정보") or {}
        for wi in _L(item.get("위임정보")):
            if not isinstance(wi, dict):
                continue
            kinds = set(_split_kinds(wi.get("위임구분")))
            real = kinds & DELEGATION_KINDS

            for a in _L(wi.get("위임행정규칙조문정보")):
                edges.append(_edge(src_id, src_name, jo, "행정규칙",
                                   a.get("위임행정규칙일련번호"),
                                   a.get("위임행정규칙제목"), a,
                                   "위임행정규칙" if "위임행정규칙" in kinds
                                   else ",".join(sorted(kinds))))
            for a in _L(wi.get("위임자치법규조문정보")):
                edges.append(_edge(src_id, src_name, jo, "자치법규",
                                   a.get("위임자치법규일련번호"),
                                   a.get("위임자치법규제목"), a,
                                   "위임자치법규" if "위임자치법규" in kinds
                                   else ",".join(sorted(kinds))))
            if not real & {"시행령", "시행규칙"}:
                continue          # ★ 인용법령 제외
            titles = _L(wi.get("위임법령제목"))
            seqs = _L(wi.get("위임법령일련번호"))
            t_title = titles[0] if len(titles) == 1 else "|".join(map(str, titles))
            t_seq = seqs[0] if len(seqs) == 1 else "|".join(map(str, seqs))
            for a in _L(wi.get("위임법령조문정보")):
                edges.append(_edge(src_id, src_name, jo, "법령", t_seq, t_title, a,
                                   ",".join(sorted(real & {"시행령", "시행규칙"})),
                                   ambiguous=len(titles) > 1))
    return edges


def _edge(src_id, src_name, jo, tgt_type, tgt_id, tgt_name, a, kind,
          ambiguous=False):
    line, link = a.get("라인텍스트"), a.get("링크텍스트")
    return {"상위법령ID": src_id, "상위법령명": src_name,
            "상위조문번호": jo.get("조문번호"), "상위조문제목": jo.get("조문제목"),
            "위임구분": kind, "위임된형식": _extract_form(line, link),
            "라인텍스트": line, "링크텍스트": link,
            "대상유형": tgt_type, "대상ID": tgt_id, "대상명": tgt_name,
            "대상조항호목": a.get("조항호목"), "제목매칭모호": ambiguous}


# ---------------------------------------------------------------- detect

CLAIM_PAT = re.compile(r"[「『]\s*([^」』]{2,50}?)\s*[」』]\s*"
                       r"(?:제\s*(\d+)\s*조(?:의\s*(\d+))?)?")


def cmd_detect(args):
    laws = _read_jsonl(DATA / "laws.jsonl")
    rules = _read_jsonl(DATA / "admrules.jsonl")
    edges = _read_jsonl(DATA / "edges.jsonl")
    if not rules:
        sys.exit("admrules.jsonl 없음.")

    deleg_ids, deleg_names = set(), set()
    for e in edges:
        if e["대상유형"] == "행정규칙":
            if e.get("대상ID"):
                deleg_ids.add(str(e["대상ID"]))
            if e.get("대상명"):
                deleg_names.add(_norm(e["대상명"]))

    # 법률별 위임 보유 현황 (D1a 판정용)
    law_by_name = {_norm(l.get("법령명한글", "")): l for l in laws}
    law_has_edge = defaultdict(lambda: {"시행령": 0, "행정규칙": 0})
    for e in edges:
        key = _norm(e.get("상위법령명", ""))
        if e["대상유형"] == "법령":
            law_has_edge[key]["시행령"] += 1
        elif e["대상유형"] == "행정규칙":
            law_has_edge[key]["행정규칙"] += 1

    scoped = [r for r in rules
              if any(t in str(r.get("행정규칙종류", "")) for t in ADMRULE_TYPES)]

    # ---- D1 / D1a
    d1 = []
    for r in scoped:
        rid = str(r.get("행정규칙일련번호", ""))
        rname = _norm(r.get("행정규칙명", ""))
        if rid in deleg_ids or rname in deleg_names:
            continue
        head = (r.get("_조문텍스트") or "")[:1500]
        claims = [m.group(1) for m in CLAIM_PAT.finditer(head)]
        claimed_law = next((c for c in claims if _norm(c) in law_by_name), None)
        sub = ""
        if claimed_law:
            k = _norm(claimed_law)
            if law_has_edge[k]["시행령"] > 0 and law_has_edge[k]["행정규칙"] == 0:
                sub = "D1a_재위임단절후보"
        d1.append({"행정규칙일련번호": rid, "행정규칙명": r.get("행정규칙명"),
                   "종류": r.get("행정규칙종류"), "소관부처": r.get("소관부처명"),
                   "발령일자": r.get("발령일자"), "시행일자": r.get("시행일자"),
                   "주장근거법령": claimed_law or "", "하위분류": sub,
                   "상세링크": r.get("행정규칙상세링크")})

    # ---- D2
    d2 = []
    for e in edges:
        f, t = e.get("위임된형식"), e.get("대상유형")
        if t == "행정규칙" and f in ("대통령령", "부령"):
            d2.append({**e, "결함": f"위임형식={f} → 실제=행정규칙"})
        elif t == "행정규칙" and f == "미특정":
            d2.append({**e, "결함": "형식 미특정 위임(회색지대)"})

    # ---- D4
    edge_pairs = {(_norm(e.get("상위법령명", "")), str(e.get("대상ID")))
                  for e in edges}
    d4 = []
    for r in scoped:
        head = (r.get("_조문텍스트") or "")[:1500]
        rid = str(r.get("행정규칙일련번호", ""))
        claims = [(m.group(1), m.group(2)) for m in CLAIM_PAT.finditer(head)]
        if not claims:
            continue
        if all((_norm(c[0]), rid) not in edge_pairs for c in claims):
            top = claims[0]
            d4.append({"행정규칙일련번호": rid, "행정규칙명": r.get("행정규칙명"),
                       "종류": r.get("행정규칙종류"), "주장법령": top[0],
                       "주장조문": top[1], "주장건수": len(claims),
                       "주장법령_수집목록에있음": _norm(top[0]) in law_by_name})

    _write_csv(DATA / "findings_D1_orphan.csv", d1)
    _write_csv(DATA / "findings_D2_mismatch.csv", d2)
    _write_csv(DATA / "findings_D4_falseclaim.csv", d4)

    n = len(scoped)
    summary = {"법령수": len(laws), "행정규칙수": len(rules),
               "훈령예규고시지침": n, "위임간선": len(edges),
               "행정규칙피위임": len(deleg_ids),
               "D1_고아규칙": len(d1),
               "D1a_재위임단절후보": sum(1 for x in d1 if x["하위분류"]),
               "D1_비율": round(len(d1) / n, 4) if n else None,
               "D2_형식불일치": len(d2), "D4_근거참칭": len(d4)}
    (DATA / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("\n[판단] D1 비율 ≥5% → A안 확정 / 1~5% → D2·D4 전면 / <1% → 설계 재검토")


# ---------------------------------------------------------------- goldset

def cmd_goldset(args):
    """위임조항 라벨링용 층화표본 추출.

    - 위임구분별 비례 배분 + '미특정' 형식 과대표집(희소·난이도 높음)
    - 파일럿(이중코딩) 20% 를 별도 플래그
    - 출력 CSV의 라벨 열은 비워둠 → 변호사가 채우고, 저자가 조정
    """
    edges = _read_jsonl(DATA / "edges.jsonl")
    if not edges:
        sys.exit("edges.jsonl 없음. 먼저 `delegation` 실행.")
    rng = random.Random(args.seed)
    n_total = args.n

    strata = defaultdict(list)
    for e in edges:
        key = (e.get("위임구분", "?"), e.get("위임된형식") or "없음")
        strata[key].append(e)

    # 배분: 기본 비례 + 미특정/None 가중 3배
    weights = {}
    for key, rows in strata.items():
        w = len(rows)
        if key[1] in ("미특정", "없음"):
            w *= 3
        weights[key] = w
    tw = sum(weights.values()) or 1

    picked = []
    for key, rows in strata.items():
        k = max(1, round(n_total * weights[key] / tw))
        picked.extend(rng.sample(rows, min(k, len(rows))))
    rng.shuffle(picked)
    picked = picked[:n_total]

    n_pilot = max(1, int(len(picked) * args.pilot))
    out = []
    for i, e in enumerate(picked):
        out.append({
            "id": f"G{i+1:04d}",
            "파일럿": "Y" if i < n_pilot else "",
            "상위법령명": e.get("상위법령명"),
            "상위조문번호": e.get("상위조문번호"),
            "상위조문제목": e.get("상위조문제목"),
            "조문문장": e.get("라인텍스트"),
            "위임표지어구": e.get("링크텍스트"),
            "API_위임구분": e.get("위임구분"),
            "자동추출_위임형식": e.get("위임된형식"),
            "대상유형": e.get("대상유형"),
            "대상명": e.get("대상명"),
            # ↓ 아래 4개는 라벨러가 채움
            "L1_위임인가": "",          # 위임 / 인용 / 판단불가
            "L2_위임된법형식": "",      # 대통령령/부령/고시/훈령/예규/조례/미특정/해당없음
            "L3_확신도": "",            # 1~5
            "L4_메모": "",
        })
    path = DATA / "goldset_to_label.csv"
    _write_csv(path, out)
    print(f"\n층화 배분:")
    for key, rows in sorted(strata.items(), key=lambda x: -len(x[1]))[:12]:
        print(f"  {key}: 모집단 {len(rows)}")
    print(f"\n총 {len(out)}건 추출, 그중 파일럿(이중코딩) {n_pilot}건.")
    print(f"→ {path}")
    print("   L1~L4 열을 라벨러가 채웁니다. 지침은 docs/04_annotation_protocol.md")


# ---------------------------------------------------------------- oracle

# 공백 = AND (실측 확인). 정밀도 높은 순.
ORACLE_QUERIES = [
    ("위임한계를 벗어나", {}),
    ("위임범위를 벗어나", {}),
    ("대외적 구속력 훈령", {}),
    ("대외적 구속력 고시", {}),
    ("대외적 구속력 예규", {}),
    ("법령보충적 행정규칙", {}),
    ("위임 없이 훈령", {}),
    ("위임 없이 고시", {}),
    ("행정규칙 위임 무효", {}),
    ("재위임", {}),
    ("대외적 구속력", {"org": "400201"}),   # 대법원 한정
    ("법규명령 행정규칙 효력", {}),
]

STRONG = [r"위임\s*없", r"위임범위를?\s*벗어", r"위임의?\s*한계",
          r"대외적\s*구속력이?\s*(없|인정되지)", r"효력이?\s*(없|인정)",
          r"무효", r"재위임"]
WEAK = ["위임", "법규명령", "행정규칙", "훈령", "예규", "고시",
        "법령보충", "구속력", "상위법령"]


def cmd_oracle(args):
    """판례·헌재결정례·법령해석례를 스크리닝해 수작업 라벨링 대상 산출."""
    targets = args.targets.split(",")
    pool = {}          # (target, id) -> row
    print("1단계: 검색 스크리닝 (공백=AND)")
    for tg in targets:
        for q, extra in ORACLE_QUERIES:
            rows = paginate(tg, extra={"search": 2, "query": q, **extra},
                            limit=args.per_query, quiet=True)
            new = 0
            for r in rows:
                rid = (r.get("판례일련번호") or r.get("헌재결정례일련번호")
                       or r.get("법령해석례일련번호") or r.get("id"))
                key = (tg, str(rid))
                if key not in pool:
                    r["_target"], r["_쿼리"] = tg, q
                    pool[key] = r
                    new += 1
                else:
                    pool[key]["_쿼리"] += f"; {q}"
            print(f"  [{tg}] '{q}' → {len(rows)}건 (신규 {new}) / 누적 {len(pool)}")

    print(f"\n2단계: 본문 조회 및 자동 점수화 ({len(pool)}건)")
    scored = []
    for i, ((tg, rid), r) in enumerate(pool.items(), 1):
        js = _get(SERVICE_URL, {"target": tg, "ID": rid},
                  raw_name=f"{tg}_{rid}.json", quiet=True)
        body = next(iter(js.values()), {}) if isinstance(js, dict) else {}
        if not isinstance(body, dict):
            body = {}
        head = _strip_tags(body.get("판시사항") or body.get("판시사항내용")
                           or body.get("질의요지") or "")
        gist = _strip_tags(body.get("판결요지") or body.get("결정요지")
                           or body.get("회답") or "")
        blob = head + " " + gist
        s_hits = [p for p in STRONG if re.search(p, blob)]
        w_hits = [w for w in WEAK if w in blob]
        score = len(s_hits) * 3 + len(w_hits)
        tier = "A" if len(s_hits) >= 2 and len(w_hits) >= 3 else \
               "B" if len(s_hits) >= 1 and len(w_hits) >= 2 else "C"
        scored.append({
            "tier": tier, "score": score, "source": tg, "id": rid,
            "사건명": r.get("사건명") or r.get("안건명") or r.get("법령해석례명"),
            "사건번호": r.get("사건번호") or r.get("안건번호"),
            "선고일자": r.get("선고일자") or r.get("종국일자") or r.get("해석일자"),
            "법원": r.get("법원명") or r.get("기관명"),
            "사건종류": r.get("사건종류명"),
            "매칭쿼리": r.get("_쿼리"),
            "강한신호": ",".join(s_hits),
            "판시사항": head[:400],
            "요지": gist[:400],
            "링크": r.get("판례상세링크") or r.get("상세링크"),
            # ↓ 라벨러가 채움
            "O1_무효판단": "",       # Y / N / 부분 / 무관
            "O2_결함유형": "",       # D1 / D2 / D3 / 기타
            "O3_대상규정명": "",
            "O4_대상규정일련번호": "",
            "O5_메모": "",
        })
        if i % 25 == 0:
            print(f"  {i}/{len(pool)}")

    scored.sort(key=lambda x: (-{"A": 2, "B": 1, "C": 0}[x["tier"]], -x["score"]))
    out_path = DATA / getattr(args, "out", "oracle_to_label.csv")
    _write_csv(out_path, scored)
    t = defaultdict(int)
    for s in scored:
        t[s["tier"]] += 1
    print(f"\n티어 분포: {dict(t)}")
    print("  A = 우선 판독 (강한 신호 2개 이상)")
    print("  B = 2순위 / C = 보류")
    print(f"→ {out_path}")
    print("   O1~O5 열을 채우면 검증 라벨셋이 됩니다. 지침은 docs/05_oracle_protocol.md")


# ---------------------------------------------------------------- casecheck

def cmd_casecheck(args):
    print("=== worked example: 오라클 하급심 판결 재현 (인천지법 2025구합50834) ===\n")
    js = _get(SEARCH_URL, {"target": "admrul", "search": 1,
                           "query": "교육공무원 인사관리규정", "display": 5})
    rows = [r for r in _L((next(iter(js.values()), {}) or {}).get("admrul"))
            if "교육공무원 인사관리규정" in str(r.get("행정규칙명"))]
    if not rows:
        print("  행정규칙을 찾지 못했습니다.")
        return
    r = rows[0]
    print(f"  대상: {r['행정규칙명']} ({r['행정규칙종류']}), "
          f"일련번호 {r['행정규칙일련번호']}, 소관 {r.get('소관부처명')}\n")
    for name, lid in (("교육공무원법", "001616"), ("교육공무원임용령", "002583")):
        d = _get(SERVICE_URL, {"target": "lsDelegated", "ID": lid})
        edges = parse_delegated(d, {"법령ID": lid, "법령명한글": name})
        adm = [e for e in edges if e["대상유형"] == "행정규칙"]
        hit = [e for e in adm if "인사관리규정" in str(e.get("대상명"))]
        print(f"  {name}")
        print("    위임행정규칙 %d건: %s" % (
            len(adm),
            ", ".join(f"{e['대상명']}(제{e['상위조문번호']}조)" for e in adm[:8])
            or "없음"))
        print(f"    → 「교육공무원 인사관리규정」 포함: "
              f"{'있음' if hit else '★ 없음 = D1 고아규칙'}\n")
    print("  판결 요지: 교육공무원법 §44⑧이 휴직제도 운영사항을 대통령령에 위임했으나")
    print("  교육공무원임용령은 연수휴직 의무복무를 정하지 않았고, 교육부훈령에")
    print("  재위임하지도 않았으므로 인사관리규정 §24는 대외적 구속력 없음.")


# ---------------------------------------------------------------- I/O

def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"  저장: {path} ({len(rows)}행)")


def _read_jsonl(path):
    p = Path(path)
    if not p.exists():
        return []
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _write_csv(path, rows):
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        print(f"  저장: {path} (0행)")
        return
    keys = list(rows[0].keys())
    for r in rows:
        for k in r:
            if k not in keys:
                keys.append(k)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    print(f"  저장: {path} ({len(rows)}행)")


def main():
    p = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    for n, h in (("smoke", "권한·응답구조 진단"),
                 ("casecheck", "오라클 하급심 판결 재현 예시"),
                 ("laws", "소관 법령 수집"),
                 ("admrules", "행정규칙 목록+본문 수집"),
                 ("delegation", "위임 간선 전수 조회"),
                 ("detect", "결함 탐지 D1/D1a/D2/D4")):
        sub.add_parser(n, help=h)

    g = sub.add_parser("goldset", help="라벨링용 층화표본 추출")
    g.add_argument("--n", type=int, default=500)
    g.add_argument("--pilot", type=float, default=0.2, help="이중코딩 비율")
    g.add_argument("--seed", type=int, default=20260814)

    o = sub.add_parser("oracle", help="판례·헌재·해석례 스크리닝")
    o.add_argument("--targets", default="prec,detc,expc")
    o.add_argument("--per-query", type=int, default=100,
                   dest="per_query", help="쿼리당 최대 수집 건수")
    o.add_argument("--out", default="oracle_to_label.csv",
                   help="출력 파일명 (data/ 아래). 부분 재실행 시 다른 이름 지정")

    a = p.parse_args()
    globals()[f"cmd_{a.cmd}"](a)


if __name__ == "__main__":
    main()
