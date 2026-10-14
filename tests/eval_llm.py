"""LLM の判断精度を、正解ラベル付きの観測でオフライン評価する。
使い方: python3 -I -m tests.eval_llm [model]   (Mac 側で Ollama が動いていること)"""
import os
import sys
from src.controller import llm_controller as L
from src.detector.color_detector import Detection

def D(pos, dist):
    if pos is None:
        return Detection(False)
    off = {"左": -0.6, "中央": 0.0, "右": 0.6}[pos]
    w = {"遠い": 30, "中": 75, "到達": 100}[dist]
    return Detection(True, off, w, 0, w)

CASES = [  # (指示, red, blue, 正解)
    ("赤い箱に近づいて止まれ", D("右", "遠い"), D("左", "遠い"), "right"),
    ("赤い箱に近づいて止まれ", D("左", "遠い"), D("右", "遠い"), "left"),
    ("赤い箱に近づいて止まれ", D("中央", "遠い"), D(None, None), "forward"),
    ("赤い箱に近づいて止まれ", D("中央", "中"), D("左", "到達"), "forward"),
    ("赤い箱に近づいて止まれ", D("中央", "到達"), D(None, None), "stop"),
    ("赤い箱に近づいて止まれ", D(None, None), D("中央", "遠い"), "left"),
    ("青い箱に近づいて止まれ", D("中央", "遠い"), D(None, None), "left"),
    ("青い箱に近づいて止まれ", D("中央", "到達"), D("右", "遠い"), "right"),
    ("青い箱の手前で止まれ", D("左", "遠い"), D("中央", "到達"), "stop"),
    ("青い箱の手前で止まれ", D("中央", "遠い"), D("左", "中"), "left"),
    ("青い箱の手前で止まれ", D("右", "遠い"), D("中央", "遠い"), "forward"),
    ("青い箱に近づいて止まれ", D("中央", "遠い"), D("右", "到達"), "stop"),
    ("赤い箱に近づいて止まれ", D("左", "到達"), D("中央", "遠い"), "stop"),
    ("赤い箱の手前で停止して", D("中央", "中"), D("中央", "到達"), "forward"),
]

CASES += [  # 実機で見つかった失敗パターン(再発防止)
    ("青い箱に近づいて止まれ", D("中央", "遠い"), D("右", "遠い"), "right"),
    ("青い箱に近づいて止まれ", D("中央", "遠い"), D("左", "遠い"), "left"),
    ("青い箱に近づいて止まれ", D(None, None), D(None, None), "left"),
    ("赤い箱に近づいて止まれ", D(None, None), D(None, None), "left"),
    ("青い箱に近づいて止まれ", D("右", "遠い"), D("中央", "遠い"), "forward"),
]
CASES += [  # 動画の素材で見つかった誤り(目標が少しずれていて距離が「中」)
    ("青い箱に近づいて止まれ", D(None, None), D("左", "中"), "left"),
    ("赤い箱に近づいて止まれ", D(None, None), D("右", "中"), "left"),   # 目標(赤)が見えない→探索
    ("赤い箱に近づいて止まれ", D("左", "中"), D(None, None), "left"),
    ("青い箱に近づいて止まれ", D(None, None), D("右", "中"), "right"),
]
CASES += [  # 最終確認で見つかった失敗(目標が見えない×「停止」を含む言い回し)
    ("青いボックスへ向かって、手前で停止してください", D(None, None), D(None, None), "left"),
    ("赤い箱まで進んで止まる", D(None, None), D(None, None), "left"),
    ("青い箱に近づいて止まれ", D(None, None), D(None, None), "left"),
]
HELDOUT = [  # プロンプトの例とは別の言い回し(汎化の確認用)
    ("赤色の箱のところまで行って、着いたら止まって", D("右", "中"), D("左", "遠い"), "right"),
    ("青いボックスへ向かって、手前で停止してください", D("左", "遠い"), D("左", "遠い"), "left"),
    ("赤い箱まで進んで止まる", D("中央", "遠い"), D("右", "中"), "forward"),
    ("青い箱に到着したら止まれ", D("右", "遠い"), D("中央", "到達"), "stop"),
    ("赤いのに近づいて", D(None, None), D("中央", "遠い"), "left"),
    ("青色の箱を目指して前進、近くで止まって", D("中央", "中"), D("中央", "中"), "forward"),
]
CASES += HELDOUT


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3.5:9b"
    url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
    L.ask_ollama("OK と答えて", url, model, timeout=180.0)   # ウォームアップ(モデルのロード待ちを除く)
    ok = 0
    for ins, r, b, want in CASES:
        got, fb = L.decide(ins, {"red": r, "blue": b}, os.environ.get("OLLAMA_URL", "http://localhost:11434"), model)
        ok += got == want
        print(("OK " if got == want else "NG "), ins, "| red", L.describe(r), "| blue", L.describe(b), "->", got, "(want", want + ")", "FALLBACK" if fb else "")
    print(f"accuracy {ok}/{len(CASES)}")

main()
