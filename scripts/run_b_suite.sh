#!/usr/bin/env bash
# B 版の一括確認: 初期位置と指示文を変えて走らせ、結果を表示する(1ケース約 1〜3 分)。
cd "$(dirname "$0")/.."
run() {  # <x y yaw> <color> <指示文>
  echo "== start=($1) | $3"
  MODE=llm INSTRUCTION="$3" scripts/run_scenario.sh $1 "$2" 2>&1 | grep -E "RESULT|FINAL|EMERGENCY"
}
run "0 0 0"     blue "青い箱に近づいて止まれ"
run "0 2 0"     red  "赤い箱のところまで行って、着いたら止まって"
run "0 -2 0.5"  blue "青いボックスへ向かって、手前で停止してください"
run "-2 0 3.14" red  "赤い箱に近づいて止まれ"
echo done
