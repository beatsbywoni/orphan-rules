#!/bin/bash
# 헌재결정례(detc)만 재수집 — Detc 키 버그 수정 후 보완 실행 (10~20분)
# 사용법: bash ~/Desktop/orphan-rules/run_oracle_detc.sh
set -u
cd "$(dirname "$0")"
: "${MOLEG_OC:?export MOLEG_OC=<your NLIC OC key> first}"
source .venv/bin/activate
mkdir -p logs
python src/collect_moleg.py oracle --targets detc --per-query 100 --out oracle_detc.csv \
  2>&1 | tee -a "logs/oracle_detc_$(date +%Y%m%d_%H%M).log"
echo "완료. data/oracle_detc.csv 생성 — Cowork 세션이 oracle_to_label.csv에 병합합니다."
