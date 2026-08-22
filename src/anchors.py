#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
anchors.py — Phase 2: 결정론적 앵커 A1–A4 (OSF 등록 osf.io/[OSF registration; identifier withheld for double-blind review] §3 이행)

역할: 라벨 고정이 아니라 **인간·패널 공통의 외부 검증**.
앵커 영역에서 저자·각 검사의 정확도를 보고하고, 패널 만장일치 ≥99% 게이트를
점검한다. 모호한 것은 전부 앵커에서 제외한다(보수 원칙).

  A1  완료형 인용: "…(대통령령|총리령|○○부령|조례|교육규칙)으로 정한" + 명사구
      (정하는/정한다 제외) → L1=인용
  A2  법률유보: "…(따로 )?법률로 정한다" → L1=인용
  A3  단일형식 위임(대통령령): 문말 "…(은|는|사항은) 대통령령으로 정한다",
      문장 내 형식 언급이 정확히 1개 → L1=위임, L2={대통령령}
  A4  단일형식 위임(총리령/부령): A3과 동일 패턴 → L1=위임, L2={부령}

사용
  python src/anchors.py coverage                  # 전수+보정표본 커버리지
  python src/anchors.py gate --scope pilot|full   # 만장일치 게이트 + 정확도
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PANEL = DATA / "panel"

FORM = r"(대통령령|총리령|[가-힣]{1,8}부령|조례|교육규칙)"
ALL_FORM_MENTIONS = re.compile(r"대통령령|총리령|[가-힣]{1,8}부령|조례|교육규칙|고시|훈령|예규")

RE_A1 = re.compile(FORM + r"으?로\s*정한(?!다)(?=\s*[가-힣])")
RE_A2 = re.compile(r"(따로\s*)?법률로\s*정한다")
RE_A3 = re.compile(r"(은|는|사항은)\s*대통령령으로\s*정한다\s*[.」』]?\s*$")
RE_A4 = re.compile(r"(은|는|사항은)\s*(총리령|[가-힣]{1,8}부령)으로\s*정한다\s*[.」』]?\s*$")


def _norm_form(s):
    return "부령" if (s.endswith("부령") or s == "총리령") else s


def anchor_of(sent):
    """앵커 판정. 반환 (anchor_id, 기대L1, 기대L2집합) 또는 None. 보수적:
    복수 앵커가 동시에 걸리면 제외(모호), A3/A4는 형식 언급이 1개일 때만."""
    s = (sent or "").strip()
    if not s:
        return None
    hits = []
    if RE_A2.search(s):
        hits.append(("A2", "인용", set()))
    # A1 보수 조건: 문장에 능동 위임 표지(정하는/정한다/정할)가 함께 있으면 제외
    # (예: "대통령령으로 정한 범위 안에서 조례로 정한다" — 완료형+위임 혼재 → 모호)
    if RE_A1.search(s) and not re.search(r"정하는|정한다|정할", s):
        hits.append(("A1", "인용", set()))
    n_forms = len(ALL_FORM_MENTIONS.findall(s))
    if n_forms == 1:
        if RE_A3.search(s):
            hits.append(("A3", "위임", {"대통령령"}))
        m = RE_A4.search(s)
        if m:
            hits.append(("A4", "위임", {"부령"}))
    if len(hits) != 1:
        return None  # 무앵커 또는 모호(복수 매치) → 제외
    return hits[0]


def _read(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def cmd_coverage(args):
    for name, path, col in [("full(panel_input)", PANEL / "panel_input.csv", "조문문장"),
                            ("보정표본(goldset)", DATA / "goldset_to_label.csv", "조문문장")]:
        rows = _read(path)
        c = Counter()
        for r in rows:
            a = anchor_of(r.get(col, ""))
            c[a[0] if a else "무앵커"] += 1
        n = len(rows)
        cov = sum(v for k, v in c.items() if k != "무앵커")
        print(f"{name}: n={n}, 앵커 {cov} ({cov/n:.1%})  {dict(sorted(c.items()))}")


def cmd_gate(args):
    scope = args.scope
    rows = _read(DATA / "goldset_to_label.csv") if scope == "pilot" \
        else _read(PANEL / "panel_input.csv")
    tests = [f"T{i}" for i in range(1, 8)]
    labels = {}
    for t in tests:
        p = PANEL / f"labels_{t}_{scope}.csv"
        if not p.exists():
            sys.exit(f"{p} 없음 — 먼저 패널 라벨을 수집하십시오.")
        labels[t] = {r["id"]: (r[f"{t}_L1"], r[f"{t}_L2"]) for r in _read(p)}
    gold = None
    if scope == "pilot":
        gold = {r["id"]: r for r in _read(DATA / "goldset_labeled_v2.csv")}

    anchored = []
    for r in rows:
        a = anchor_of(r.get("조문문장", ""))
        if a:
            anchored.append((r["id"], r.get("조문문장", ""), a))
    print(f"[{scope}] 앵커 영역 {len(anchored)}건 / 전체 {len(rows)}건")

    # 게이트: 앵커 항목별 패널 만장일치(기대 L1과의 일치) — 등록 §3: ≥99%
    unanimous = 0
    disagreements = []
    acc = {t: [0, 0] for t in tests}   # [일치, 총]
    human = [0, 0]
    for rid, sent, (aid, el1, el2) in anchored:
        votes = {t: labels[t].get(rid, ("", ""))[0] for t in tests}
        ok_all = all(v == el1 for v in votes.values())
        unanimous += ok_all
        if not ok_all:
            disagreements.append({"id": rid, "anchor": aid, "기대L1": el1,
                                  "문장": sent[:80],
                                  "votes": {t: v for t, v in votes.items() if v != el1}})
        for t in tests:
            acc[t][1] += 1
            acc[t][0] += votes[t] == el1
        if gold and rid in gold:
            gl = gold[rid].get("L1_위임인가", "").strip()
            if gl:
                human[1] += 1
                human[0] += gl == el1
    rate = unanimous / max(1, len(anchored))
    print(f"패널 만장일치(기대 L1 기준): {unanimous}/{len(anchored)} = {rate:.4f}"
          f"  → {'PASS (≥0.99)' if rate >= 0.99 else 'FAIL — 불일치 전건 분석 필요'}")
    for t in tests:
        print(f"  {t} 앵커 정확도: {acc[t][0]}/{acc[t][1]} = {acc[t][0]/max(1,acc[t][1]):.4f}")
    if human[1]:
        print(f"  저자 앵커 정확도: {human[0]}/{human[1]} = {human[0]/human[1]:.4f}")
    out = PANEL / f"anchor_gate_{scope}.json"
    out.write_text(json.dumps({
        "scope": scope, "n_anchored": len(anchored), "unanimity": round(rate, 5),
        "per_test_accuracy": {t: acc[t][0]/max(1, acc[t][1]) for t in tests},
        "human_accuracy": (human[0]/human[1]) if human[1] else None,
        "disagreements": disagreements,
    }, ensure_ascii=False, indent=2))
    print(f"→ {out}  (불일치 {len(disagreements)}건 전량 수록 — 등록 §3 의무)")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("coverage").set_defaults(func=cmd_coverage)
    g = sub.add_parser("gate")
    g.add_argument("--scope", choices=["pilot", "full"], default="pilot")
    g.set_defaults(func=cmd_gate)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
