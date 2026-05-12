#!/usr/bin/env bash
# 一键产出论文第四章底稿。
# 用法：
#   bash scripts/paper.sh mbpp 10 3 data/out/paper_qwen
# 参数：
#   $1 dataset   默认 mbpp
#   $2 samples   默认 10
#   $3 max_round 默认 3
#   $4 out_root  默认 data/out/paper_qwen

set -euo pipefail

DATASET="${1:-mbpp}"
SAMPLES="${2:-10}"
MAX_ROUND="${3:-3}"
OUT_ROOT="${4:-data/out/paper_qwen}"

CMP_DIR="${OUT_ROOT}/cmp"
REG_DIR="${OUT_ROOT}/reg"
CH4_DIR="${OUT_ROOT}/ch4"

mkdir -p "${CMP_DIR}" "${REG_DIR}" "${CH4_DIR}"

export PYTHONPATH=.

python scripts/exp_cmp.py \
  --dataset "${DATASET}" \
  --samples "${SAMPLES}" \
  --max-round "${MAX_ROUND}" \
  --out-dir "${CMP_DIR}" \
  --require-real

python scripts/reg_qwen.py \
  --dataset "${DATASET}" \
  --samples "${SAMPLES}" \
  --max-round "${MAX_ROUND}" \
  --out-dir "${REG_DIR}" \
  --require-real

python scripts/ch4_draft.py \
  --cmp "${CMP_DIR}/cmp.json" \
  --case-pack "${REG_DIR}/reg_qwen_case_pack.json" \
  --out-dir "${CH4_DIR}"

echo "=== done ==="
echo "compare: ${CMP_DIR}"
echo "regress: ${REG_DIR}"
echo "chapter4: ${CH4_DIR}"
