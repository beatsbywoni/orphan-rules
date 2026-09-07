#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""make_public.py — 공개 저장소 번들 `public/` 을 작업 트리에서 결정론적으로 재생성한다.

왜 있는가
---------
`public/` 은 2026-08-15 에 손으로 한 번 만들어졌다. 그 뒤 Phase 1 패널이 통째로
들어왔지만 번들은 그대로였다. 손으로 만든 번들은 (a) 원본이 바뀌면 조용히 낡고,
(b) 스크럽을 사람이 기억해야 한다. 실제로 `cmd_ministry_stats` 가 산출 JSON 에
OC 를 적어 넣은 사고가 있었다(docs/28).

이 스크립트는 그 둘을 없앤다. 매니페스트에 적힌 파일만 원본에서 복사하고,
치환표대로 스크럽하고, 마지막에 금지 문자열을 **전수 검사해서 하나라도 남으면
0 이 아닌 코드로 죽는다.** 통과하지 못한 번들은 만들어지지 않는다.

두 층으로 나뉜다
----------------
- **저장소(이 번들)** — 코드, 라벨 전량, 패널 산출물, 코드북, 편차 로그. ~25MB.
- **DOI 아카이브(Zenodo)** — 원시 API 응답 `data/raw/`(218MB)와 패널 요청
  페이로드 `data/panel/req_*.jsonl`(155MB). 저장소에 넣기엔 크고, 원고가
  재현 대상으로 지정한 것은 요청이 아니라 **산출물**이다.
  `DEPOSIT_ONLY` 에 적혀 있고 실행할 때마다 출력된다 — 조용히 빠지지 않는다.

민감 문자열은 코드에 없다
--------------------------
OC·OSF 식별자·저자명 같은 실제 문자열은 `.scrub_terms` 에 있고, 이 파일은
번들에 들어가지 않는다(`.gitignore`). 스크립트 자체를 공개해도 식별자가 같이
나가지 않는다 — 처음 이 검사를 돌렸을 때 검사기가 **자기 자신을** 잡아냈고,
그게 맞았다. `.scrub_terms` 없이는 번들을 만들지 않는다.

심사용 익명화
-------------
기본값은 **심사용**이다. OSF 등록 식별자를 가림 문구로 치환한다 —
`data/panel/manifest.json` 이 등록 URL 을 담고 있어서, 그대로 두면 익명 링크로
공개하는 순간 사전등록 기록을 통해 저자가 드러난다. 게재 확정 후에는
`--camera-ready` 로 실제 식별자를 넣어 다시 만든다.

사용
----
    python3 src/make_public.py                  # 심사용 재생성 + 검사
    python3 src/make_public.py --camera-ready   # 게재본용 (OSF 식별자 노출)
    python3 src/make_public.py --check          # 검사만 (파일을 쓰지 않는다)
    python3 src/make_public.py --diff           # 무엇이 바뀌는지만 본다

종료코드 0 = 통과, 1 = 금지 문자열 잔존 또는 원본 누락.

건드리지 않는 것
----------------
`public/README.md`, `LICENSE`, `requirements.txt`, `.gitignore`,
`codebook/annotation_guideline.md` 은 번들에서 직접 쓰고 관리하는 원본이다
(작업 트리에 대응 파일이 없다). 덮어쓰지 않고 검사만 한다.

지우지 않는 것
--------------
매니페스트에 없는 파일이 `public/` 에 있어도 지우지 않는다. ⚠ 로 알린다.
삭제는 사람이 판단할 일이다.
"""
from __future__ import annotations

import argparse
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUB = ROOT / "public"

# ── 매니페스트 ────────────────────────────────────────────────────────────────
# (원본 경로, 번들 내 경로, 처리기)
#   "copy"   원본 그대로 복사 후 일반 치환
#   "script" 셸 스크립트 — OC 대입 줄을 가드 형태로 바꾼 뒤 일반 치환
MANIFEST: list[tuple[str, str, str]] = [
    # ── 코드 ─────────────────────────────────────────────────────────────────
    ("src/collect_moleg.py",           "src/collect_moleg.py",           "copy"),
    ("src/resolve_external_claims.py", "src/resolve_external_claims.py", "copy"),
    ("src/llm_annotate.py",            "src/llm_annotate.py",            "copy"),
    ("src/agreement.py",               "src/agreement.py",               "copy"),
    # Phase 1 패널·추정량 — 원고 §6.4~§6.6 의 모든 수치가 여기서 나온다
    ("src/panel_annotate.py",          "src/panel_annotate.py",          "copy"),
    ("src/dsl_estimate.py",            "src/dsl_estimate.py",            "copy"),
    ("src/anchors.py",                 "src/anchors.py",                 "copy"),
    ("src/fulltext_check.py",          "src/fulltext_check.py",          "copy"),
    # 재검사(§6.2)
    ("src/retest_kappa.py",            "src/retest_kappa.py",            "copy"),
    ("src/make_retest_workbook.py",    "src/make_retest_workbook.py",    "copy"),
    # 트리아지 기계 패널 (게이트 P1-1 — 동결 루브릭 + 재라벨 코드)
    ("src/triage_panel.py",            "src/triage_panel.py",            "copy"),
    ("docs/triage_rubric_T1_v1.md",    "docs/triage_rubric_T1_v1.md",    "copy"),
    ("docs/34_triage_panel_result.md",  "docs/triage_panel_result.md",    "copy"),
    # 주장 조문 원문 대조 (9/7 게재가능성 진단 R2 — 등록 외 사후 분석, deviation_log D-2026-09-07-2)
    ("src/claim_check.py",             "src/claim_check.py",             "copy"),
    ("data/claim_check_labeled.csv",   "data/labels/claim_check_labeled.csv", "copy"),
    ("docs/39_claim_check_result.md",  "docs/claim_check_result.md",     "copy"),
    # 그림 생성 (원고 Fig. 1–2 — 재현성 서사와 일관되게 스크립트 공개)
    ("src/make_figures.py",            "src/make_figures.py",            "copy"),
    # 이 번들 자신을 만든 코드 — 무엇이 어떻게 스크럽됐는지 독자가 확인할 수 있게
    ("src/make_public.py",             "src/make_public.py",             "copy"),
    ("src/make_deposit.py",            "src/make_deposit.py",            "copy"),

    # ── 라벨 (Braun 2024 보고 권고에 따라 전량 공개) ──────────────────────────
    ("data/oracle_labeled_v2.csv",          "data/labels/oracle_labeled_v2.csv",          "copy"),
    ("data/goldset_labeled_v2.csv",         "data/labels/goldset_labeled_v2.csv",         "copy"),
    ("data/goldset_llm.csv",                "data/labels/goldset_llm.csv",                "copy"),
    ("data/external_claims_resolution.csv", "data/labels/external_claims_resolution.csv", "copy"),
    # 트리아지 — v2 와 v3 를 **둘 다** 낸다. 원고가 "all versions" 라고 적었고,
    # 실제로 T032·T081·T127 세 건이 8월 18일 전문 재확인으로 바뀌었다
    # (총계 61/77 은 두 판본이 같다 — 두 건이 서로 상쇄).
    ("data/findings_D1_triage_v2.csv",      "data/labels/findings_D1_triage_v2.csv",      "copy"),
    ("data/findings_D1_triage_v3.csv",      "data/labels/findings_D1_triage_v3.csv",      "copy"),
    # 8월 단기 재검사(§6.2 의 3일 간격 검사) + 9월 재검사 백지 양식
    ("data/goldset_retest_0818.csv",        "data/labels/goldset_retest_0818.csv",        "copy"),
    ("data/triage_retest_0818.csv",         "data/labels/triage_retest_0818.csv",         "copy"),
    ("data/goldset_retest_sept_blank.csv",  "data/labels/goldset_retest_sept_blank.csv",  "copy"),
    ("data/goldset_retest_sept_labeled.csv","data/labels/goldset_retest_sept_labeled.csv","copy"),
    ("data/goldset_retest_sept.xlsx",       "data/labels/goldset_retest_sept.xlsx",       "copy"),

    # ── 패널 (원고가 지정한 재현 대상) ───────────────────────────────────────
    ("data/panel/manifest.json",        "data/panel/manifest.json",        "copy"),
    ("data/panel/state.json",           "data/panel/state.json",           "copy"),
    ("data/panel/system_prompt.txt",    "data/panel/system_prompt.txt",    "copy"),
    ("data/panel/calibration_map.csv",  "data/panel/calibration_map.csv",  "copy"),
    ("data/panel/anchor_gate_full.json","data/panel/anchor_gate_full.json","copy"),
    ("data/panel/dsl_results_full.json","data/panel/dsl_results_full.json","copy"),
    ("data/panel/panel_input.csv",      "data/panel/panel_input.csv",      "copy"),
    ("data/panel/consistency_input.csv","data/panel/consistency_input.csv","copy"),
    # 전문 확인 실험(§8.4) — 폐기된 판본도 이름 그대로 낸다
    ("data/panel/fulltext/ftcheck_input.csv",  "data/panel/fulltext/ftcheck_input.csv",  "copy"),
    ("data/panel/fulltext/ftcheck_req.jsonl",  "data/panel/fulltext/ftcheck_req.jsonl",  "copy"),
    ("data/panel/fulltext/ftcheck_raw.jsonl",  "data/panel/fulltext/ftcheck_raw.jsonl",  "copy"),
    ("data/panel/fulltext/ftcheck_result.csv", "data/panel/fulltext/ftcheck_result.csv", "copy"),
    ("data/panel/fulltext/ftcheck_raw_SUPERSEDED_wrongarticle.jsonl",
     "data/panel/fulltext/ftcheck_raw_SUPERSEDED_wrongarticle.jsonl", "copy"),
    ("data/panel/fulltext/ftcheck_result_SUPERSEDED_wrongarticle.csv",
     "data/panel/fulltext/ftcheck_result_SUPERSEDED_wrongarticle.csv", "copy"),
    ("data/panel/fulltext/state.json",  "data/panel/fulltext/state.json",  "copy"),

    # ── 사전등록 준수 기록 ───────────────────────────────────────────────────
    ("docs/deviation_log.md",           "docs/deviation_log.md",           "copy"),

    # ── 요약·표 ──────────────────────────────────────────────────────────────
    ("data/summary.json",                  "data/summary.json",                  "copy"),
    ("output/tables/table6_agreement.csv", "output/tables/table6_agreement.csv", "copy"),
    ("output/tables/table7_audit.csv",     "output/tables/table7_audit.csv",     "copy"),
    ("output/figures/fig1_edges.png",      "output/figures/fig1_edges.png",      "copy"),
    ("output/figures/fig2_triage.png",     "output/figures/fig2_triage.png",     "copy"),

    # ── 라이선스 (심사용에서는 저작권자 표기를 가린다) ────────────────────────
    ("LICENSE", "LICENSE", "copy"),

    # ── 실행 래퍼 ────────────────────────────────────────────────────────────
    ("run_pipeline.sh",    "scripts/run_pipeline.sh",    "script"),
    ("run_llm.sh",         "scripts/run_llm.sh",         "script"),
    ("run_crossref.sh",    "scripts/run_crossref.sh",    "script"),
    ("run_oracle.sh",      "scripts/run_oracle.sh",      "script"),
    ("run_oracle_detc.sh", "scripts/run_oracle_detc.sh", "script"),
]

# 트리아지 기계 패널 산출 — 2모델 × 3회
for _m in ("claude-sonnet-5", "gpt-5-mini"):
    for _k in (1, 2, 3):
        MANIFEST.append((f"data/triage_panel/labels_{_m}_r{_k}.csv",
                         f"data/triage_panel/labels_{_m}_r{_k}.csv", "copy"))

# 패널 라벨 — T1~T7 파일럿/전수, T1~T6 자기일관성(T7 은 결정론적이라 없다)
for _t in range(1, 8):
    MANIFEST.append((f"data/panel/labels_T{_t}_pilot.csv",
                     f"data/panel/labels_T{_t}_pilot.csv", "copy"))
    MANIFEST.append((f"data/panel/labels_T{_t}_full.csv",
                     f"data/panel/labels_T{_t}_full.csv", "copy"))
for _t in range(1, 7):
    MANIFEST.append((f"data/panel/labels_T{_t}_cons.csv",
                     f"data/panel/labels_T{_t}_cons.csv", "copy"))

# 저장소가 아니라 DOI 아카이브로 가는 것. 조용히 빠지지 않도록 실행할 때마다 출력한다.
DEPOSIT_ONLY = [
    ("data/raw/",                  "원시 API 응답 — MST 고정 스냅숏"),
    ("data/panel/req_*.jsonl",     "패널 요청 페이로드 — 재현 대상은 요청이 아니라 산출물"),
    ("data/admrules.jsonl, data/laws.jsonl, data/edges.jsonl", "통합 코퍼스(중간 산출물)"),
]

# 번들에서 직접 관리하는 원본 — 덮어쓰지 않는다
AUTHORED = [
    "README.md",
    "requirements.txt",
    ".gitignore",
    "codebook/annotation_guideline.md",
]

# ── 스크럽 ────────────────────────────────────────────────────────────────────
# 실제 문자열은 코드에 두지 않는다. `.scrub_terms` 형식(| 구분, # 주석):
#     역할 | 문자열 | 치환값 | 설명
#   oc   — 복사할 때 치환하고, 남아 있으면 치명
#   osf  — 심사용에서만 치환·치명. --camera-ready 면 그대로 둔다
#   name — 저자 표기형. osf 와 같은 규칙 (심사용에서만 치환·치명)
#   deny — 치환하지 않는다. 나오면 치명 (애초에 나올 일이 없어야 하는 것)
#   warn — 나오면 경고만
TERMS_FILE = ROOT / ".scrub_terms"

SHELL_GUARD = ': "${MOLEG_OC:?export MOLEG_OC=<your NLIC OC key> first}"'

# 셸에서 OC 를 값으로 대입하는 모든 형태
#   export MOLEG_OC=...
#   export MOLEG_OC="${MOLEG_OC:-...}"
SHELL_OC_ASSIGN = re.compile(r'^\s*export\s+MOLEG_OC=.*$', re.M)

TEXT_SUFFIXES = {".py", ".sh", ".csv", ".json", ".md", ".txt", ".jsonl", ".yml", ".yaml"}

# 문자열이 아니라 모양으로 잡는 것 — 여기에는 둬도 안전하다
SHAPE_RULES = [
    (re.compile(r"sk-[A-Za-z0-9_-]{20,}"),  "API 키로 보이는 문자열", True),
    (re.compile(r"/Users/[A-Za-z0-9._-]+"), "로컬 홈 디렉터리 경로",  False),
]


def load_terms() -> list[tuple[str, str, str, str]] | None:
    if not TERMS_FILE.exists():
        return None
    out = []
    for raw in TERMS_FILE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        parts = [x.strip() for x in line.split("|")]
        while len(parts) < 4:
            parts.append("")
        out.append(tuple(parts[:4]))
    return out


def forbidden(terms, camera_ready: bool):
    """번들에 남아 있으면 안 되는 것. (패턴, 설명, 치명 여부)"""
    rules = []
    for role, lit, _repl, label in terms:
        if role in ("osf", "name") and camera_ready:
            continue
        if role in ("oc", "osf", "name", "deny"):
            rules.append((re.compile(re.escape(lit), re.I), label or lit, True))
        elif role == "warn":
            rules.append((re.compile(re.escape(lit), re.I), label or lit, False))
    return rules + SHAPE_RULES


def scrub(text: str, kind: str, terms, camera_ready: bool) -> str:
    if kind == "script":
        text = SHELL_OC_ASSIGN.sub(SHELL_GUARD, text)
    for role, lit, repl, _label in terms:
        if role == "oc":
            text = text.replace(lit, repl)
        elif role == "name" and not camera_ready:
            text = text.replace(lit, repl)
        elif role == "osf" and not camera_ready:
            text = re.sub(rf"https?://osf\.io/{re.escape(lit)}\b", repl, text, flags=re.I)
            text = re.sub(rf"\b{re.escape(lit)}\b", repl, text, flags=re.I)
    return text


def read_text(p: Path) -> str | None:
    """복사·치환용. 확장자 화이트리스트 + 확장자 없는 파일(LICENSE 류).

    확장자가 없는 파일을 바이너리로 넘기면 치환이 통째로 건너뛰어진다 —
    실제로 `LICENSE` 의 저작권자 줄이 그렇게 살아남았다."""
    if p.suffix and p.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def scan_text(p: Path) -> str | None:
    """검사용. 확장자를 보지 않는다 — 디코딩되면 본다.

    처음 이 검사를 통과한 번들의 `LICENSE` 에 저작권자 이름이 그대로 남아
    있었다. 확장자가 없어서 화이트리스트에 걸리지 않았기 때문이다. 검사에서는
    확장자를 신뢰하지 않는다."""
    try:
        return p.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def build(dry: bool, terms, camera_ready: bool) -> tuple[list[str], list[str]]:
    """매니페스트대로 번들을 채운다. (바뀐 것, 없는 원본) 반환."""
    changed, missing = [], []
    for src_rel, dst_rel, kind in MANIFEST:
        src, dst = ROOT / src_rel, PUB / dst_rel
        if not src.exists():
            missing.append(src_rel)
            continue
        text = read_text(src)
        if text is None:                       # 바이너리 — 그대로 복사
            if not (dst.exists() and dst.read_bytes() == src.read_bytes()):
                changed.append(dst_rel)
                if not dry:
                    dst.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(src, dst)
            continue
        out = scrub(text, kind, terms, camera_ready)
        if not (dst.exists() and dst.read_text(encoding="utf-8") == out):
            changed.append(dst_rel)
            if not dry:
                dst.parent.mkdir(parents=True, exist_ok=True)
                dst.write_text(out, encoding="utf-8")
    return changed, missing


def verify(terms, camera_ready: bool) -> tuple[list[str], list[str]]:
    """번들 전체를 훑는다. (치명, 경고) 반환. 매니페스트 밖 파일도 본다."""
    rules = forbidden(terms, camera_ready)
    fatal, warn = [], []
    for p in sorted(PUB.rglob("*")):
        if not p.is_file() or ".git" in p.parts or p.name == ".DS_Store":
            continue
        text = scan_text(p)
        if text is None:
            continue
        rel = p.relative_to(PUB)
        for pat, label, is_fatal in rules:
            hits = pat.findall(text)
            if hits:
                (fatal if is_fatal else warn).append(f"{rel} — {label} {len(hits)}건")
    return fatal, warn


def strays() -> list[str]:
    """매니페스트에도 AUTHORED 에도 없는 파일. 지우지 않고 알리기만 한다."""
    known = {d for _, d, _ in MANIFEST} | set(AUTHORED)
    return [str(p.relative_to(PUB)) for p in sorted(PUB.rglob("*"))
            if p.is_file() and ".git" not in p.parts and p.name != ".DS_Store"
            and str(p.relative_to(PUB)) not in known]


def total_bytes() -> int:
    return sum(p.stat().st_size for p in PUB.rglob("*") if p.is_file())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="검사만 한다 (쓰지 않음)")
    ap.add_argument("--diff",  action="store_true", help="무엇이 바뀌는지만 본다 (쓰지 않음)")
    ap.add_argument("--camera-ready", action="store_true",
                    help="게재본용 — OSF 식별자를 가리지 않는다. 심사 전에는 쓰지 말 것")
    a = ap.parse_args()
    dry = a.check or a.diff
    cr = a.camera_ready

    if not PUB.exists():
        print(f"✘ {PUB} 가 없다. 번들 원본(README·LICENSE·codebook)이 먼저 있어야 한다.")
        return 1

    terms = load_terms()
    if terms is None:
        print(f"✘ {TERMS_FILE} 가 없다. 민감 문자열 목록이 없으면 스크럽도 검사도 못 한다.")
        print("  형식:  역할 | 문자열 | 치환값 | 설명     (역할: oc / osf / deny / warn)")
        return 1

    print(f"[번들] {PUB}")
    print(f"[검사 목록] {TERMS_FILE.name} — {len(terms)}개 항목 (+ 모양 규칙 {len(SHAPE_RULES)}개)")
    print(f"[모드] {'게재본 — OSF 식별자 노출' if cr else '심사용 — OSF 식별자 가림'}")
    print(f"[매니페스트] {len(MANIFEST)}개 파일")

    if not a.check:
        changed, missing = build(dry, terms, cr)
        if missing:
            print(f"\n✘ 원본 없음 {len(missing)}건 — 매니페스트를 고치거나 파일을 만들 것")
            for m in missing:
                print(f"    {m}")
        if changed:
            print(f"\n{'바뀔 것' if dry else '갱신됨'} {len(changed)}건")
            for c in changed:
                print(f"    {c}")
        else:
            print("\n  갱신할 것 없음 — 번들이 원본과 같다")
        if missing:
            return 1

    print("\n[저장소에 넣지 않고 DOI 아카이브로 보내는 것]")
    for path, why in DEPOSIT_ONLY:
        print(f"    {path}  — {why}")

    print("\n[식별 문자열 검사]")
    fatal, warn = verify(terms, cr)
    for w in warn:
        print(f"  ⚠ {w}")
    for f in fatal:
        print(f"  ✘ {f}")
    if not fatal and not warn:
        print("  ✔ 0건")

    s = strays()
    if s:
        print(f"\n[매니페스트 밖 파일 {len(s)}건] — 지우지 않았다. 공개 전에 확인할 것")
        for x in s:
            print(f"    {x}")

    print(f"\n[번들 크기] {total_bytes()/1_048_576:.1f} MB")

    if fatal:
        print("\n=== 실패. 위 ✘ 가 남아 있는 한 저장소를 공개하지 말 것. ===")
        return 1
    print("\n=== 통과. 공개해도 되는 상태다. ===")
    return 0


if __name__ == "__main__":
    sys.exit(main())
