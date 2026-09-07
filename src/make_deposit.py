#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_deposit.py — Zenodo 아카이브 깃(deposit)을 만든다. 저장소에 넣지 않는 큰 파일들:
   data/raw/ (원시 API 응답), data/panel/req_*.jsonl (패널 요청 페이로드),
   data/{admrules,laws,edges}.jsonl (통합 코퍼스).
`.scrub_terms` 의 oc/osf/name/deny 문자열을 make_public.py 와 같은 규칙으로 치환하고,
치환 후 전수 검사해 하나라도 남으면 exit 1. 산출: deposit/orphan-rules_archive_<날짜>.zip
"""
import datetime, io, re, sys, time, zipfile
BUDGET = float(sys.argv[1]) if len(sys.argv) > 1 else 150.0   # 초 — 시간 제한 환경용, 재실행하면 이어서 한다
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
terms = []
for raw in (ROOT/".scrub_terms").read_text(encoding="utf-8").splitlines():
    line = raw.split("#",1)[0].strip()
    if not line: continue
    parts=[x.strip() for x in line.split("|")]; parts += [""]*(4-len(parts)); terms.append(parts[:4])
def scrub(t):
    for role,lit,repl,_ in terms:
        if role in ("oc","osf","name") and lit: t = t.replace(lit, repl or "[withheld]")
    return t
# 허용 목록 — 금지 문자열과 같은 글자이지만 저자가 아닌 공적 기록. 원문을 보존한다.
# (문자열 자체는 여기에 적지 않는다 — 이 스크립트도 공개 번들에 들어간다)
ALLOW = {
    "data/raw/law_002582.json": "2013년 공포문 서명란(당시 국무총리 성명) — 금지 목록의 한 항목과 글자가 같은 공적 인물. 법령 원문 보존.",
}
def bad(t):
    return [lit for role,lit,_,_ in terms if lit and lit.lower() in t.lower()]
files = sorted(list((ROOT/"data/raw").rglob("*"))) + sorted((ROOT/"data/panel").glob("req_*.jsonl")) + \
        [ROOT/"data"/x for x in ("admrules.jsonl","laws.jsonl","edges.jsonl")]
files = [f for f in files if f.is_file() and f.name != ".DS_Store"]
out = ROOT/"deposit"/"orphan-rules_archive.zip"
n=0; hits=[]; t0=time.time()
done = set()
if out.exists():
    with zipfile.ZipFile(out) as z0: done = set(z0.namelist())
with zipfile.ZipFile(out, "a", zipfile.ZIP_DEFLATED, compresslevel=1) as z:
    for f in files:
        rel = str(f.relative_to(ROOT))
        if rel in done: continue
        if time.time() - t0 > BUDGET:
            print(f"  [시간 예산 소진] {n}개 추가, 남은 {len(files)-len(done)-n}개 — 다시 실행하면 이어서 한다"); sys.exit(2)
        b = f.read_bytes()
        try:
            t = b.decode("utf-8"); t2 = scrub(t); rem = bad(t2)
            if rem and rel in ALLOW: print(f"  ⚠ 허용 {rel}: {ALLOW[rel]}")
            elif rem: hits.append((rel, rem))
            z.writestr(rel, t2)
        except UnicodeDecodeError:
            z.writestr(rel, b)
        n+=1
    if "README_ARCHIVE.txt" not in done: z.writestr("README_ARCHIVE.txt",
        "Orphan Rules — archival deposit (raw API responses, panel request payloads, consolidated corpus).\n"
        "Companion to the GitHub repository; MST-pinned snapshot of 2026-08-15. API account identifier masked as YOUR_OC.\n")
# 전수 재검사 (이전 실행에서 넣은 항목 포함)
with zipfile.ZipFile(out) as z:
    for nm in z.namelist():
        try: t = z.read(nm).decode("utf-8")
        except UnicodeDecodeError: continue
        rem = bad(t)
        if rem and nm not in ALLOW and (nm, rem) not in hits: hits.append((nm, rem))
print(f"이번 {n}개 · 총 {len(done)+n+1}개 → {out.name}  {out.stat().st_size/1048576:.0f} MB")
if hits:
    print("✘ 식별 문자열 잔존:", hits[:5]); sys.exit(1)
print("✔ 식별 문자열 0건")
