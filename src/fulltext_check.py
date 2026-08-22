#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fulltext_check.py — 조작 점검: 조각 입력이 패널 과대판정의 원인인가?

배경 (원고 §6.4). DSL 보정항 −5.0pp를 만드는 보정표본 불일치 10건이 전부
'절단된 조문 조각'이고, 전수에서도 패널 비위임 판정 721건의 88.2%가 조각이다.
이는 상관관계다. 본 점검은 같은 레코드에 **전체 조문 본문**을 주고 판정이
저자 라벨 쪽으로 뒤집히는지를 보는 개입 실험이다.

등록상 위치: OSF osf.io/[OSF registration; identifier withheld for double-blind review] "other planned analysis" (b) 검사별 오류 패턴
분석(탐색적). 주 추정량·보정표본·코드북은 건드리지 않는다.

절차
  1) build : edges ↔ lawbodies.jsonl 조인 → 조각 레코드에 전체 조문 부착
             표본 = 보정표본 불일치 전건 + 전수 조각·패널비위임 층 무작위 추출
  2) submit/fetch : 값싼 검사 1개(기본 T5 gpt-5-mini)로 조각본/전문본 각 1회
  3) report : 조각 → 전문 전환 시 판정 변화표 + 저자 라벨 방향 전환율

사용
  python src/fulltext_check.py build --n 200
  python src/fulltext_check.py submit          # $2 내외
  python src/fulltext_check.py fetch
  python src/fulltext_check.py report
"""
import argparse, csv, json, os, random, re, sys, time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA, PANEL, RAW = ROOT / "data", ROOT / "data" / "panel", ROOT / "data" / "raw" / "panel"
FT = PANEL / "fulltext"
sys.path.insert(0, str(ROOT / "src"))
from panel_annotate import (PANEL_SYSTEM, TESTS, _http, _oai_headers, _anth_headers,  # noqa
                            OAI_URL, ANTH_URL, _read_csv, _write_csv, OAI_MAX_COMPLETION,
                            OAI_REASONING_BY_MODEL, OAI_REASONING_DEFAULT,
                            ANTH_MAX_TOKENS, ANTH_NO_TEMPERATURE)
from llm_annotate import parse  # noqa

TEST = os.environ.get("FTCHECK_TEST", "T5")     # 값싼 검사 1개
FIN = re.compile(r"(다|것|음|함|호|목)\s*[.」』]?\s*$")
trunc = lambda s: not FIN.search((s or "").strip())


def _read_jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8")]


def build(args):
    FT.mkdir(parents=True, exist_ok=True)
    bodies = {b["법령ID"]: b for b in _read_jsonl(DATA / "lawbodies.jsonl")}
    pop = {r["id"]: r for r in _read_csv(PANEL / "panel_input.csv")}
    labels = {t: {r["id"]: r[f"{t}_L1"] for r in _read_csv(PANEL / f"labels_{t}_full.csv")}
              for t in TESTS}
    cmap = {r["gold_id"]: r["panel_id"] for r in _read_csv(PANEL / "calibration_map.csv")}
    gold = {r["id"]: r for r in _read_csv(DATA / "goldset_labeled_v2.csv")}
    err = lambda l: 0 if l == "위임" else 1
    maj = lambda pid: 1 if sum(err(labels[t][pid]) for t in TESTS) * 2 > len(TESTS) else 0

    def full_article(rec):
        """조번호만으로는 가지번호(제59조의11 등)를 구분할 수 없다.
        메타데이터의 상위조문제목으로 가지를 확정하고, 제목이 비거나 일치하지
        않으면 가지번호 없는 본조를 쓰되, 그래도 모호하면 빈 문자열(=표본 제외)."""
        b = bodies.get((rec.get("상위법령ID") or "").strip())
        if not b:
            return ""
        num = str(rec.get("상위조문번호") or "").strip().lstrip("0")
        cands = [a for a in b["조문"]
                 if str(a["조번호"]).strip().lstrip("0") == num]
        if not cands:
            return ""
        if len(cands) == 1:
            return cands[0]["조내용"]
        title = (rec.get("상위조문제목") or "").strip()
        exact = [a for a in cands if (a.get("조제목") or "").strip() == title]
        if len(exact) == 1:
            return exact[0]["조내용"]
        base = [a for a in cands if not (a.get("가지번호") or "").strip()]
        if title == "" and len(base) == 1:
            return base[0]["조내용"]
        return ""          # 모호 → 표본에서 제외 (오조문 투입 금지)

    rows, seen = [], set()
    # (a) 보정표본 인간-대리 불일치 전건 (보정항의 원천)
    for gid, g in gold.items():
        gl = (g.get("L1_위임인가") or "").strip()
        if not gl:
            continue
        pid = cmap[gid]
        if err(gl) != maj(pid):
            rows.append({"id": pid, "gold_id": gid, "층": "보정불일치",
                         "인간L1": gl, "조각": pop[pid]["조문문장"],
                         "전문": full_article(pop[pid])})
            seen.add(pid)
    # (b) 전수 조각 × 패널 비위임 층 무작위
    pool = [p for p, r in pop.items()
            if p not in seen and trunc(r["조문문장"]) and maj(p) == 1]
    rng = random.Random(20260820)
    for pid in rng.sample(pool, min(args.n - len(rows), len(pool))):
        rows.append({"id": pid, "gold_id": "", "층": "조각·패널비위임",
                     "인간L1": "", "조각": pop[pid]["조문문장"],
                     "전문": full_article(pop[pid])})
    got = sum(1 for r in rows if r["전문"])
    _write_csv(FT / "ftcheck_input.csv", rows)
    print(f"표본 {len(rows)}건 (보정불일치 {sum(1 for r in rows if r['층']=='보정불일치')}), "
          f"전체 조문 확보 {got} ({got/len(rows):.1%})")
    if got / len(rows) < 0.8:
        print("※ 조문 매칭률이 낮습니다 — 조번호 표기(가지번호 등) 확인 필요")

    # 요청 파일: 같은 레코드를 조각본/전문본 두 조건으로
    prov, model = TESTS[TEST]
    reqs = []
    for r in rows:
        if not r["전문"]:
            continue
        for cond, txt in (("frag", r["조각"]), ("full", r["전문"])):
            user = (f"상위법령: {pop[r['id']]['상위법령명']}\n"
                    f"조문: 제{pop[r['id']]['상위조문번호']}조"
                    f"({pop[r['id']]['상위조문제목']})\n"
                    f"문장: {txt}\n표지어구: {pop[r['id']]['위임표지어구']}")
            cid = f"{TEST}-{r['id']}-{cond}"
            if prov == "anthropic":
                params = {"model": model, "max_tokens": ANTH_MAX_TOKENS,
                          "system": [{"type": "text", "text": PANEL_SYSTEM,
                                      "cache_control": {"type": "ephemeral"}}],
                          "messages": [{"role": "user", "content": user}]}
                if model not in ANTH_NO_TEMPERATURE:
                    params["temperature"] = 0
                reqs.append({"custom_id": cid, "params": params})
            else:
                reqs.append({"custom_id": cid, "method": "POST",
                             "url": "/v1/chat/completions",
                             "body": {"model": model,
                                      "messages": [{"role": "system", "content": PANEL_SYSTEM},
                                                   {"role": "user", "content": user}],
                                      "max_completion_tokens": OAI_MAX_COMPLETION,
                                      "reasoning_effort": OAI_REASONING_BY_MODEL.get(
                                          model, OAI_REASONING_DEFAULT)}})
    with open(FT / "ftcheck_req.jsonl", "w", encoding="utf-8") as f:
        for q in reqs:
            f.write(json.dumps(q, ensure_ascii=False) + "\n")
    print(f"요청 {len(reqs)}건 (검사 {TEST}={model}, 조각/전문 각 1회) → ftcheck_req.jsonl")


def submit(args):
    prov, model = TESTS[TEST]
    path = FT / "ftcheck_req.jsonl"
    if prov == "anthropic":
        reqs = [json.loads(l) for l in open(path, encoding="utf-8")]
        out = json.loads(_http(f"{ANTH_URL}/messages/batches", "POST", _anth_headers(),
                               {"requests": reqs}))
    else:
        b = "----ftboundary"
        body = (f"--{b}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nbatch\r\n"
                f"--{b}\r\nContent-Disposition: form-data; name=\"file\"; "
                f"filename=\"ft.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n"
                ).encode() + path.read_bytes() + f"\r\n--{b}--\r\n".encode()
        h = _oai_headers(); h["Content-Type"] = f"multipart/form-data; boundary={b}"
        up = json.loads(_http(f"{OAI_URL}/files", "POST", h, body))
        out = json.loads(_http(f"{OAI_URL}/batches", "POST", _oai_headers(),
                               {"input_file_id": up["id"],
                                "endpoint": "/v1/chat/completions",
                                "completion_window": "24h"}))
    (FT / "state.json").write_text(json.dumps(
        {"provider": prov, "model": model, "batch_id": out["id"]}, ensure_ascii=False))
    print(f"제출 완료 batch_id={out['id']}")


def fetch(args):
    st = json.loads((FT / "state.json").read_text())
    if st["provider"] == "anthropic":
        b = json.loads(_http(f"{ANTH_URL}/messages/batches/{st['batch_id']}",
                             headers=_anth_headers()))
        if b["processing_status"] != "ended":
            sys.exit(f"아직 {b['processing_status']}")
        blob = _http(b["results_url"], headers=_anth_headers())
    else:
        b = json.loads(_http(f"{OAI_URL}/batches/{st['batch_id']}", headers=_oai_headers()))
        if b["status"] != "completed":
            sys.exit(f"아직 {b['status']}")
        blob = _http(f"{OAI_URL}/files/{b['output_file_id']}/content", headers=_oai_headers())
    (FT / "ftcheck_raw.jsonl").write_bytes(blob)
    print(f"원시 {len(blob)//1024}KB → {FT/'ftcheck_raw.jsonl'}")
    report(args)


def report(args):
    res = {}
    for line in open(FT / "ftcheck_raw.jsonl", encoding="utf-8"):
        rec = json.loads(line)
        cid = rec.get("custom_id", "")
        _, rid, cond = cid.split("-", 2)
        text = ""
        if "result" in rec:
            r = rec["result"]
            if r.get("type") == "succeeded":
                text = "".join(x.get("text", "") for x in r["message"].get("content", [])
                               if x.get("type") == "text")
        else:
            rp = rec.get("response", {})
            if rp.get("status_code") == 200:
                ch = rp["body"].get("choices", [])
                text = ch[0]["message"].get("content", "") if ch else ""
        p = parse(text) or {"L1": "판단불가", "L2": "해당없음"}
        res.setdefault(rid, {})[cond] = p["L1"]

    rows = {r["id"]: r for r in _read_csv(FT / "ftcheck_input.csv")}
    tab = Counter()
    flip_to_human = flip_n = 0
    detail = []
    for rid, d in res.items():
        if "frag" not in d or "full" not in d:
            continue
        tab[(d["frag"], d["full"])] += 1
        r = rows.get(rid, {})
        if r.get("층") == "보정불일치" and r.get("인간L1"):
            flip_n += 1
            flip_to_human += (d["full"] == r["인간L1"])
        detail.append({"id": rid, "층": r.get("층", ""), "인간L1": r.get("인간L1", ""),
                       "조각판정": d["frag"], "전문판정": d["full"],
                       "조각": (r.get("조각") or "")[:60]})
    _write_csv(FT / "ftcheck_result.csv", detail)
    n = sum(tab.values())
    print(f"\n[조작 점검 — 검사 {TEST}, n={n}]")
    print("조각 판정 → 전문 판정 전이표")
    for (a, b), c in sorted(tab.items(), key=lambda x: -x[1]):
        print(f"  {a:5s} → {b:5s} : {c:4d} ({c/n:.1%})")
    same = sum(c for (a, b), c in tab.items() if a == b)
    to_del = sum(c for (a, b), c in tab.items() if a != "위임" and b == "위임")
    print(f"판정 유지 {same} ({same/n:.1%}) / 비위임·판단불가 → 위임 전환 {to_del} ({to_del/n:.1%})")
    if flip_n:
        print(f"보정불일치 층({flip_n}건): 전체 조문 제공 시 저자 라벨과 일치 "
              f"{flip_to_human} ({flip_to_human/flip_n:.1%})")
    print(f"→ {FT/'ftcheck_result.csv'}")


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build"); b.add_argument("--n", type=int, default=200)
    b.set_defaults(func=build)
    sub.add_parser("submit").set_defaults(func=submit)
    sub.add_parser("fetch").set_defaults(func=fetch)
    sub.add_parser("report").set_defaults(func=report)
    a = ap.parse_args(); a.func(a)


if __name__ == "__main__":
    main()
