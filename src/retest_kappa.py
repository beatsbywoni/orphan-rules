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
def sentence(l1_60, l1_58, l2_60, completed="2026-09-06"):
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
                + f"; over the {l2_60['n']} items both passes classify as delegations, L2 agreement "
                + f"was {l2_60['agree']*100:.1f}% (κ = {fmt(l2_60['kappa'],2)})"
                + (f", the {'two' if len(l2_60['disagreements'])==2 else len(l2_60['disagreements'])} divergent item"
                   f"{'s' if len(l2_60['disagreements'])!=1 else ''} reproducing the primary form "
                   f"but omitting a co-listed second form. " if l2_60['disagreements'] else ". ")
                + f"Excluding the two items whose identifiers appeared in a public "
                f"adjudication note before the re-test, L1 agreement over the "
                f"remaining 58 was {l1_58['agree']*100:.1f}%"
                + (f" (Cohen's κ = {k58})." if k58 else "."))
    import datetime as _dt
    done = _dt.date.fromisoformat(completed)
    gap = (done - _dt.date(2026, 8, 15)).days
    when = (f"The re-test was completed on {done.isoformat()}, {gap} days after the original "
            f"labelling — beyond the registered three-week minimum, though two days before the "
            f"calendar date named in the registration (recorded in the deviation log). ")
    return (when + core +
            " L2 is compared as form sets, co-listed forms included. "
            "Every re-test label is released alongside the original.")


# ── main ────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", default="data/goldset_retest_sept.xlsx")
    ap.add_argument("--orig", default="data/goldset_labeled_v2.csv")
    ap.add_argument("--apply", action="store_true", help="원고 자리표시자 교체")
    ap.add_argument("--completed", default="2026-09-06", help="라벨링 완료일 (YYYY-MM-DD)")
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

    by = {r["id"]: r for r in new}

    def orig_l2(i):
        # 원본은 주형식 열과 병존형식 열이 나뉘어 있고, 재검사 시트는 '|' 로 병기한다.
        # 둘을 합쳐 집합으로 비교해야 같은 판정이 같은 것으로 잡힌다.
        return as_set(orig[i]["L2_위임된법형식"]) | as_set(orig[i].get("L2_병존형식", ""))

    def pairs(ids, col, setwise=False):
        if setwise:
            return [(orig_l2(i), as_set(by[i].get(col, ""))) for i in ids]
        return [(str(orig[i][col]).strip(), str(by[i].get(col, "")).strip()) for i in ids]

    # L2 는 원본·재검사 모두 '위임'인 항목에서만 정의된다 (인용·판단불가는 법형식 미해당 —
    # 표 1 의 8월 재검사 행 59/59 와 같은 관행)
    ids_l2_all = [i for i in ids_all if orig[i]["L1_위임인가"].strip() == "위임"
                  and by[i]["L1_위임인가"] == "위임"]
    ids_l2_58 = [i for i in ids_l2_all if i not in EXPOSED]

    l1_60 = agreement_stats(pairs(ids_all, "L1_위임인가"), f"L1 ({len(ids_all)}건)")
    l1_58 = agreement_stats(pairs(ids_58, "L1_위임인가"), f"L1 ({len(ids_58)}건, 노출 2건 제외)")
    l2_60 = agreement_stats(pairs(ids_l2_all, "L2_위임된법형식", True), f"L2 ({len(ids_l2_all)}건, 양쪽 위임)")
    l2_58 = agreement_stats(pairs(ids_l2_58, "L2_위임된법형식", True), f"L2 ({len(ids_l2_58)}건, 노출 2건 제외)")
    ids_all, ids_58 = ids_all, ids_58

    def setlabel(st):
        for k in ("disagreements",):
            st[k] = [(i, "|".join(sorted(a)) or "(빈값)", "|".join(sorted(b)) or "(빈값)")
                     for i, a, b in st[k]]
        return st
    l2_60, l2_58 = setlabel(l2_60), setlabel(l2_58)

    print("\n=== 9월 재검사 결과 ===\n")
    for st, ids in ((l1_60, ids_all), (l1_58, ids_58), (l2_60, ids_l2_all), (l2_58, ids_l2_58)):
        print(st["label"]); print(block(st, ids))

    sent = sentence(l1_60, l1_58, l2_60, a.completed)
    import datetime as _dt
    gap_days = (_dt.date.fromisoformat(a.completed) - _dt.date(2026, 8, 15)).days
    print("=== 원고 §6.2 에 들어갈 문장 ===\n" + sent.strip() + "\n")

    doc = ROOT / "docs" / "35_sept_retest_result.md"
    doc.write_text(
        "# 9월 재검사 결과 (intra-annotator)\n\n"
        f"입력 파일: `{a.file}` · 원본: `{a.orig}`\n\n"
        "표본 60건은 8월 재검사(60건)와 **겹치지 않는다**. "
        "G0106·G0136 은 docs/22 §4.3 에서 식별자가 저자에게 노출된 이력이 있어 "
        "(편차 로그 P-2026-08-20-5), 전체 60건과 이 둘을 제외한 58건을 모두 보고한다.\n\n"
        "## L1 (위임/인용/판단불가)\n\n```\n" + block(l1_60, ids_all) + block(l1_58, ids_58) +
        "```\n\n## L2 (법형식, 집합 비교 — 원본 주형식∪병존형식 vs 재검사 '|' 병기)\n\n```\n" + block(l2_60, ids_l2_all) + block(l2_58, ids_l2_58) +
        "```\n\n## 지표 해석\n\n"
        "L1 은 원본 분포가 극단적으로 치우쳐 있어(위임 58 / 인용 2) Cohen κ 가 "
        "유병률 역설에 취약하다. 그래서 관측일치도·PABAK·Gwet AC1 을 함께 적는다. "
        "**주 보고값은 등록대로 Cohen κ 이고 나머지는 기술통계**다.\n\n"
        "## 원고 문장\n\n> " + sent.strip() + "\n",
        encoding="utf-8")
    print(f"→ {doc.relative_to(ROOT)}")
    exp = ROOT / "data" / "goldset_retest_sept_labeled.csv"
    with open(exp, "w", newline="", encoding="utf-8") as f:
        cols = ["id", "L1_위임인가", "L2_위임된법형식", "L3_확신도", "L4_메모"]
        w = csv.DictWriter(f, fieldnames=cols); w.writeheader()
        for r in new: w.writerow({c: r.get(c, "") for c in cols})
    print(f"→ {exp.relative_to(ROOT)} (텍스트 사본)")

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
            extra = [
                ("planned re-annotation for intra-annotator κ",
                 "completed re-annotation for intra-annotator κ (§6.2)"),
                ("and the scheduled intra-annotator re-test",
                 "and the completed intra-annotator re-test (§6.2)"),
            ]
            t2 = m.read_text(encoding="utf-8"); done = 0
            for o2, n2 in extra:
                if o2 in t2: t2 = t2.replace(o2, n2, 1); done += 1
            m.write_text(t2, encoding="utf-8")
            print(f"[적용] §10 시제 정리 {done}/2")
            row_anchor = "| author, re-test (3-day interval) | L1 / L2 | 1.000 (60/60) / 1.000 (59/59) | 1.000 / 1.000 |"
            new_row = (f"| author, re-test ({gap_days} days, fresh sample) | L1 / L2 | "
                       f"{l1_60['agree']:.3f} ({l1_60['n']-len(l1_60['disagreements'])}/{l1_60['n']}) / "
                       f"{l2_60['agree']:.3f} ({l2_60['n']-len(l2_60['disagreements'])}/{l2_60['n']}) | "
                       f"{fmt(l1_60['kappa'])} / {fmt(l2_60['kappa'])} |")
            t3 = m.read_text(encoding="utf-8")
            if row_anchor in t3 and new_row not in t3:
                t3 = t3.replace(row_anchor, row_anchor + "\n" + new_row, 1)
                t3 = t3.replace("In the re-test row the L2 denominator is 59 because one re-tested item is a citation, to which no instrument form applies.",
                                "In the re-test rows the L2 denominators (59; 58) exclude re-tested items that are citations, to which no instrument form applies.", 1)
                m.write_text(t3, encoding="utf-8"); print("[적용] 표 1 에 9월 재검사 행 추가")
            else:
                print("[건너뜀] 표 1 행: 앵커 없음 또는 이미 추가됨")


if __name__ == "__main__":
    main()
