# だんごボーダー — Border Analysis API（MVP）

生データ（Excel/CSV）をアップロードし、任意ターゲットの学習・推論を行うバックエンド API です。

## 前提

- Python 3.11+ 推奨
- 作業ディレクトリ: リポジトリルート（`raw-data.xlsx` がある場所）

## 1. セットアップ

```powershell
cd C:\Users\furup\Documents\border-analysis
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

社内プロキシ等で `pip install` が SSL エラーになる場合:

```powershell
python -m pip install -r requirements.txt --trusted-host pypi.org --trusted-host files.pythonhosted.org
```

## 2. API 起動

```powershell
.\scripts\start-api.ps1
```

または:

```powershell
.\.venv\Scripts\Activate.ps1
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- ヘルスチェック: http://127.0.0.1:8000/health
- **予測UI**: http://127.0.0.1:8000/ui/
- **データ投入UI**: http://127.0.0.1:8000/ui/admin.html
- **ターゲット運用UI**: http://127.0.0.1:8000/ui/targets.html
- OpenAPI: http://127.0.0.1:8000/docs

## 3. M1 検証フロー（curl）

別ターミナルで実行してください。PowerShell の例です。

### 3.1 データアップロード

```powershell
curl.exe -X POST "http://127.0.0.1:8000/datasets/upload" `
  -F "file=@raw-data.xlsx"
```

レスポンスの `job_id` を控えます。

### 3.2 ジョブ状態確認（完了まで数秒待つ）

```powershell
$jobId = "<job_id>"
curl.exe "http://127.0.0.1:8000/datasets/jobs/$jobId"
```

- `status`: `completed`
- `stage`: `quality_gate_passed` または `quality_gate_failed`
- `pipeline_blocked`: `false` なら学習可能

品質ゲート失敗時の手動解除:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/datasets/jobs/$jobId/quality-gate/override" `
  -H "Content-Type: application/json" `
  -d "{\"reason\":\"manual review passed\"}"
```

### 3.3 ターゲット一覧

```powershell
curl.exe "http://127.0.0.1:8000/datasets/targets"
```

`publish: true` かつ `status: ready` のターゲットが M1 の主対象です。

### 3.4 学習（単体）

```powershell
curl.exe -X POST "http://127.0.0.1:8000/models/train?target=S1%20%2B6&strategy=auto&feature_profile=auto_steps"
```

- `strategy`: `auto`（線形 vs LightGBM をCVで比較） / `linear` / `lightgbm`
- `feature_profile`: `auto_steps`（step1→step3をCV採用、未達時sparse） / `step1` / `step2` / `step3` / `sparse` / `full`（=step3）
- 予測区間は CV 残差の分位点（新規学習モデル）。旧 artifact は RMSE 近似にフォールバック
- `adopted: true` のときのみレジストリで `active` になります
- `improvement_rate` がベースライン比改善率（10%以上で採用）

戦略比較（開発用）:

```powershell
.\scripts\compare-strategies.ps1
```

一括学習:

```powershell
curl.exe -X POST "http://127.0.0.1:8000/models/train-all"
```

### 3.5 現行モデル確認

```powershell
curl.exe "http://127.0.0.1:8000/models/current?target=S1%20%2B6"
```

### 3.6 推論

ラグ特徴量が計算できる日付を指定してください（データ末尾付近が安全です）。

```powershell
curl.exe "http://127.0.0.1:8000/predictions?target=S1%20%2B6&date=2026-02-26"
```

## 4. ターゲット状況レポート（自分運用向け）

```powershell
.\scripts\report-targets.ps1
```

各ターゲットの `publish` / `active` / **予測可能日範囲** を一覧表示します。

未採用ターゲットを sparse 特徴量で再学習:

```powershell
.\scripts\retry-not-adopted.ps1
```

## 5. ready ターゲット一括学習

API 起動後:

```powershell
.\scripts\train-ready.ps1
```

`adopted` 件数が推論可能な active モデル数です。

## 6. 一括検証スクリプト

API 起動後に:

```powershell
.\scripts\verify-m1.ps1
```

`raw-data.xlsx` のアップロードから推論までを自動で試します。

## 7. 主要エンドポイント一覧

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/health` | 死活監視 |
| POST | `/datasets/upload` | データ投入 |
| GET | `/datasets/jobs/{job_id}` | ジョブ状態 |
| GET | `/datasets/targets` | ターゲット台帳 |
| PATCH | `/datasets/targets/{target}/publish` | 公開切替 |
| POST | `/models/train` | 単体学習 |
| POST | `/models/train-all` | 一括学習 |
| GET | `/models/current` | active モデル |
| GET | `/models/versions` | バージョン一覧 |
| POST | `/models/activate` | active 切替 |
| POST | `/models/rollback` | ロールバック |
| GET | `/predictions` | 単日推論 |
| GET | `/predictions/range` | 期間推論（最大90日） |
| GET | `/datasets/targets/operations` | 運用向けターゲット一覧 |
| GET | `/system/metrics` | カウンタ・精度サマリ |
| GET | `/system/audit` | 監査ログ（末尾） |
| POST | `/system/monitoring/reconcile` | 予測ログと実績の突合 |
| GET | `/datasets/publication/plan` | 段階公開の進捗（目標39） |
| GET | `/datasets/publication/candidates` | beta 公開候補 |
| POST | `/datasets/publication/promote-batch` | eligible beta を一括公開 |
| POST | `/datasets/publication/train-beta` | beta 全件学習 |

## 8. ストレージ構成

```
storage/
  uploads/          # 原本
  jobs/             # ジョブメタ・正規化CSV
  targets.json      # ターゲット台帳
  model_versions.json
  models/           # 学習 artifact
  audit/audit.log   # 監査ログ
```

## 9. トラブルシュート

| 症状 | 対処 |
|------|------|
| `No normalized dataset found` | 先に upload → job completed を確認 |
| `No active model` | `POST /models/train` を実行し `adopted: true` を確認 |
| `Target is not published` | `PATCH .../publish` で公開する |
| 推論が 400 | UI の日付範囲内を選ぶ（`GET /datasets/targets/{target}/prediction-range`） |
| `Cannot build features` | 範囲外の日付。未来日本格対応は計画の後半 |

## 10. 開発ロードマップ

詳細は `開発手順.md` を参照。

- 完了: Epic A、B-1/B-2、C-1〜C-3、D-1、D-2（最小UI）
- 次: B-3（本格管理 UI）、E（SLO/監視）、Next.js 化（任意）
