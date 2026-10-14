#!/usr/bin/env bash
# A 版(固定ルール)の一括確認: 開始位置を変えて赤い箱へ。
cd "$(dirname "$0")/.."
for pose in "0 0 0" "0 2 0" "0 -2 0.5" "-2 0 3.14" "1 3 -1.2"; do
  echo "== start=($pose)"
  scripts/run_scenario.sh $pose red 2>&1 | grep -E "RESULT|FINAL"
done
echo done
