#!/usr/bin/env bash
# 使い方: scripts/run_scenario.sh <x> <y> <yaw_rad> [color]
#   A(固定ルール): scripts/run_scenario.sh 0 0 0 red
#   B(LLM)      : MODE=llm INSTRUCTION="青い箱に近づいて止まれ" scripts/run_scenario.sh 0 0 0 blue
#   記録(動画の素材): REC_DIR=/ws/out/run_red MODE=llm ... (リポジトリの out/ に出力)
#   (color は最終距離の計測対象。B では OLLAMA_MODEL / OLLAMA_URL で上書き可)
# 初期位置を指定して Docker 内で Gazebo(ヘッドレス)+ chase_node を実行し、最終位置と箱までの距離を表示する。
set -euo pipefail
X=${1:-0}; Y=${2:-0}; YAW=${3:-0}; COLOR=${4:-red}
MODE=${MODE:-rule}; INSTRUCTION=${INSTRUCTION:-赤い箱に近づいて止まれ}
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
docker run --rm -v "$ROOT":/ws -e X="$X" -e Y="$Y" -e YAW="$YAW" -e COLOR="$COLOR" -e REC_DIR="${REC_DIR:-}" -e RUN_TIMEOUT="${RUN_TIMEOUT:-120}" -e MODE="$MODE" -e INSTRUCTION="$INSTRUCTION" -e OLLAMA_URL="${OLLAMA_URL:-http://host.docker.internal:11434}" -e OLLAMA_MODEL="${OLLAMA_MODEL:-qwen3.5:9b}" pai-final:humble bash -c '
source /opt/ros/humble/setup.bash
sed "s|<pose>0 0 0.1 0 0 0</pose>|<pose>$X $Y 0.1 0 0 $YAW</pose>|" /ws/worlds/red_box.sdf > /tmp/world.sdf
(xvfb-run -a ign gazebo -s -r --headless-rendering /tmp/world.sdf > /tmp/gz.log 2>&1 &)
sleep 15
(ros2 run ros_ign_bridge parameter_bridge \
   /camera/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image \
   /odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry \
   /cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist > /tmp/br.log 2>&1 &)
sleep 3
cd /ws
if [ "$MODE" = llm ]; then python3 -m src.llm_node "$INSTRUCTION" "$RUN_TIMEOUT" || true
else python3 -m src.chase_node "$COLOR" 90 || true; fi
sleep 1
ign topic -e -n 1 -t /world/red_box_world/pose/info > /tmp/pose.txt 2>/dev/null
python3 - <<PY
import re, math
t = open("/tmp/pose.txt").read()
def pos(name):
    m = re.search(r"name: \"%s\"\n(?:.*\n)*?  position \{\n((?:    .*\n)*)  \}" % name, t)
    d = dict(re.findall(r"(\w): ([-\d.e]+)", m.group(1))) if m else {}
    return float(d.get("x", 0)), float(d.get("y", 0))
r = pos("robot"); b = pos("red_box" if "$COLOR" == "red" else "blue_box")
print("FINAL robot=(%.2f, %.2f) dist_to_box_center=%.2f m" % (r[0], r[1], math.dist(r, b)))
PY'
