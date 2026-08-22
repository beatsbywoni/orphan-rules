#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""retest_kappa.py — 9월 intra-annotator 재검사 집계.

채운 라벨 파일(xlsx 또는 csv)과 8월 원본 라벨을 대조해 L1·L2 일치도를 낸다.
60건 전체와, 저자에게 사전 노출 이력이 있는 2건(G0106·G0136)을 제외한 58건을
모두 보고한다(편차 로그 P-2026-08-20-5).

사용:
    python3 src/retest_kappa.py [--file data/goldset_retest_sept.xlsx] [--apply]

--apply 를 주면 draft/paper_draft_v2.md 의 자리표시자를 산출 문장으로 교체한다
(교체 전 .paper_draft_v2.bak* 백업 생성).
"""
import argparse, csv, re, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXPOSED = {"G0106", "G0136"}          # docs/22 §4.3 에서 저자에게 노출된 항목
PLACEHOLDER = " [결과 확보 후 수치 기입]."   # 앞 공백·뒤 마침표까지 통째로 교체한다


# ── 읽기 ────────────────────────────────────────────────────────────────
def read_labels(path: Path):
    if path.suffix.lower() in (".xlsx", ".xlsm"):
        try:
            from openpyxl import load_workbook
        except ImportError:
            sys.exit("openpyxl 없음:  .venv/bin/pip install openpyxl")
        wb = load_workbook(path, data_only=True)
        ws = wb["라벨링"] if "라벨링" in wb.sheetnames else wb[wb.sheetnames[0]]
        rows = list(ws.iter_rows(values_only=True))
        head = [str(h).strip() if h is not None else "" for h in rows[0]]
        out = []
        for r in rows[1:]:
            if r[0] is None:
                continue
            out.append({head[i]: ("" if v is None else str(v).strip())
                        for i, v in enumerate(r) if i < len(head)})
        return out
    return [{k.strip(): (v or "").strip() for k, v in r.items()}
            for r in csv.DictReader(open(path, encoding="utf-8-sig"))]


def as_set(v):
    return frozenset(x.strip() for x in str(v).split("|") if x.strip())


# ── 통계 ────────────────────────────────────────────────────────────────
def agreement_stats(pairs, label):
    """pairs = [(원본, 재검사)]. 관측일치도·Cohen κ·PABAK·Gwet AC1 을 낸다."""
    n = len(pairs)
    if n == 0:
        return None
    po = sum(1 for a, b in pairs if a == b) / n
    cats = sorted({a for a, _ in pairs} | {b for _, b in pairs})
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe = sum((ca[c] / n) * (cb[c] / n) for c in cats)
    kappa = None if abs(1 - pe) < 1e-12 else (po - pe) / (1 - pe)
    q = len(cats)
    pabak = (q * po - 1) / (q - 1) if q > 1 else None
    # Gwet AC1
    ac1 = None
    if q > 1:
        pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
        pe_g = sum(pi[c] * (1 - pi[c]) for c in cats) / (q - 1)
        ac1 = None if abs(1 - pe_g) < 1e-12 else (po - pe_g) / (1 - pe_g)
    return {"label": label, "n": n, "agree": po, "kappa": kappa, "pabak": pabak,
            "ac1": ac1, "n_cats": q, "pe": pe,
            "disagreements": [(i, a, b) for i, (a, b) in enumerate(pairs) if a != b],
            "dist_orig": dict(ca), "dist_retest": dict(cb)}


def fmt(x, nd=3):
    return "n/a" if x is None else f"{x:.{nd}f}"


def block(st, ids):
    if st is None:
        return "  (해당 없음)\n"
    d = st["disagreements"]
    s = (f"  n = {st['n']} · 관측일치도 {st['agree']*100:.1f}% "
         f"({st['n']-len(d)}/{st['n']})\n"
         f"  Cohen κ = {fmt(st['kappa'])} · PABAK = {fmt(st['pabak'])} "
         f"· Gwet AC1 = {fmt(st['ac1'])}\n")
    if d:
        s += "  불일치:\n"
        for i, a, b in d:
            s += f"    {ids[i]}  8월 '{a}'  →  9월 '{b}'\n"
    else:
        s += "  불일치 없음\n"
    return s


# ── 원고 문장 ───────────────────────────────────────────────────────────
def sentence(l1_60, l1_58, l2_60):
    def k(st):
        """κ 가 정의되지 않는 경우(양쪽 모두 단일 범주)는 그 사실을 말한다."""
        if st["kappa"] is None:
            return None
        return f"{st['kappa']:.2f}"

    if l1_60["agree"] == 1.0 and l2_60["agree"] == 1.0:
        kk = k(l1_60)
        if kk is None:
            stat = ("raw agreement 1.000 on both L1 and L2; κ is undefined here because "
                    "every item in the sample falls in one class, and the "
                    "prevalence-adjusted PABAK is 1.00")
        else:
            stat = f"raw agreement 1.000 on both L1 and L2, Cohen's κ = {kk}"
        core = ("The re-test reproduced the original labels exactly on all 60 items "
                f"({stat}). Excluding the two items whose identifiers appeared in a "
                "public adjudication note before the re-test, the 58 remaining items "
                "also reproduce exactly.")
    else:
        k60, k58 = k(l1_60), k(l1_58)
        core = (f"On the fresh 60-item sample the author reproduced the original L1 "
                f"labels on {l1_60['agree']*100:.1f}% of items "
                + (f"(Cohen's κ = {k60}, PABAK = {fmt(l1_60['pabak'],2)})"
                   if k60 else f"(κ undefined at this prevalence; "
                               f"PABAK = {fmt(l1_60['pabak'],2)})")
                + f"; L2 raw agreement was {l2_60['agree']*100:.1f}%. "
                f"Excluding the two items whose identifiers appeared in a public "
                f"adjudication note before the re-test, L1 agreement over the "
                f"remaining 58 was {l1_58['agree']*100:.1f}%"
                + (f" (Cohen's κ = {k58})." if k58 else "."))
    return ("The re-test was completed on the scheduled date. " + core +
            " Every re-test label is released alongside the original.")


# ── main ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/goldset_retest_sept.xlsx")
    ap.add_argument("--orig", default="data/goldset_labeled_v2.csv")
    ap.add_argument("--apply", action="store_true", help="원고 자리표시자 교체")
    a = ap.parse_args()

    fp = ROOT / a.file
    if not fp.exists():
        sys.exit(f"파일 없음: {fp}\n  라벨을 채운 파일 경로를 --file 로 지정할 것.")
    new = read_labels(fp)
    orig = {r["id"]: r for r in csv.DictReader(open(ROOT / a.orig, encoding="utf-8-sig"))}

    blank = [r["id"] for r in new if not r.get("L1_위임인가")]
    if blank:
        sys.exit(f"L1 미입력 {len(blank)}건: {', '.join(blank[:10])}"
                 f"{' …' if len(blank) > 10 else ''}\n  전부 채운 뒤 다시 실행할 것.")
    missing = [r["id"] for r in new if r["id"] not in orig]
    if missing:
        sys.exit(f"8월 원본에 없는 id: {', '.join(missing)}")

    ids_all = [r["id"] for r in new]
    ids_58 = [i for i in ids_all if i not in EXPOSED]

    def pairs(ids, col, setwise=False):
        by = {r["id"]: r for r in new}
        f = as_set if setwise else (lambda x: str(x).strip())
        return [(f(orig[i][col]), f(by[i].get(col, ""))) for i in ids]

    l1_60 = agreement_stats(pairs(ids_all, "L1_위임인가"), "L1 (60건)")
    l1_58 = agreement_stats(pairs(ids_58, "L1_위임인가"), "L1 (58건)")
    l2_60 = agreement_stats(pairs(ids_all, "L2_위임된법형식", True), "L2 (60건)")
    l2_58 = agreement_stats(pairs(ids_58, "L2_위임된법형식", True), "L2 (58건)")

    def setlabel(st):
        for k in ("disagreements",):
            st[k] = [(i, "|".join(sorted(a)) or "(빈값)", "|".join(sorted(b)) or "(빈값)")
                     for i, a, b in st[k]]
        return st
    l2_60, l2_58 = setlabel(l2_60), setlabel(l2_58)

    print("\n=== 9월 재검사 결과 ===\n")
    for st, ids in ((l1_60, ids_all), (l1_58, ids_58), (l2_60, ids_all), (l2_58, ids_58)):
        print(st["label"]); print(block(st, ids))

    sent = sentence(l1_60, l1_58, l2_60)
    print("=== 원고 §6.2 에 들어갈 문장 ===\n" + sent.strip() + "\n")

    doc = ROOT / "docs" / "31_sept_retest_result.md"
    doc.write_text(
        "# 9월 재검사 결과 (intra-annotator)\n\n"
        f"입력 파일: `{a.file}` · 원본: `{a.orig}`\n\n"
        "표본 60건은 8월 재검사(60건)와 **겹치지 않는다**. "
        "G0106·G0136 은 docs/22 §4.3 에서 식별자가 저자에게 노출된 이력이 있어 "
        "(편차 로그 P-2026-08-20-5), 전체 60건과 이 둘을 제외한 58건을 모두 보고한다.\n\n"
        "## L1 (위임/인용/판단불가)\n\n```\n" + block(l1_60, ids_all) + block(l1_58, ids_58) +
        "```\n\n## L2 (법형식, 집합 비교)\n\n```\n" + block(l2_60, ids_all) + block(l2_58, ids_58) +
        "```\n\n## 지표 해석\n\n"
        "L1 은 원본 분포가 극단적으로 치우쳐 있어(위임 58 / 인용 2) Cohen κ 가 "
        "유병률 역설에 취약하다. 그래서 관측일치도·PABAK·Gwet AC1 을 함께 적는다. "
        "**주 보고값은 등록대로 Cohen κ 이고 나머지는 기술통계**다.\n\n"
        "## 원고 문장\n\n> " + sent.strip() + "\n",
        encoding="utf-8")
    print(f"→ {doc.relative_to(ROOT)}")

    if a.apply:
        m = ROOT / "draft" / "paper_draft_v2.md"
        s = m.read_text(encoding="utf-8")
        if PLACEHOLDER not in s:
            print("\n[건너뜀] 원고에 자리표시자가 없다. 이미 반영된 것으로 보인다.")
        else:
            n = 1
            while (m.parent / f".paper_draft_v2.bak{n}").exists():
                n += 1
            (m.parent / f".paper_draft_v2.bak{n}").write_text(s, encoding="utf-8")
            m.write_text(s.replace(PLACEHOLDER, ". " + sent.strip(), 1), encoding="utf-8")
            print(f"\n[적용] 원고 자리표시자 교체 완료 (백업 .paper_draft_v2.bak{n})")


if __name__ == "__main__":
    main()
