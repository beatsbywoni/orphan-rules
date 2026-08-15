#!/bin/bash
# 판례·헌재·해석례 오라클 스크리닝 (30~60분 소요)
# 사용법: run_pipeline.sh 와 "다른 터미널 탭에서" 병렬 실행 가능
#   bash ~/Desktop/orphan-rules/run_oracle.sh
set -u
cd "$(dirname "$0")"
: "${MOLEG_OC:?export MOLEG_OC=<your NLIC OC key> first}"

if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q requests

mkdir -p logs
LOG="logs/oracle_$(date +%Y%m%d_%H%M).log"
echo "로그: $LOG (30~60분 걸립니다. 탭을 닫지 마세요)"

python src/collect_moleg.py oracle --targets prec,detc,expc --per-query 100 2>&1 | tee -a "$LOG"

echo "" | tee -a "$LOG"
echo "완료. data/oracle_to_label.csv 생성됨." | tee -a "$LOG"
