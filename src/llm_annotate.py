#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm_annotate.py — LLM을 '제2 어노테이터'로 사용 (트랙 B)

중요한 위치 설정
---------------
LLM 라벨은 **gold가 아닙니다.** 저자 라벨과 독립적인 제2 어노테이터의 산출물이며,
저자-LLM 간 κ를 보고하는 것이 목적입니다.
근거: Cevallos-Salas et al. (2025), AI&Law — LLM을 인간 어노테이터 분포 안에
      위치시키는 equivalence-within-human-variance 검증 프레임.
경고: Egami et al. (NeurIPS 2023) — 정확도 80~90%의 대리라벨도 보정 없이 쓰면
      실질적 편향과 무효한 신뢰구간을 낳습니다.

★ 저자가 라벨을 끝내기 전에는 이 스크립트의 출력을 열지 마십시오.
  보는 순간 독립성이 깨지고 κ가 무의미해집니다.

Schepers et al. (2025, AI&Law)은 GPT-4o의 반복 실행 간 일치도를 보고하지
않았습니다. 이 스크립트는 --repeats 로 반복 호출해 self-consistency를 산출합니다.
그 수치를 보고하면 해당 게재작보다 엄격한 보고가 됩니다.

사용
----
  export LLM_API_KEY=...
  export LLM_BASE_URL=https://api.openai.com/v1     # OpenAI 호환 엔드포인트
  export LLM_MODEL=gpt-4o

  python src/llm_annotate.py \
      --in data/goldset_to_label.csv \
      --out data/goldset_llm.csv \
      --repeats 3

출력 열
  LLM_L1 (위임/인용/판단불가)  LLM_L2 (법형식)  LLM_확신도
  LLM_L1_일관성  LLM_L2_일관성  (반복 간 다수결 비율)
  LLM_원응답_1..R
"""

import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter

import requests

API_KEY = os.environ.get("LLM_API_KEY", "")
BASE_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o")

# 코드북 v1.1 (2026-08-15): '교육규칙'을 조례와 구분하는 독립 값으로 추가.
# 복수 형식이 병기된 문장은 '|'로 연결 (예: "대통령령|조례"). 저자 라벨의
# L2+L2_병존형식 집합과 교집합 유무로 일치를 판정한다 (agreement 단계).
FORMS = ["대통령령", "부령", "고시", "훈령", "예규", "조례", "교육규칙",
         "미특정", "해당없음"]

# docs/04_annotation_protocol.md 1절과 동일한 정의를 사용해야 합니다.
# 가이드라인이 바뀌면 이 프롬프트도 함께 바꾸십시오 (재현성).
SYSTEM = """당신은 한국 법령 조문을 분류하는 어노테이터입니다.
주어진 조문 문장 하나에 대해 두 가지만 판정하고, 지정된 JSON으로만 답하십시오.

[L1] 이 문장이 하위 규범에 규율권한을 넘기는가?
  "위임"      = 하위 규범이 정할 사항의 범위를 지시하며 규율권한을 넘긴다.
  "인용"      = 다른 법령을 가리키기만 한다. 정의 원용, 절차 준용,
                "「○○법」에 따른" 형태.
  "판단불가"  = 문장이 잘렸거나 맥락 없이 판정할 수 없다.

  경계 규칙:
  - 준용 규정("제○조를 준용한다")은 → 인용
  - "대통령령으로 정하는 ○○" 처럼 요건 일부만 맡기는 부분 위임 → 위임
  - 규범 제정이 아니라 개별 처분 권한만 부여하는 경우 → 인용
  - 포괄위임이 의심되어도 일단 "위임". 위헌 여부는 판단하지 않는다.

[L2] 문장이 명시적으로 지정한 법형식.
  실제로 무엇이 제정되었는지가 아니라, 문언이 무엇을 요구하는지로 판정한다.
  대통령령 / 부령 / 고시 / 훈령 / 예규 / 조례 / 교육규칙 / 미특정 / 해당없음
  - "조례"와 "교육규칙"(교육감 제정)은 구분한다.
  - 복수의 법형식이 병기된 경우(예: "대통령령 또는 조례로 정하는 바에 따라",
    "대통령령으로 정하는 범위에서 조례로 정한다")에는 병기된 형식을 전부
    "|"로 연결해 나열한다 (예: "대통령령|조례").
  - "미특정": "장관이 정하는", "교육감이 지정하는" 등 형식을 지정하지 않은 경우
  - "해당없음": L1이 "인용"인 경우

출력 형식 (다른 텍스트 없이 이 JSON만):
{"L1": "...", "L2": "...", "confidence": 1~5, "reason": "한 문장"}"""


def build_user(row):
    return (
        f"상위법령: {row.get('상위법령명','')}\n"
        f"조문: 제{row.get('상위조문번호','')}조"
        f"({row.get('상위조문제목','')})\n"
        f"문장: {row.get('조문문장','')}\n"
        f"표지어구: {row.get('위임표지어구','')}"
    )


def call(messages, temperature=0.0, timeout=60):
    if not API_KEY:
        sys.exit("LLM_API_KEY 환경변수가 없습니다.")
    r = requests.post(
        f"{BASE_URL}/chat/completions",
        headers={"Authorization": f"Bearer {API_KEY}",
                 "Content-Type": "application/json"},
        json={"model": MODEL, "messages": messages,
              "temperature": temperature, "max_tokens": 300},
        timeout=timeout)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]


def parse(text):
    m = re.search(r"\{.*\}", text or "", re.S)
    if not m:
        return None
    try:
        d = json.loads(m.group(0))
    except json.JSONDecodeError:
        return None
    l1 = str(d.get("L1", "")).strip()
    l2 = str(d.get("L2", "")).strip()
    if l1 not in ("위임", "인용", "판단불가"):
        l1 = "판단불가"
    if "|" in l2:      # 복수 형식 나열 허용 (코드북 v1.1)
        parts = [p.strip() for p in l2.split("|") if p.strip() in FORMS]
        l2 = "|".join(dict.fromkeys(parts)) or "해당없음"
    elif l2 not in FORMS:
        l2 = "해당없음"
    return {"L1": l1, "L2": l2,
            "conf": d.get("confidence", ""), "reason": d.get("reason", "")}


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--in", dest="inp", default="data/goldset_to_label.csv")
    ap.add_argument("--out", dest="out", default="data/goldset_llm.csv")
    ap.add_argument("--repeats", type=int, default=3,
                    help="반복 호출 횟수. self-consistency 산출용")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--sleep", type=float, default=0.3)
    ap.add_argument("--limit", type=int, default=None)
    a = ap.parse_args()

    with open(a.inp, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if a.limit:
        rows = rows[:a.limit]
    print(f"{len(rows)}건 × {a.repeats}회 = {len(rows)*a.repeats} 호출")
    print(f"모델 {MODEL}, temperature {a.temperature}\n")

    out = []
    for i, row in enumerate(rows, 1):
        msgs = [{"role": "system", "content": SYSTEM},
                {"role": "user", "content": build_user(row)}]
        picks, raws = [], []
        for _ in range(a.repeats):
            try:
                txt = call(msgs, a.temperature)
            except requests.RequestException as e:
                sys.stderr.write(f"[warn] {row.get('id')}: {e}\n")
                txt = ""
            raws.append(txt)
            p = parse(txt)
            if p:
                picks.append(p)
            time.sleep(a.sleep)

        if picks:
            c1 = Counter(p["L1"] for p in picks)
            c2 = Counter(p["L2"] for p in picks)
            l1, n1 = c1.most_common(1)[0]
            l2, n2 = c2.most_common(1)[0]
            conf = next((p["conf"] for p in picks if p["L1"] == l1), "")
            reason = next((p["reason"] for p in picks if p["L1"] == l1), "")
        else:
            l1, l2, n1, n2, conf, reason = "판단불가", "해당없음", 0, 0, "", ""

        rec = {"id": row.get("id"),
               "조문문장": row.get("조문문장"),
               "LLM_L1": l1, "LLM_L2": l2, "LLM_확신도": conf,
               "LLM_L1_일관성": round(n1 / a.repeats, 3),
               "LLM_L2_일관성": round(n2 / a.repeats, 3),
               "LLM_근거": reason}
        for r_i, t in enumerate(raws, 1):
            rec[f"LLM_원응답_{r_i}"] = t
        out.append(rec)
        if i % 20 == 0:
            print(f"  {i}/{len(rows)}")

    keys = list(out[0].keys()) if out else []
    with open(a.out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(out)

    sc1 = sum(r["LLM_L1_일관성"] for r in out) / len(out) if out else 0
    sc2 = sum(r["LLM_L2_일관성"] for r in out) / len(out) if out else 0
    print(f"\n저장: {a.out} ({len(out)}행)")
    print(f"self-consistency  L1 {sc1:.3f} / L2 {sc2:.3f}  "
          f"(temperature={a.temperature}, repeats={a.repeats})")
    print("\n※ 저자 라벨을 끝내기 전에는 이 파일을 열지 마십시오.")
    print("※ 논문에는 이 self-consistency 수치를 반드시 보고하십시오 —")
    print("   Schepers et al.(2025, AI&Law)은 이 수치를 보고하지 않았습니다.")
    print(f"\n다음: python src/agreement.py kappa \\")
    print(f"        --a {a.inp} --a-col L1_위임인가 \\")
    print(f"        --b {a.out} --b-col LLM_L1")


if __name__ == "__main__":
    main()
