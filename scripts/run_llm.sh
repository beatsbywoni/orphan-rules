#!/bin/bash
# LLM 제2 어노테이터 실행 (트랙 B) — 맥 터미널 전용 (클라우드에서 api.openai.com 차단 확인)
# 예상 비용: gpt-4o, 200건 × 3회 ≈ $1.5~2.5
#
# 사용법:
#   export LLM_API_KEY=sk-...     ← 터미널에 직접 입력 (파일에 저장하지 말 것)
#   bash ~/Desktop/orphan-rules/run_llm.sh
set -u
cd "$(dirname "$0")"
if [ -z "${LLM_API_KEY:-}" ]; then
  echo "LLM_API_KEY가 없습니다. 먼저:  export LLM_API_KEY=sk-..." ; exit 1
fi
export LLM_BASE_URL=https://api.openai.com/v1
export LLM_MODEL=gpt-4o
source .venv/bin/activate
mkdir -p logs
python src/llm_annotate.py \
  --in data/goldset_labeled_v2.csv \
  --out data/goldset_llm.csv \
  --repeats 3 2>&1 | tee -a "logs/llm_$(date +%Y%m%d_%H%M).log"
echo ""
echo "완료. 저자 라벨은 이미 확정되어 있으므로 data/goldset_llm.csv를 열어봐도 됩니다."
echo "Cowork 세션에 알려주면 κ 산출·감사 표 생성을 진행합니다."
