# silent-failure-watch

[English](README.md) | 日本語

無人で動くエージェントパイプラインにおける **偽の成功 (false success)** —
成果物もデータも実行も起きていないのに「完了」と報告する失敗 —
に関する記事シリーズの一次データリポジトリです。

2つのデータセットがあり、どちらも実際の単一マシンのエージェント運用
(WSL2ラップトップ上のcron駆動エージェント、実行1,000件、2026-10-24エクスポート)
で計測したものです。

1. `data/fleet_runs.jsonl` — 実cron実行1,000件の無害化エクスポート
   (ステータス・汎用ジョブ種別・エラー分類・実行時間・スケジュール遅刻)。
   `python3 scripts/analyze_fleet.py` で同じ集計が再現できます。
2. `experiments/inject/` — 小規模な制御グリッド: 4種類の環境故障を玩具タスクに
   注入し、エージェント自身の構造化ステータス報告と、ルールベースの状態検証器
   を突き合わせます。`python3 experiments/inject/run_grid.py` で再現できます。

外部の基準として arXiv:2606.09863 (「From Confident Closing to Silent Failure」、
tau2-bench 9,876軌跡 + AppWorld 1,879軌跡で偽の成功を計測) を引用します。
本リポジトリが付け足すのは、ベンチマークでは取れない2点です:
現実の運用fleetで無人失敗がどう見えるか、そしてエージェントの自己申告が
見落とすものを5行の状態チェックがどこまで捕まえるか。

## 構成

| パス | 内容 |
|---|---|
| `data/fleet_runs.jsonl` | 無害化済み実行レコード1,000件 (fleet数値の元データ) |
| `scripts/analyze_fleet.py` | エクスポートに対する分類・遅刻の集計 |
| `scripts/export_fleet.py` | サイト固有のエクスポータ (非公開のcron DBを読む。マッピングファイルはコミットされない) |
| `scripts/job_type_map.example.json` | サイト固有マッピングの形式例 |
| `experiments/inject/run_grid.py` | 制御された偽成功グリッド |
| `tests/` | 分類器と報告パーサの単体テスト |
| `results/` | グリッドの生実行レコード (実行に使ったモデル名はここだけ) |

## 実行方法

```bash
# fleet集計 (標準ライブラリのみ)
python3 scripts/analyze_fleet.py

# 注入グリッド (任意のOpenAI互換エンドポイント)
export LLM_BASE_URL=...
export LLM_API_KEY=...
export LLM_MODEL=...      # 汎用チャットモデル
python3 experiments/inject/run_grid.py             # 5条件 x 8実行
python3 experiments/inject/run_grid.py --analyze    # 結果JSONLから集計

# テスト
python3 -m pytest tests/ -q
```

グリッドには思考量を制御できるチャットモデルが必要です。デフォルトで
思考が長いモデルは `max_tokens` を思考が食い潰して本文が1文字も出ないことが
あります (実測: 512トークン上限で思考570トークン・本文0、`finish_reason:
length`)。そのため `run_grid.py` は既定で低めの effort を送ります。
使用したモデルとパラメータは `results/` のトレースに記録されます。

## 正直な限界

- fleet実行1,000件は1台・1スケジューラでの事例研究です。エージェント運用全般
  の推定値ではありません。
- 注入グリッドは既知の注入を持つ玩具タスクです。エージェントの能力ではなく、
  故障時の自己申告の信頼性を測ります。
- グリッドの検証器はハーネスが制御する状態を読むため、自明に正しいです。
  それが要点 (安い状態チェックは自己申告に勝つ) ですが、検証器の列は
  デモンストレーションであってベンチマークスコアではありません。

## コントリビュート

再現手順付きのissue報告を歓迎します — 特に注入グリッドへの新しい故障クラス。
条件を追加するPRには、ground truthエントリとパーサテストの追加を合わせてください。

## ライセンス

MIT — [LICENSE](LICENSE) を参照。
