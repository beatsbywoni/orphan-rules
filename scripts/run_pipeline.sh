#!/bin/bash
# orphan-rules 수집 파이프라인 (트랙 B 기준: goldset 200건)
# 사용법: 터미널에서  bash ~/Desktop/orphan-rules/run_pipeline.sh
# 예상 소요: 15~25분 (행정규칙 본문 261건 + 위임조회 273건, 호출당 0.4초 지연)
set -u
cd "$(dirname "$0")"
: "${MOLEG_OC:?export MOLEG_OC=<your NLIC OC key> first}"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q requests

mkdir -p logs
LOG="logs/pipeline_$(date +%Y%m%d_%H%M).log"
echo "로그: $LOG"

run() {
  echo "===== $* =====" | tee -a "$LOG"
  python src/collect_moleg.py "$@" 2>&1 | tee -a "$LOG"
}

run smoke
run casecheck
run laws
run admrules
run delegation
run detect
run goldset --n 200 --pilot 0.5

echo "" | tee -a "$LOG"
echo "완료. data/summary.json 을 확인하고, Cowork 세션에 '파이프라인 끝났어'라고 알려주세요." | tee -a "$LOG"
