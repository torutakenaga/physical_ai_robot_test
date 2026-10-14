"""B 版: 指示文 + カメラの検出結果 → Ollama(LLM) → 粗い指令 → /cmd_vel。
LLM が(正常な出力で)stop を返したら終了。出力が不正なら stop にフォールバックし、次の周期で再試行する。
使い方: python3 -m src.llm_node "<指示文>" [timeout_s]   環境変数 OLLAMA_URL / OLLAMA_MODEL"""
import json
import math
import os
import sys
import time
import cv2
import numpy as np
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from src.detector.color_detector import detect
from src.controller import llm_controller as L


class LlmNode(Node):
    def __init__(self):
        super().__init__("llm_node")
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Image, "/camera/image_raw", self.on_image, 1)
        self.create_subscription(Odometry, "/odom", self.on_odom, 10)
        self.latest, self.odom = None, (0.0, 0.0, 0.0)

    def on_odom(self, msg: Odometry):
        q = msg.pose.pose.orientation
        yaw = math.atan2(2 * (q.w * q.z + q.x * q.y), 1 - 2 * (q.y * q.y + q.z * q.z))
        self.odom = (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def world_pose(self):
        """odom(出発点が原点)を、開始位置 X,Y,YAW を使ってワールド座標に直す。"""
        x0, y0, yaw0 = (float(os.environ.get(k, 0)) for k in ("X", "Y", "YAW"))
        ox, oy, oyaw = self.odom
        c, s = math.cos(yaw0), math.sin(yaw0)
        return x0 + c * ox - s * oy, y0 + s * ox + c * oy, yaw0 + oyaw

    def on_image(self, msg: Image):
        self.latest = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, 3)

    def send(self, action: str):
        lin, ang = L.ACTIONS[action]
        t = Twist()
        t.linear.x, t.angular.z = float(lin), float(ang)
        self.pub.publish(t)

    def fresh_image(self, wait=3.0):
        self.latest = None
        end = time.time() + wait
        while self.latest is None and time.time() < end:
            rclpy.spin_once(self, timeout_sec=0.2)
        return self.latest


def main():
    instruction = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 120.0
    url = os.environ.get("OLLAMA_URL", "http://host.docker.internal:11434")
    model = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
    try:   # ウォームアップ(モデルのロード待ちで走行中に遅延しないよう、動く前に済ませる)
        L.ask_ollama("OK と答えて", url, model, timeout=180.0)
    except Exception as e:
        print(f"warmup failed: {e}", flush=True)
    rclpy.init()
    node = LlmNode()
    rec_dir = os.environ.get("REC_DIR")           # 指定時は各ステップを記録(動画の素材)
    rec = None
    if rec_dir:
        os.makedirs(rec_dir + "/frames", exist_ok=True)
        rec = open(rec_dir + "/steps.jsonl", "w")
    t0 = time.time()
    deadline, steps, fallbacks, reached, emergency = time.time() + timeout, 0, 0, False, False
    while rclpy.ok() and time.time() < deadline:
        img = node.fresh_image()
        if img is None:
            continue
        dets = {c: detect(img, c) for c in ("red", "blue")}
        if any(d.found and d.height_px >= L.EMERGENCY_HEIGHT_PX for d in dets.values()):
            print("EMERGENCY STOP (too close)", flush=True)   # 安全層: LLM を呼ばず停止
            emergency = True
            break
        action, fb = L.decide(instruction, dets, url, model)
        steps += 1
        fallbacks += fb
        raw = " ".join(f"{c}[h={d.height_px} w={d.width_px} off={d.offset:+.2f}]" for c, d in dets.items() if d.found)
        print(f"step {steps}: {L.build_prompt(instruction, dets).splitlines()[-2]} -> {action}{' (FALLBACK)' if fb else ''}  {raw}", flush=True)
        node.send(action)
        if rec:
            x, y, yaw = node.world_pose()
            cv2.imwrite(f"{rec_dir}/frames/{steps:04d}.jpg", cv2.cvtColor(img, cv2.COLOR_RGB2BGR))
            rec.write(json.dumps({
                "step": steps, "t": round(time.time() - t0, 2), "instruction": instruction,
                "obs": L.build_prompt(instruction, dets).splitlines()[-2], "action": action, "fallback": fb,
                "dets": {c: {"found": d.found, "h": d.height_px, "w": d.width_px, "cx": d.cx,
                             "off": round(d.offset, 3)} for c, d in dets.items()},
                "pose": [round(x, 3), round(y, 3), round(yaw, 3)]}, ensure_ascii=False) + "\n")
            rec.flush()
        if action == "stop" and not fb:
            reached = True
            break
    for _ in range(5):
        node.send("stop")
    print(f"RESULT success={reached} steps={steps} fallbacks={fallbacks} emergency={emergency}", flush=True)
    rclpy.shutdown()
    sys.exit(0 if reached else 1)


if __name__ == "__main__":
    main()
