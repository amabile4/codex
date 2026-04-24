# Azure Fork Analysis - ドキュメント一覧

次バージョンのフォーク作成必要性を検討するための調査資料。

## メインドキュメント

| ファイル | 内容 |
|---|---|
| [azure-official-vs-fork-analysis-v0.124.0.md](azure-official-vs-fork-analysis-v0.124.0.md) | **包括的調査報告**（公式バイナリ vs Azureフォークの全比較、curl検証、Python検証、api-version調査結果） |

## 公式ドキュメント要約（api-version調査）

| ファイル | 内容 |
|---|---|
| [azure-doc-page1-models-directly-sold.md](azure-doc-page1-models-directly-sold.md) | MS Learn: Azure直接提供モデル一覧 |
| [azure-doc-page2-reference-preview-latest.md](azure-doc-page2-reference-preview-latest.md) | MS Learn: REST API v1 Preview リファレンス（**api-version=preview の正しい形式**） |
| [azure-doc-page3-codex-config-advanced.md](azure-doc-page3-codex-config-advanced.md) | OpenAI: Codex Config Advanced（**Azure公式推奨設定**） |

## 検証スクリプト

| ファイル | 内容 |
|---|---|
| [azure-cde-repro-test.py](azure-cde-repro-test.py) | C/D/E変更のPython再現テスト（v2: api-version=preview対応） |

## バージョン間差分

| ファイル | 内容 |
|---|---|
| [azure-release-0.118.0-vs-rust-v0.118.0.diff](azure-release-0.118.0-vs-rust-v0.118.0.diff) | v0.118.0 フォーク差分 |
| [azure-release-0.122.0-vs-rust-v0.122.0.diff](azure-release-0.122.0-vs-rust-v0.122.0.diff) | v0.122.0 フォーク差分 |

## フォーク変更の最終判定サマリ

| 変更 | 判定 | 根拠 |
|---|---|---|
| A. `encrypted_content` スキップ | **不要** | Azure APIが受け入れ |
| B. `client_metadata` スキップ | **不要** | Azure APIが受け入れ |
| C. Base64 turn metadata | **必要（テレメトリ）** | 非ASCIIヘッダー欠落 |
| D. 孤立メッセージ除去 | **必要（要確認）** | compaction整合性 |
| E. serde属性変更 | **逆効果の可能性** | id付きがcompactでエラー |

## 推奨設定（api-version）

```toml
# 選択肢1: MS Learn v1 API形式
[model_providers.azure]
base_url = "https://YOUR_PROJECT.services.ai.azure.com/openai/v1"
wire_api = "responses"

# 選択肢2: OpenAI推奨形式
[model_providers.azure]
base_url = "https://YOUR_PROJECT.services.ai.azure.com/openai"
query_params = { api-version = "2025-04-01-preview" }
wire_api = "responses"
```
