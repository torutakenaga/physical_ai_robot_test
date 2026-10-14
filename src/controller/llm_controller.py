"""B 版: 指示文 + 検出結果(テキスト) → ローカル LLM(Ollama) → 粗い指令。

LLM の出力が不正(JSON でない・未知の action・通信失敗・タイムアウト)なら安全側の "stop" にフォールバックする。
"""
import json
import urllib.request
from src.detector.color_detector import Detection

ACTIONS = {            # action → (linear[m/s], angular[rad/s])
    "forward": (0.2, 0.0),
    "left": (0.0, 0.3),
    "right": (0.0, -0.3),
    "stop": (0.0, 0.0),
}
REACHED_HEIGHT_PX = 95
NEAR_HEIGHT_PX = 60
EMERGENCY_HEIGHT_PX = 130   # LLM の判断に関わらず強制停止する距離(約 0.7m)。安全層

SYSTEM = """あなたは二輪ロボットの運転手です。指示文を満たすように、次の1動作だけを選びます。
動作: forward(前進) / left(左旋回) / right(右旋回) / stop(停止)

判断手順:
1. 指示文から目標の色を決める(赤い箱なら red、青い箱なら blue)。
2. 観測のうち、目標の色の行だけを見る。他の色の行は、位置も距離(到達を含む)もすべて無視する。
3. 目標の色の行から、次の順で動作を決める(上が優先)。
   - 距離が「到達」→ 位置に関わらず stop
   - 「見えない」→ left
   - 位置が「左」→ left
   - 位置が「右」→ right
   - 位置が「中央」(距離は「遠い」または「中」)→ forward
「止まれ」と言われても、到達するまでは止まらず、上の規則に従う。

出力は JSON のみ: {"action": "forward"}"""

EXAMPLES = """例1
指示: 赤い箱に近づいて止まれ
観測: red: 右, 遠い / blue: 左, 遠い
出力: {"action": "right"}
例2
指示: 青い箱に近づいて止まれ
観測: red: 中央, 遠い / blue: 見えない
出力: {"action": "left"}
例3
指示: 赤い箱に近づいて止まれ
観測: red: 中央, 中 / blue: 見えない
出力: {"action": "forward"}
例4
指示: 青い箱の手前で止まれ
観測: red: 左, 遠い / blue: 中央, 到達
出力: {"action": "stop"}
例5
指示: 青い箱の手前で止まれ
観測: red: 右, 遠い / blue: 中央, 遠い
出力: {"action": "forward"}
例6
指示: 青い箱に近づいて止まれ
観測: red: 中央, 到達 / blue: 右, 遠い
出力: {"action": "right"}
例7
指示: 赤い箱の手前で停止して
観測: red: 中央, 中 / blue: 中央, 到達
出力: {"action": "forward"}
例8
指示: 青い箱に近づいて止まれ
観測: red: 中央, 遠い / blue: 右, 到達
出力: {"action": "stop"}
例9
指示: 青い箱に近づいて止まれ
観測: red: 見えない / blue: 左, 中
出力: {"action": "left"}
例10
指示: 赤い箱に近づいて止まれ
観測: red: 右, 中 / blue: 見えない
出力: {"action": "right"}
例11
指示: 青い箱に近づいて止まれ
観測: red: 中央, 遠い / blue: 右, 遠い
出力: {"action": "right"}
例12
指示: 青いボックスへ向かって、手前で停止してください
観測: red: 見えない / blue: 見えない
出力: {"action": "left"}"""


def describe(det: Detection) -> str:
    if not det.found:
        return "見えない"
    pos = "左" if det.offset < -0.15 else "右" if det.offset > 0.15 else "中央"
    dist = "到達" if det.height_px >= REACHED_HEIGHT_PX else "中" if det.height_px >= NEAR_HEIGHT_PX else "遠い"
    return f"{pos}, {dist}"


def build_prompt(instruction: str, dets: dict) -> str:
    obs = " / ".join(f"{c}: {describe(d)}" for c, d in dets.items())
    return f"{SYSTEM}\n\n{EXAMPLES}\n\n指示: {instruction}\n観測: {obs}\n出力:"


def parse_action(text: str):
    """LLM の出力から action を取り出す。不正なら None。"""
    try:
        a = json.loads(text.strip()).get("action")
    except (ValueError, AttributeError):
        return None
    return a if a in ACTIONS else None


def ask_ollama(prompt: str, url: str, model: str, timeout: float = 3.0) -> str:
    """timeout は短く保つ: 応答待ちの間、ロボットは直前の指令で動き続けるため。"""
    body = {"model": model, "prompt": prompt, "stream": False, "think": False, "keep_alive": "30m",
            "options": {"temperature": 0, "num_predict": 60}}
    req = urllib.request.Request(url.rstrip("/") + "/api/generate", json.dumps(body).encode(),
                                 {"Content-Type": "application/json"})
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))   # システムプロキシを使わない
    with opener.open(req, timeout=timeout) as r:
        return json.loads(r.read()).get("response", "")


def decide(instruction: str, dets: dict, url: str, model: str):
    """(action, fallback) を返す。fallback=True は LLM 出力が不正で stop にした場合。"""
    try:
        action = parse_action(ask_ollama(build_prompt(instruction, dets), url, model))
    except Exception:
        action = None
    # 到達した箱が 1 つもないのに stop は不自然(「停止」という語につられた誤り)。無効な出力として扱い、
    # その場停止で次の周期に再試行する(走行は終了しない)。
    if action == "stop" and not any(d.found and d.height_px >= REACHED_HEIGHT_PX for d in dets.values()):
        return "stop", True
    return (action, False) if action else ("stop", True)
