#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
panel_annotate.py — Phase 1: 전수(N=7,558) K=7 패널 주석 (OSF 등록 osf.io/[OSF registration; identifier withheld for double-blind review] 이행)

사전등록(2026-08-18, [OSF registration; identifier withheld for double-blind review])이 이 스크립트의 사양서입니다.
등록과 다른 모든 변경은 docs/deviation_log.md 에 기록해야 합니다.

패널 구성 (등록 §2)
  T1 anthropic claude-haiku-4-5-20251001
  T2 anthropic claude-sonnet-5
  T3 anthropic claude-opus-5
  T4 openai    gpt-5-nano
  T5 openai    gpt-5-mini
  T6 openai    gpt-5.4
  T7 rule      결정론적 규칙 추출기 (이 파일 안, rulebase)

프롬프트 = llm_annotate.SYSTEM (코드북 v1.1 verbatim) + 고정 few-shot 4개.
첫 호출 전에 SHA-256 해시가 data/panel/manifest.json 에 기록됩니다.

순서 (각 단계는 한 줄 sh로 래핑되어 있음)
  1) build-input   edges.jsonl → data/panel/panel_input.csv (P0001..P7558)
                   + 파일럿 입력 = data/goldset_to_label.csv (G####, 200건)
  2) prepare       요청 JSONL 생성 + manifest(프롬프트 해시·파라미터) + 비용 추정
  3) submit --scope pilot   두 provider에 파일럿 배치 제출 (200건 × 6검사)
  4) status / fetch         폴링, 원시 응답 archive → data/raw/panel/
  5) pilot-check   검사별 파싱률 ≥99.5% + 비용 전망 → go/no-go
  6) submit --scope full    전수 배치 제출 (7,558건 × 6검사)
  7) fetch → data/panel/labels_T{k}_{scope}.csv
  8) rulebase      T7 라벨 (로컬, 결정론)

키는 터미널 환경변수로만: ANTHROPIC_API_KEY, OPENAI_API_KEY. 파일 저장 금지.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
PANEL = DATA / "panel"
RAW = DATA / "raw" / "panel"

sys.path.insert(0, str(ROOT / "src"))
from llm_annotate import SYSTEM, FORMS, parse, build_user  # noqa: E402  (코드북 v1.1 verbatim 재사용)

# ---------------------------------------------------------------- 고정 few-shot
# 등록 §2: "system prompt = codebook verbatim + 4 fixed few-shot examples".
# 예시는 코드북 v1.1의 경계 규칙 4개를 각 1회 시연한다. 수정 금지(해시 고정).
FEWSHOT = """
[고정 예시 4]
예시 1
문장: 학교의 설립 기준에 관하여 필요한 사항은 대통령령으로 정한다.
답: {"L1": "위임", "L2": "대통령령", "confidence": 5, "reason": "문말 종결형으로 대통령령에 규율권한을 넘긴다."}

예시 2
문장: 교육부령으로 정한 기준을 충족하는 기관은 지원 대상이 된다.
답: {"L1": "인용", "L2": "해당없음", "confidence": 5, "reason": "완료형 '정한'은 이미 존재하는 규범을 가리키는 인용이다."}

예시 3
문장: 수업료는 대통령령으로 정하는 범위에서 조례로 정한다.
답: {"L1": "위임", "L2": "대통령령|조례", "confidence": 4, "reason": "두 법형식이 병기된 위임으로 '|'로 연결한다."}

예시 4
문장: 제12조부터 제15조까지의 규정을 준용한다.
답: {"L1": "인용", "L2": "해당없음", "confidence": 5, "reason": "준용 규정은 인용이다."}
"""

PANEL_SYSTEM = SYSTEM + "\n" + FEWSHOT

TESTS = {
    "T1": ("anthropic", "claude-haiku-4-5-20251001"),
    "T2": ("anthropic", "claude-sonnet-5"),
    "T3": ("anthropic", "claude-opus-5"),
    "T4": ("openai", "gpt-5-nano"),
    "T5": ("openai", "gpt-5-mini"),
    "T6": ("openai", "gpt-5.4"),
    "T7": ("rule", None),
}
LLM_TESTS = [t for t, (p, _) in TESTS.items() if p != "rule"]

# 등록 파라미터. OpenAI gpt-5 계열은 chat completions에서 temperature 지정을
# 거부할 수 있어(추론 모델 제약) temperature를 생략하고 reasoning_effort=minimal,
# max_completion_tokens=1000을 쓴다 → 등록 대비 편차이므로 deviation_log에 기록.
# Anthropic 5세대(sonnet-5, opus-5)도 temperature를 거부함이 파일럿에서 실측됨
# ("`temperature` is deprecated for this model") → 해당 모델은 생략. haiku-4-5는 0 유지.
ANTH_NO_TEMPERATURE = {"claude-sonnet-5", "claude-opus-5"}
# 등록값 300은 5세대(sonnet-5·opus-5)에서 내부 추론 토큰이 출력 예산에 포함되어
# 잘림(stop_reason=max_tokens, T2 2건·T3 46건 실측) → 1000으로 상향, deviation_log 기록.
ANTH_MAX_TOKENS = 1000
OAI_MAX_COMPLETION = 1000
# gpt-5.4는 'minimal' 미지원(none/low/medium/high/xhigh) — 파일럿 실측. 최소 추론 = 'none'.
OAI_REASONING_BY_MODEL = {"gpt-5.4": "none"}
OAI_REASONING_DEFAULT = "minimal"

COST = {  # $/MTok (input, output); Batch 50% 할인은 별도 적용
    "claude-haiku-4-5-20251001": (1.0, 5.0),
    "claude-sonnet-5": (2.0, 10.0),
    "claude-opus-5": (5.0, 25.0),
    "gpt-5-nano": (0.05, 0.40),
    "gpt-5-mini": (0.25, 2.00),
    "gpt-5.4": (2.50, 15.00),
}
BATCH_DISCOUNT = 0.5
COST_CEILING_USD = 250.0  # 등록 §4

ANTH_URL = "https://api.anthropic.com/v1"
OAI_URL = "https://api.openai.com/v1"


def _http(url, method="GET", headers=None, data=None, timeout=180, fatal=True):
    req = urllib.request.Request(url, method=method, headers=headers or {})
    if data is not None:
        if isinstance(data, (dict, list)):
            data = json.dumps(data).encode()
            req.add_header("Content-Type", "application/json")
        req.data = data
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")[:2000]
        if fatal:
            sys.exit(f"HTTP {e.code} {url}\n{body}")
        raise RuntimeError(f"HTTP {e.code}: {body}")


def _anth_headers():
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        sys.exit("ANTHROPIC_API_KEY 환경변수가 없습니다 (터미널에서만 입력).")
    return {"x-api-key": key, "anthropic-version": "2023-06-01"}


def _oai_headers():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        sys.exit("OPENAI_API_KEY 환경변수가 없습니다 (터미널에서만 입력).")
    return {"Authorization": f"Bearer {key}"}


def _read_csv(path):
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def _write_csv(path, rows, keys=None):
    keys = keys or list(rows[0].keys())
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def _state():
    p = PANEL / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def _save_state(st):
    PANEL.mkdir(parents=True, exist_ok=True)
    (PANEL / "state.json").write_text(json.dumps(st, ensure_ascii=False, indent=2))


def _input_rows(scope):
    if scope == "pilot":
        return _read_csv(DATA / "goldset_to_label.csv")
    if scope == "cons":
        return _read_csv(PANEL / "consistency_input.csv")
    return _read_csv(PANEL / "panel_input.csv")


def _build_consistency_input():
    """500건 층화 서브샘플 (API_위임구분 비례, 시드 20260819) — 등록 §2."""
    import random
    rows = _read_csv(PANEL / "panel_input.csv")
    strata = {}
    for r in rows:
        strata.setdefault(r.get("API_위임구분", "?"), []).append(r)
    rng = random.Random(20260819)
    picked = []
    for key, rs in sorted(strata.items()):
        k = max(1, round(500 * len(rs) / len(rows)))
        picked.extend(rng.sample(rs, min(k, len(rs))))
    picked = picked[:500]
    _write_csv(PANEL / "consistency_input.csv", picked)
    return picked


# ---------------------------------------------------------------- build-input
def cmd_build_input(args):
    edges = []
    with open(DATA / "edges.jsonl", encoding="utf-8") as f:
        for line in f:
            edges.append(json.loads(line))
    out = []
    for i, e in enumerate(edges, 1):
        out.append({
            "id": f"P{i:05d}",
            "상위법령ID": e.get("상위법령ID"),
            "상위법령명": e.get("상위법령명"),
            "상위조문번호": e.get("상위조문번호"),
            "상위조문제목": e.get("상위조문제목"),
            "조문문장": e.get("라인텍스트"),
            "위임표지어구": e.get("링크텍스트"),
            "API_위임구분": e.get("위임구분"),
            "자동추출_위임형식": e.get("위임된형식"),
            "대상유형": e.get("대상유형"),
            "대상명": e.get("대상명"),
        })
    _write_csv(PANEL / "panel_input.csv", out)
    print(f"panel_input.csv {len(out)}행 (edges.jsonl 순서 그대로, P00001..)")
    print("파일럿 입력은 data/goldset_to_label.csv (G####, 200건)를 그대로 씁니다.")


# ---------------------------------------------------------------- prepare
def _requests_for(test, rows, repeats=1):
    provider, model = TESTS[test]
    for row in rows:
      for rep in range(1, repeats + 1):
        # Anthropic custom_id 규칙: ^[a-zA-Z0-9_-]{1,64}$ → 반복 구분자는 '_r'
        cid = f"{test}-{row['id']}" if repeats == 1 else f"{test}-{row['id']}_r{rep}"
        user = build_user(row)
        if provider == "anthropic":
            params = {
                "model": model,
                "max_tokens": ANTH_MAX_TOKENS,
                "system": [{"type": "text", "text": PANEL_SYSTEM,
                            "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": user}],
            }
            if model not in ANTH_NO_TEMPERATURE:
                params["temperature"] = 0
            yield {"custom_id": cid, "params": params}
        else:
            yield {
                "custom_id": cid,
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": model,
                    "messages": [{"role": "system", "content": PANEL_SYSTEM},
                                 {"role": "user", "content": user}],
                    "max_completion_tokens": OAI_MAX_COMPLETION,
                    "reasoning_effort": OAI_REASONING_BY_MODEL.get(
                        model, OAI_REASONING_DEFAULT),
                },
            }


def cmd_prepare(args):
    PANEL.mkdir(parents=True, exist_ok=True)
    prompt_hash = hashlib.sha256(PANEL_SYSTEM.encode()).hexdigest()
    manifest = {
        "registration": "[OSF registration; identifier withheld for double-blind review]",
        "prepared_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "system_prompt_sha256": prompt_hash,
        "system_prompt_chars": len(PANEL_SYSTEM),
        "tests": {t: {"provider": p, "model": m} for t, (p, m) in TESTS.items()},
        "params": {
            "anthropic": {"max_tokens": ANTH_MAX_TOKENS,
                          "temperature": "0 (haiku-4-5) / 생략 (sonnet-5·opus-5: API 거부, deviation_log 기록)",
                          "prompt_caching": "ephemeral system block"},
            "openai": {"max_completion_tokens": OAI_MAX_COMPLETION,
                       "reasoning_effort": "minimal (nano·mini) / none (gpt-5.4)",
                       "temperature": "생략(추론 모델 제약) — deviation_log 기록"},
        },
        "cost_ceiling_usd": COST_CEILING_USD,
        "batch_discount": BATCH_DISCOUNT,
    }
    (PANEL / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2))
    (PANEL / "system_prompt.txt").write_text(PANEL_SYSTEM, encoding="utf-8")

    if (PANEL / "panel_input.csv").exists() and not (PANEL / "consistency_input.csv").exists():
        _build_consistency_input()
    for scope in ("pilot", "full", "cons"):
        if scope == "cons" and not (PANEL / "consistency_input.csv").exists():
            continue
        rows = _input_rows(scope)
        reps = 3 if scope == "cons" else 1
        for test in LLM_TESTS:
            provider, model = TESTS[test]
            path = PANEL / f"req_{test}_{scope}.jsonl"
            with open(path, "w", encoding="utf-8") as f:
                for req in _requests_for(test, rows, repeats=reps):
                    f.write(json.dumps(req, ensure_ascii=False) + "\n")
        print(f"{scope}: {len(rows)}건 × {len(LLM_TESTS)}검사"
              f"{' × 3회' if reps == 3 else ''} 요청 파일 생성")

    # 비용 추정 (대략: system ~1.4k tok, user ~0.12k, out ~0.1k / 캐시 미반영 상한)
    n = len(_input_rows("full")) + len(_input_rows("pilot"))
    est_in, est_out = 1.55e3 * n, 0.12e3 * n
    total = 0.0
    print("\n[비용 상한 추정 — 프롬프트 캐시 무시한 보수적 값]")
    for test in LLM_TESTS:
        _, model = TESTS[test]
        ci, co = COST[model]
        c = (est_in / 1e6 * ci + est_out / 1e6 * co) * BATCH_DISCOUNT
        total += c
        print(f"  {test} {model:28s} ~${c:6.2f}")
    print(f"  합계 ~${total:.2f}  (상한 ${COST_CEILING_USD})")
    print(f"\nmanifest.json 기록 완료. 프롬프트 SHA-256: {prompt_hash[:16]}…")
    if total > COST_CEILING_USD:
        sys.exit("추정 비용이 상한을 초과합니다. 제출 금지.")


# ---------------------------------------------------------------- submit
def _submit_anthropic(test, scope):
    path = PANEL / f"req_{test}_{scope}.jsonl"
    reqs = [json.loads(l) for l in open(path, encoding="utf-8")]
    body = {"requests": reqs}
    out = json.loads(_http(f"{ANTH_URL}/messages/batches", "POST",
                           _anth_headers(), body))
    return out["id"]


def _submit_openai(test, scope):
    path = PANEL / f"req_{test}_{scope}.jsonl"
    # multipart 업로드
    boundary = "----panelboundary"
    data = path.read_bytes()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nbatch\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"{path.name}\"\r\nContent-Type: application/jsonl\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    h = _oai_headers()
    h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    up = json.loads(_http(f"{OAI_URL}/files", "POST", h, body))
    out = json.loads(_http(f"{OAI_URL}/batches", "POST", _oai_headers(), {
        "input_file_id": up["id"],
        "endpoint": "/v1/chat/completions",
        "completion_window": "24h",
    }))
    return out["id"]


def cmd_submit(args):
    st = _state()
    tests = args.tests.split(",") if args.tests else LLM_TESTS
    if args.scope == "full":
        gate = st.get("pilot_check_passed")
        if not gate and not args.force:
            sys.exit("pilot-check 통과 기록이 없습니다. 먼저 pilot-check를 실행하십시오"
                     " (--force 로 무시 가능하나 deviation_log 기록 필요).")
    for test in tests:
        key = f"{test}_{args.scope}"
        if key in st and st[key].get("batch_id") and not args.force:
            print(f"{key}: 이미 제출됨 ({st[key]['batch_id']}) — 건너뜀")
            continue
        provider, model = TESTS[test]
        old_raw = RAW / f"{key}_raw.jsonl"
        if old_raw.exists():  # 재제출 시 이전 원시 파일은 보존 이름으로 이동
            ts = time.strftime("%Y%m%d_%H%M%S")
            old_raw.rename(RAW / f"{key}_raw_superseded_{ts}.jsonl")
        bid = (_submit_anthropic if provider == "anthropic"
               else _submit_openai)(test, args.scope)
        st[key] = {"provider": provider, "model": model, "batch_id": bid,
                   "status": "submitted",
                   "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
        _save_state(st)
        print(f"{key}: 제출 완료 batch_id={bid}")


# ---------------------------------------------------------------- status/fetch
def _poll(entry):
    if entry["provider"] == "anthropic":
        out = json.loads(_http(f"{ANTH_URL}/messages/batches/{entry['batch_id']}",
                               headers=_anth_headers()))
        entry["status"] = out["processing_status"]  # in_progress / ended
        entry["_results_url"] = out.get("results_url")
        entry["counts"] = out.get("request_counts")
    else:
        out = json.loads(_http(f"{OAI_URL}/batches/{entry['batch_id']}",
                               headers=_oai_headers()))
        entry["status"] = out["status"]  # validating/in_progress/completed/failed…
        entry["_output_file"] = out.get("output_file_id")
        entry["_error_file"] = out.get("error_file_id")
        entry["counts"] = out.get("request_counts")
    return entry


def cmd_status(args):
    st = _state()
    for key, entry in sorted(st.items()):
        if isinstance(entry, dict) and entry.get("chunked"):
            print(f"{key}: 드립 {len(entry.get('done', []))}/{entry.get('n_chunks','?')}조각"
                  f" ({entry.get('status')}) — t6-drip 실행으로 진행")
            continue
        if not isinstance(entry, dict) or "batch_id" not in entry:
            continue
        _poll(entry)
        print(f"{key}: {entry['status']}  {entry.get('counts')}")
    _save_state(st)


def cmd_fetch(args):
    st = _state()
    RAW.mkdir(parents=True, exist_ok=True)
    for key, entry in sorted(st.items()):
        if not isinstance(entry, dict) or "batch_id" not in entry:
            continue
        if entry.get("chunked"):
            continue
        test, scope = key.split("_", 1)
        raw_path = RAW / f"{key}_raw.jsonl"
        if raw_path.exists() and not args.force:
            # 이미 수집된 원시 파일은 재다운로드 없이 재파싱해 통계를 복구
            stats = _parse_raw(test, scope, raw_path)
            st.setdefault("parse", {})[key] = stats
            continue
        _poll(entry)
        done = entry["status"] in ("ended", "completed")
        if not done:
            print(f"{key}: 아직 {entry['status']}")
            continue
        if entry["provider"] == "anthropic":
            blob = _http(entry["_results_url"], headers=_anth_headers())
        else:
            blob = _http(f"{OAI_URL}/files/{entry['_output_file']}/content",
                         headers=_oai_headers())
            if entry.get("_error_file"):
                eb = _http(f"{OAI_URL}/files/{entry['_error_file']}/content",
                           headers=_oai_headers())
                (RAW / f"{key}_errors.jsonl").write_bytes(eb)
        raw_path.write_bytes(blob)  # ★ 원시 응답 verbatim 아카이브 = 재현 대상
        print(f"{key}: 원시 {len(blob)//1024}KB → {raw_path}")
        stats = _parse_raw(test, scope, raw_path)
        st.setdefault("parse", {})[f"{test}_{scope}"] = stats
    _save_state(st)


def _rid_base(rid):
    """반복 접미사 분리: 'P04277@r2'(구) 또는 'P04277_r2'(신) → ('P04277','r2')."""
    if "@" in rid:
        base, _, rep = rid.partition("@")
        return base, (rep or "r1")
    import re as _re2
    m = _re2.match(r"^(.*)_r([0-9]+)$", rid)
    if m:
        return m.group(1), f"r{m.group(2)}"
    return rid, "r1"


def _parse_raw(test, scope, raw_path):
    provider, model = TESTS[test]
    rows_in = {r["id"]: r for r in _input_rows(scope)}
    out, n_fail = [], 0
    for line in open(raw_path, encoding="utf-8"):
        rec = json.loads(line)
        cid = rec.get("custom_id", "")
        rid = cid.split("-", 1)[1] if "-" in cid else cid
        text = ""
        if provider == "anthropic":
            res = rec.get("result", {})
            if res.get("type") == "succeeded":
                content = res["message"].get("content", [])
                text = "".join(b.get("text", "") for b in content
                               if b.get("type") == "text")
        else:
            resp = rec.get("response", {})
            if resp.get("status_code") == 200:
                ch = resp["body"].get("choices", [])
                text = ch[0]["message"].get("content", "") if ch else ""
        p = parse(text)
        if p is None:
            n_fail += 1
            p = {"L1": "판단불가", "L2": "해당없음", "conf": "", "reason": "PARSE_FAIL"}
        src = rows_in.get(_rid_base(rid)[0], {})
        out.append({"id": rid, "조문문장": src.get("조문문장", ""),
                    f"{test}_L1": p["L1"], f"{test}_L2": p["L2"],
                    f"{test}_확신도": p["conf"], f"{test}_근거": p["reason"]})
    out.sort(key=lambda r: r["id"])
    if scope == "cons":   # 3회 반복을 id별 wide로 접고 run 간 일치율 산출
        from collections import defaultdict as _dd
        runs = _dd(dict)
        for r in out:
            rid, rep = _rid_base(r["id"])
            runs[rid][rep] = (r[f"{test}_L1"], r[f"{test}_L2"])
        wide = []
        for rid in sorted(runs):
            d = runs[rid]
            l1s = [d.get(f"r{k}", ("판단불가", ""))[0] for k in (1, 2, 3)]
            l2s = [d.get(f"r{k}", ("", "해당없음"))[1] for k in (1, 2, 3)]
            from collections import Counter as _C
            c1 = _C(l1s).most_common(1)[0]
            c2 = _C(l2s).most_common(1)[0]
            wide.append({"id": rid,
                         "r1_L1": l1s[0], "r2_L1": l1s[1], "r3_L1": l1s[2],
                         "r1_L2": l2s[0], "r2_L2": l2s[1], "r3_L2": l2s[2],
                         "L1_일관성": round(c1[1] / 3, 3),
                         "L2_일관성": round(c2[1] / 3, 3)})
        dest = PANEL / f"labels_{test}_cons.csv"
        _write_csv(dest, wide)
        sc1 = sum(w["L1_일관성"] for w in wide) / max(1, len(wide))
        sc2 = sum(w["L2_일관성"] for w in wide) / max(1, len(wide))
        rate = 1 - n_fail / max(1, len(out))
        print(f"  {test} self-consistency: L1 {sc1:.3f} / L2 {sc2:.3f} "
              f"(n={len(wide)}, 파싱 {rate:.4f}) → {dest}")
        return {"n": len(out), "fail": n_fail, "rate": round(rate, 5),
                "sc_L1": round(sc1, 4), "sc_L2": round(sc2, 4)}
    dest = PANEL / f"labels_{test}_{scope}.csv"
    _write_csv(dest, out)
    rate = 1 - n_fail / max(1, len(out))
    print(f"  파싱 {len(out)}건, 실패 {n_fail} (성공률 {rate:.4f}) → {dest}")
    return {"n": len(out), "fail": n_fail, "rate": round(rate, 5)}


# ---------------------------------------------------------------- t6-drip
def _oai_upload_submit(lines):
    """JSONL 라인 목록을 배치로 제출. 성공 시 batch_id, 한도 초과 시 None."""
    boundary = "----panelboundary"
    data = ("\n".join(lines) + "\n").encode()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"purpose\"\r\n\r\nbatch\r\n"
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
        f"filename=\"chunk.jsonl\"\r\nContent-Type: application/jsonl\r\n\r\n"
    ).encode() + data + f"\r\n--{boundary}--\r\n".encode()
    h = _oai_headers()
    h["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    up = json.loads(_http(f"{OAI_URL}/files", "POST", h, body))
    out = json.loads(_http(f"{OAI_URL}/batches", "POST", _oai_headers(), {
        "input_file_id": up["id"], "endpoint": "/v1/chat/completions",
        "completion_window": "24h"}))
    return out["id"]


def cmd_t6_drip(args):
    """gpt-5.4 조직 대기열 한도(1.35M 토큰) 우회: full 요청을 조각으로 순차 제출.
    이전 조각이 끝나야 다음 조각이 들어간다. 완료 조각 결과는 즉시 아카이브.
    실행 예: caffeinate -i .venv/bin/python src/panel_annotate.py t6-drip
    (터미널을 열어 두는 동안 자동 진행; 중단해도 재실행하면 이어서 진행)"""
    test, scope = "T6", args.scope
    key = f"T6_{scope}"
    lines = [l.rstrip("\n") for l in open(PANEL / f"req_T6_{scope}.jsonl", encoding="utf-8")]
    chunks = [lines[i:i + args.chunk] for i in range(0, len(lines), args.chunk)]
    st = _state()
    d = st.get(key) if isinstance(st.get(key), dict) and st.get(key, {}).get("chunked") \
        else {"chunked": True, "provider": "openai", "model": "gpt-5.4",
              "n_chunks": len(chunks), "done": [], "current": None, "status": "drip"}
    st[key] = d
    _save_state(st)
    RAW.mkdir(parents=True, exist_ok=True)
    raw_path = RAW / f"{key}_raw.jsonl"
    print(f"T6 드립: {len(lines)}건을 {len(chunks)}조각 × ≤{args.chunk}건으로 순차 제출")
    while len(d["done"]) < len(chunks):
        if d["current"]:
            b = json.loads(_http(f"{OAI_URL}/batches/{d['current']['batch_id']}",
                                 headers=_oai_headers()))
            stat = b["status"]
            if stat in ("completed", "failed", "expired", "cancelled"):
                if b.get("output_file_id"):
                    blob = _http(f"{OAI_URL}/files/{b['output_file_id']}/content",
                                 headers=_oai_headers())
                    with open(raw_path, "ab") as f:
                        f.write(blob)
                if b.get("error_file_id"):
                    eb = _http(f"{OAI_URL}/files/{b['error_file_id']}/content",
                               headers=_oai_headers())
                    with open(RAW / f"{key}_errors.jsonl", "ab") as f:
                        f.write(eb)
                if stat != "completed":
                    print(f"  조각 {d['current']['idx']}: {stat} — errors 아카이브 확인 필요")
                d["done"].append(d["current"]["batch_id"])
                d["current"] = None
                _save_state(st)
                print(f"  진행 {len(d['done'])}/{len(chunks)} 조각 완료")
                continue
            cnt = b.get("request_counts") or {}
            print(f"  조각 {d['current']['idx']} {stat} {cnt.get('completed',0)}/{cnt.get('total','?')} …대기")
        else:
            idx = len(d["done"])
            try:
                bid = _oai_upload_submit(chunks[idx])
                d["current"] = {"idx": idx + 1, "batch_id": bid}
                _save_state(st)
                print(f"  조각 {idx+1}/{len(chunks)} 제출: {bid}")
            except SystemExit as e:
                if "token_limit_exceeded" in str(e):
                    print("  한도 대기 중…")
                else:
                    raise
        time.sleep(args.interval)
    d["status"] = "ended"
    _save_state(st)
    stats = _parse_raw(test, scope, raw_path)
    st = _state()
    st.setdefault("parse", {})[key] = stats
    st[key]["status"] = "ended"
    _save_state(st)
    print("T6 드립 완료.")


# ---------------------------------------------------------------- pilot-check
def cmd_pilot_check(args):
    st = _state()
    ok = True
    print("[파일럿 게이트 — 등록 §4: 검사별 파싱 성공률 ≥ 99.5%]")
    for test in LLM_TESTS:
        p = st.get("parse", {}).get(f"{test}_pilot")
        if not p:
            print(f"  {test}: 파일럿 결과 없음"); ok = False; continue
        flag = "PASS" if p["rate"] >= 0.995 else "FAIL"
        if flag == "FAIL":
            ok = False
        print(f"  {test}: rate={p['rate']}  {flag}")
    st["pilot_check_passed"] = ok
    _save_state(st)
    print("→ 통과, full 제출 가능" if ok else
          "→ 실패 검사 수리 후 파일럿 재실행 (실패 배치는 raw에 보존됨)")


# ---------------------------------------------------------------- rulebase(T7)
import re as _re

_FORM_PAT = "(대통령령|총리령|[가-힣]{1,8}부령|조례|교육규칙|고시|훈령|예규)"

def _norm_form(s):
    if s.endswith("부령") or s == "총리령":
        return "부령"
    return s

def rule_label(sent):
    """결정론적 T7. 코드북 v1.1의 경계 규칙을 표층 패턴으로 근사."""
    s = (sent or "").strip()
    if not s:
        return "판단불가", "해당없음"
    if "준용" in s:
        return "인용", "해당없음"
    if _re.search(r"「[^」]+」에\s*따른", s) and not _re.search(_FORM_PAT + r"으?로\s*정하", s):
        return "인용", "해당없음"
    if _re.search(r"(따로\s*)?법률로\s*정한다", s):
        return "인용", "해당없음"
    # 완료형(관형) '…으로 정한 + 명사' → 인용 ('정한다'는 제외; 앵커 A1과 동일)
    if _re.search(_FORM_PAT + r"으?로\s*정한(?!다)", s):
        return "인용", "해당없음"
    forms = [_norm_form(m.group(1)) for m in
             _re.finditer(_FORM_PAT + r"(?=(으?로|에서|이나|이란|을|의)?\s*(정하|정한|위임|따라))", s)]
    forms = list(dict.fromkeys(forms))
    if _re.search(_FORM_PAT + r"으?로\s*정하(는|여|되|고)|정하는\s*바에\s*따라|"
                 + _FORM_PAT + r"으?로\s*정한다|" + _FORM_PAT + r"으?로\s*정할\s*것", s) and forms:
        return "위임", "|".join(forms)
    if forms and _re.search(r"정한다\s*[.」』]?\s*$", s):
        return "위임", "|".join(forms)
    # 절단 스니펫: '…사항은 대통령령으로' 처럼 형식+'(으)로'로 끝남 → 위임 (코드북 절단 규칙)
    m_trunc = _re.search(_FORM_PAT + r"으?로\s*$", s)
    if m_trunc:
        return "위임", _norm_form(m_trunc.group(1))
    if _re.search(r"(장관|교육감|청장|위원회)[이가]\s*(정|지정|고시)하(는|여)", s):
        return "위임", "미특정"
    if forms:
        return "인용", "해당없음"
    return "판단불가", "해당없음"


def cmd_rulebase(args):
    for scope in ("pilot", "full"):
        rows = _input_rows(scope)
        out = []
        for r in rows:
            l1, l2 = rule_label(r.get("조문문장", ""))
            out.append({"id": r["id"], "조문문장": r.get("조문문장", ""),
                        "T7_L1": l1, "T7_L2": l2, "T7_확신도": "", "T7_근거": "rule"})
        _write_csv(PANEL / f"labels_T7_{scope}.csv", out)
        print(f"T7 {scope}: {len(out)}건 (결정론)")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build-input").set_defaults(func=cmd_build_input)
    sub.add_parser("prepare").set_defaults(func=cmd_prepare)
    s = sub.add_parser("submit")
    s.add_argument("--scope", choices=["pilot", "full", "cons"], required=True)
    s.add_argument("--tests", help="쉼표구분 예: T1,T4 (기본: 전체 LLM 검사)")
    s.add_argument("--force", action="store_true")
    s.set_defaults(func=cmd_submit)
    sub.add_parser("status").set_defaults(func=cmd_status)
    f = sub.add_parser("fetch")
    f.add_argument("--force", action="store_true")
    f.set_defaults(func=cmd_fetch)
    sub.add_parser("pilot-check").set_defaults(func=cmd_pilot_check)
    t6 = sub.add_parser("t6-drip", help="gpt-5.4 대기열 한도 우회 순차 분할 제출")
    t6.add_argument("--scope", choices=["full", "cons"], default="full")
    t6.add_argument("--chunk", type=int, default=400)  # 400×(입력~1.6k+출력1k)≈1.0M < 1.35M 한도
    t6.add_argument("--interval", type=int, default=120)
    t6.set_defaults(func=cmd_t6_drip)
    sub.add_parser("rulebase").set_defaults(func=cmd_rulebase)
    a = ap.parse_args()
    a.func(a)


if __name__ == "__main__":
    main()
