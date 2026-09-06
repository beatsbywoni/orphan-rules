#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""triage_panel.py — §7.2 트리아지(대외구속지향/내부관리)의 기계 패널 재라벨.

게이트 점검 P1-1(A안): 헤드라인 61건(23.7%)을 만든 138건 판정은 저자 단독이었다.
동결 루브릭 아래 두 벤더 모델이 재라벨해 저자 판정과의 일치율·κ 를 산출한다.
**등록 외 사후 분석**이며 산출 문서에 그렇게 표기된다.

사용 (맥 터미널, 프로젝트 루트):
    export ANTHROPIC_API_KEY=...   # 터미널에 직접. 파일에 저장하지 말 것
    export OPENAI_API_KEY=...
    sh run_triage_panel.sh

동작
  1. `docs/triage_rubric_T1_v1.md` 를 읽어 SHA-256 을 찍는다(동결 증빙).
  2. `data/findings_D1_triage_v3.csv` 의 판정 138건(대외구속지향 61 + 내부관리 77)에
     `data/admrules.jsonl` 의 규칙 본문을 붙인다.
  3. claude-sonnet-5 · gpt-5-mini × 3회 반복, temperature 0(허용 시), strict JSON,
     1회 재시도 후 undecidable. 산출: data/triage_panel/labels_<model>_r<k>.csv
  4. 자기일관성, 모델별 다수결 vs 저자 κ(이진), 불일치 전건 목록 →
     docs/34_triage_panel_result.md + 원고 반영용 문장 출력.

비용: 138 × 2모델 × 3회 = 828콜, 본문 ≤6,000자 — 몇 달러 수준.
중단·재실행 안전: 이미 있는 산출 파일은 건너뛴다.
"""
import csv, hashlib, json, os, re, sys, time, urllib.error, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUBRIC = ROOT / "docs/triage_rubric_T1_v1.md"
TRIAGE = ROOT / "data/findings_D1_triage_v3.csv"
RULES  = ROOT / "data/admrules.jsonl"
OUTDIR = ROOT / "data/triage_panel"
DOC    = ROOT / "docs/34_triage_panel_result.md"

MODELS = [
    ("anthropic", "claude-sonnet-5"),
    ("openai",    "gpt-5-mini"),
]
REPS, MAXCHARS, TIMEOUT = 3, 6000, 120

LBL = {"대외구속지향": "externally-directed", "내부관리": "internal"}


def load_items():
    bodies = {}
    for line in open(RULES, encoding="utf-8"):
        r = json.loads(line)
        t = r.get("_조문텍스트") or ""
        if not t.strip():
            t = json.dumps(r.get("_본문", ""), ensure_ascii=False)
        bodies[r["행정규칙일련번호"]] = re.sub(r"<[^>]+>", " ", t)
    items = []
    for r in csv.DictReader(open(TRIAGE, encoding="utf-8-sig")):
        a = r["T1_규범성격"].strip()
        if a not in LBL:            # 타부처위임 7 + 본문없음 4 제외 → 138
            continue
        body = bodies.get(r["행정규칙일련번호"], "")[:MAXCHARS]
        items.append({"id": r["id"], "serial": r["행정규칙일련번호"],
                      "name": r["행정규칙명"], "kind": r["종류"],
                      "author": LBL[a], "excerpt": r.get("제1조발췌", "")[:1500],
                      "body": body})
    assert len(items) == 138, f"판정 대상 {len(items)} ≠ 138"
    return items


def call(provider, model, system, user):
    if provider == "anthropic":
        key = os.environ["ANTHROPIC_API_KEY"]
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps({"model": model, "max_tokens": 300,
                             "system": system,
                             "messages": [{"role": "user", "content": user}]}).encode(),
            headers={"x-api-key": key, "anthropic-version": "2023-06-01",
                     "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=TIMEOUT) as f:
            blocks = json.load(f).get("content", [])
            # 첫 블록이 text 가 아닐 수 있다(사고·거부 블록). text 블록만 이어 붙인다.
            return "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    key = os.environ["OPENAI_API_KEY"]
    req = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        # 추론 모델은 숨은 추론에 완료 토큰을 먼저 쓴다 — 8월 패널과 동일하게
        # reasoning_effort=minimal, 예산 1000 (deviation_log D-2026-08-18-1)
        data=json.dumps({"model": model, "max_completion_tokens": 1000,
                         "reasoning_effort": "minimal",
                         "messages": [{"role": "system", "content": system},
                                      {"role": "user", "content": user}]}).encode(),
        headers={"Authorization": f"Bearer {key}", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as f:
        return (json.load(f).get("choices") or [{}])[0].get("message", {}).get("content") or ""


def parse(txt):
    m = re.search(r'\{[^{}]*"label"[^{}]*\}', txt, re.S)
    if not m:
        return None, None
    try:
        o = json.loads(m.group(0))
        lab = str(o.get("label", "")).strip().lower()
        if lab in ("externally-directed", "internal", "undecidable"):
            return lab, str(o.get("reason", ""))[:400]
    except json.JSONDecodeError:
        pass
    return None, None


def run_model(provider, model, items, system):
    for rep in range(1, REPS + 1):
        out = OUTDIR / f"labels_{model}_r{rep}.csv"
        if out.exists():
            print(f"  [건너뜀] {out.name} 존재"); continue
        rows = []; fails = 0
        for i, it in enumerate(items, 1):
            user = (f"행정규칙명: {it['name']} ({it['kind']})\n"
                    f"제1조 발췌: {it['excerpt']}\n\n규칙 본문:\n{it['body']}")
            lab = reason = None
            for attempt in (1, 2):
                try:
                    raw = call(provider, model, system, user)
                    lab, reason = parse(raw)
                    if not lab:
                        print(f"    {it['id']} 시도{attempt}: JSON 없음 — {raw[:160]!r}")
                except urllib.error.HTTPError as e:
                    body = e.read().decode("utf-8", "ignore")[:300]
                    print(f"    {it['id']} 시도{attempt}: HTTP {e.code} — {body}")
                    time.sleep(8)
                except Exception as e:            # 네트워크·요율 — 잠시 쉬고 재시도
                    print(f"    {it['id']} 시도{attempt}: {type(e).__name__}: {e}"); time.sleep(8)
                if lab: break
            fails = fails + 1 if not lab else 0
            if not lab and i <= 3 and fails >= 3:
                sys.exit(f"  [중단] {model}: 첫 3건 연속 실패 — 위 오류 본문을 확인할 것 "
                         f"(모델명·키·파라미터). 산출 파일은 만들지 않았다.")
            rows.append({"id": it["id"], "label": lab or "undecidable",
                         "reason": reason or "", "retried": attempt > 1})
            if i % 20 == 0: print(f"    {model} r{rep}: {i}/138")
            time.sleep(0.3)
        with open(out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=["id", "label", "reason", "retried"])
            w.writeheader(); w.writerows(rows)
        print(f"  [완료] {out.name}")


def kappa(pairs):
    """이진 Cohen κ. pairs = [(a,b)], 라벨 externally-directed/internal."""
    n = len(pairs); po = sum(a == b for a, b in pairs) / n
    pa = sum(a == "externally-directed" for a, _ in pairs) / n
    pb = sum(b == "externally-directed" for _, b in pairs) / n
    pe = pa * pb + (1 - pa) * (1 - pb)
    return po, (po - pe) / (1 - pe) if pe < 1 else float("nan")


def analyse(items):
    author = {it["id"]: it["author"] for it in items}
    name   = {it["id"]: it["name"] for it in items}
    lines  = ["# 트리아지 기계 패널 결과 — 등록 외 사후 분석\n",
              f"루브릭 SHA-256: `{hashlib.sha256(RUBRIC.read_bytes()).hexdigest()}`\n"]
    sent   = []
    for _, model in MODELS:
        runs = []
        for rep in range(1, REPS + 1):
            f = OUTDIR / f"labels_{model}_r{rep}.csv"
            if f.exists():
                runs.append({r["id"]: r["label"] for r in csv.DictReader(open(f, encoding="utf-8"))})
        if len(runs) < REPS:
            print(f"  [미완] {model}: {len(runs)}/{REPS}회 — 분석 보류"); return
        ids = list(author)
        cons = sum(len({r[i] for r in runs}) == 1 for i in ids) / len(ids)
        # 다수결 (동률·undecidable 다수 → undecidable)
        maj = {}
        for i in ids:
            v = [r[i] for r in runs]
            maj[i] = max(set(v), key=v.count) if v.count(max(set(v), key=v.count)) >= 2 else "undecidable"
        dec = [i for i in ids if maj[i] != "undecidable"]
        po, k = kappa([(author[i], maj[i]) for i in dec])
        dis = [i for i in dec if maj[i] != author[i]]
        lines += [f"\n## {model}\n",
                  f"- 자기일관성(3회 전일치): {cons:.3f}",
                  f"- 다수결 판정 {len(dec)}/138 (undecidable {138-len(dec)})",
                  f"- 저자와 일치 {po:.3f} · Cohen κ {k:.3f}",
                  f"- 불일치 {len(dis)}건:"]
        for i in dis:
            lines.append(f"    - {i} {name[i][:40]} — 저자 {author[i]} / 패널 {maj[i]}")
        sent.append(f"{model}: agreement {po:.3f}, κ {k:.3f}, n = {len(dec)}")
    lines += ["\n## 원고 반영(§7.2·§10) 문장 재료\n"] + [f"- {x}" for x in sent] + [
        "\n> 이 분석은 사전등록 밖의 사후 분석이며, 원고에 그렇게 표기한다.",
        "> 불일치 전건은 저자 판정 메모와 함께 공개한다 (Braun 2024 권고)."]
    DOC.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\n[산출] {DOC}")
    for x in sent: print("   ", x)


def main():
    OUTDIR.mkdir(exist_ok=True)
    system = RUBRIC.read_text(encoding="utf-8")
    print(f"[루브릭 동결] SHA-256 {hashlib.sha256(RUBRIC.read_bytes()).hexdigest()[:16]}…")
    items = load_items()
    print(f"[대상] {len(items)}건 (대외구속지향 {sum(i['author']=='externally-directed' for i in items)} / "
          f"내부관리 {sum(i['author']=='internal' for i in items)})")
    if "--analyse-only" not in sys.argv:
        for provider, model in MODELS:
            envk = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
            if envk not in os.environ:
                print(f"  [건너뜀] {model}: {envk} 없음"); continue
            run_model(provider, model, items, system)
    analyse(items)


if __name__ == "__main__":
    main()
