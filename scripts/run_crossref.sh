#!/bin/bash
# D1 중 타부처 법령 근거 주장 규칙의 실제 위임 여부 확인 (5~10분)
# 사용법: bash ~/Desktop/orphan-rules/run_crossref.sh
set -u
cd "$(dirname "$0")"
: "${MOLEG_OC:?export MOLEG_OC=<your NLIC OC key> first}"
source .venv/bin/activate
mkdir -p logs
python src/resolve_external_claims.py 2>&1 | tee -a "logs/crossref_$(date +%Y%m%d_%H%M).log"
