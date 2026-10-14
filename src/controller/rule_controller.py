"""固定ルール制御(ROS 非依存の純関数)。(linear, angular, done) を返す。"""
from src.detector.color_detector import Detection

STOP_WIDTH_PX = 95   # 幅がこれ以上なら「手前」とみなして停止(約 1m)
SLOW_WIDTH_PX = 60
SEARCH_ANGULAR = 0.5
KP_ANGULAR = 1.2


def decide(det: Detection, stop_width: int = STOP_WIDTH_PX):
    if not det.found:
        return 0.0, SEARCH_ANGULAR, False          # 見失ったらその場で探索
    if det.width_px >= stop_width:
        return 0.0, 0.0, True                      # 到達: 停止
    ang = -KP_ANGULAR * det.offset                 # 箱が右(+)なら右旋回(負)
    lin = 0.5 * max(0.0, 1.0 - abs(det.offset) * 1.5)
    if det.width_px >= SLOW_WIDTH_PX:
        lin = min(lin, 0.25)                       # 近づいたら減速
    return lin, ang, False
