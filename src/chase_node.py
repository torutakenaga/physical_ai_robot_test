"""A 版: カメラ画像 → 色検出 → 固定ルール → /cmd_vel。目標に着いたら停止して終了。"""
import sys
import time
import numpy as np
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from geometry_msgs.msg import Twist
from src.detector.color_detector import detect
from src.controller.rule_controller import decide


class ChaseNode(Node):
    def __init__(self, color: str, timeout: float):
        super().__init__("chase_node")
        self.color, self.deadline = color, time.time() + timeout
        self.done, self.success, self.last_width = False, False, 0
        self.pub = self.create_publisher(Twist, "/cmd_vel", 10)
        self.create_subscription(Image, "/camera/image_raw", self.on_image, 1)

    def send(self, lin, ang):
        t = Twist()
        t.linear.x, t.angular.z = float(lin), float(ang)
        self.pub.publish(t)

    def on_image(self, msg: Image):
        if self.done:
            return
        img = np.frombuffer(msg.data, np.uint8).reshape(msg.height, msg.width, 3)
        det = detect(img, self.color)
        self.last_width = det.width_px
        lin, ang, reached = decide(det)
        if reached or time.time() > self.deadline:
            self.success = reached
            self.done = True
            for _ in range(5):
                self.send(0.0, 0.0)
            return
        self.send(lin, ang)


def main():
    color = sys.argv[1] if len(sys.argv) > 1 else "red"
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
    rclpy.init()
    node = ChaseNode(color, timeout)
    while rclpy.ok() and not node.done:
        rclpy.spin_once(node, timeout_sec=0.5)
        if time.time() > node.deadline:   # 画像が来ない場合もここで打ち切る
            node.done = True
            for _ in range(5):
                node.send(0.0, 0.0)
    print(f"RESULT success={node.success} width_px={node.last_width}", flush=True)
    rclpy.shutdown()
    sys.exit(0 if node.success else 1)


if __name__ == "__main__":
    main()
