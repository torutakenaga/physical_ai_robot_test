# Physical AI 最終課題: 赤い箱へ走って停止する二輪ロボット

ROS 2 Humble + Ignition Gazebo Fortress(Docker、ヘッドレス)上で、カメラ付き差動二輪ロボットが
赤い箱を検出し、箱の手前(約 1m)で停止する。

- **A(完成)**: HSV 色検出 + 固定ルール制御
- **B(完成)**: ローカル LLM(Ollama + Qwen3.5 9B)が指示文と検出結果を読み、粗い指令(前進/左/右/停止)を JSON で出力

## 参照元
- ベースライン: Qiita「ROS2とGazeboの連携によるロボット操作」(N622/9d89f77d85d9da0af29e)。
  差動二輪 + ROS 2 Humble + Ignition Fortress という構成を参考にした。ワールド・ロボット定義・ノードは独自に作成している。
- 使用モデル: Qwen3.5(Ollama 公式レジストリ `qwen3.5:9b`)。同梱のライセンス表示は Apache License 2.0(`ollama show --license` で確認)。
- 使用ソフトウェア: ROS 2 Humble (Apache-2.0), Ignition Gazebo Fortress (Apache-2.0), OpenCV (Apache-2.0), NumPy (BSD)

## 自分で追加した点(ベースラインとの差分)
- ロボットにカメラを追加し、画像を ROS 2 トピックへブリッジ
- 赤い箱の検出(HSV。照明で暗く映る赤でも拾える閾値)
- 検出結果に基づく固定ルール制御(旋回・減速・停止、見失い時の探索)
- 検出・制御を ROS 非依存の純関数に分離(B で制御部だけ LLM に差し替え可能)
- B: 指示文を LLM が解釈(色の切り替え・言い回しの違いに対応)。出力が不正・通信失敗なら安全側の stop にフォールバック
- B: LLM とは独立した非常停止(箱に近すぎたら強制停止)と、距離指標を箱の高さにする工夫
- Docker 内で初期位置を指定して実行し、停止位置を自動計測するスクリプト

## 構成
```
docker/Dockerfile          ROS 2 Humble + Ignition + OpenCV
worlds/red_box.sdf         ロボット(カメラ付き)、赤い箱、青い箱
src/detector/              色検出(純関数)
src/controller/            固定ルール制御(純関数)
src/chase_node.py          A: ROS ノード(画像→検出→固定ルール→/cmd_vel)
src/controller/llm_controller.py  B: プロンプト生成・出力検証・Ollama 呼び出し
src/llm_node.py            B: ROS ノード(画像→検出→LLM→/cmd_vel)
tests/eval_llm.py          LLM の判断精度を正解ラベル付きで評価
scripts/run_scenario.sh    初期位置を指定して実行
```

## 起動手順
前提: Docker Desktop(Apple Silicon の Mac で確認)。

```bash
docker build -t pai-final:humble -f docker/Dockerfile docker
scripts/run_scenario.sh 0 0 0 red      # x y yaw[rad] 目標色
```
`RESULT success=True` と、停止位置・箱までの距離が表示される。

B(LLM 版)は Mac 側で Ollama を起動し、モデルを取得してから実行する:
```bash
brew install ollama && brew services start ollama
ollama pull qwen3.5:9b                     # 約 6.6GB
MODE=llm INSTRUCTION="青い箱に近づいて止まれ" scripts/run_scenario.sh 0 0 0 blue
scripts/run_b_suite.sh                     # 4 ケースの一括確認
```
結果: `docs/A_results.md`、`docs/B_results.md`
