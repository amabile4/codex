# OpenAI Codex Config Advanced: Azure Provider

- 取得日: 2026-04-25
- URL: https://developers.openai.com/codex/config-advanced

## 概要

OpenAI Codex CLI の高度な設定に関する公式ドキュメント。
`model_providers` の設定方法、Azure プロバイダの具体的設定例を含む。

## Azure Provider 設定（公式推奨）

### 公式設定例

```toml
[model_providers.azure]
name = "Azure"
base_url = "https://YOUR_PROJECT_NAME.openai.azure.com/openai"
env_key = "AZURE_OPENAI_API_KEY"
query_params = { api-version = "2025-04-01-preview" }
wire_api = "responses"
request_max_retries = 4
stream_max_retries = 10
stream_idle_timeout_ms = 300000
```

### 重要な設定値

| パラメータ | 公式推奨値 | 備考 |
|---|---|---|
| `base_url` | `https://YOUR_PROJECT_NAME.openai.azure.com/openai` | **`/v1` なし** |
| `query_params` | `{ api-version = "2025-04-01-preview" }` | **日付形式のpreview** |
| `wire_api` | `"responses"` | Responses API 使用 |

### URL構築の推定

Codex が `wire_api = "responses"` でURLを構築する場合:

```
base_url + /v1/responses + ?api-version=2025-04-01-preview
= https://YOUR_PROJECT_NAME.openai.azure.com/openai/v1/responses?api-version=2025-04-01-preview
```

**注意**: これは推定。実際のURL構築は `is_azure_responses_endpoint()` の検出結果により異なる可能性あり。

## 他のプロバイダ設定例

### Ollama

```toml
[model_providers.local_ollama]
name = "Ollama"
base_url = "http://localhost:11434/v1"
```

### Mistral

```toml
[model_providers.mistral]
name = "Mistral"
base_url = "https://api.mistral.ai/v1"
env_key = "MISTRAL_API_KEY"
```

### Command-backed Authentication

```toml
[model_providers.proxy.auth]
command = "/usr/local/bin/fetch-codex-token"
args = ["--audience", "codex"]
timeout_ms = 5000
refresh_interval_ms = 300000
```

## 注意事項

- `model_providers.openai` は予約済みID。オーバーライド不可
- 代わりに `openai_base_url` を使用して組み込みOpenAIプロバイダのbase URLを変更
- `http_headers` と `env_http_headers` でカスタムヘッダー追加可能

## ページ3からの結論

OpenAI公式ドキュメントは `api-version = "2025-04-01-preview"` （日付形式）を推奨。
`api-version = "preview"` （文字列のみ）は公式に推奨されていない。
`base_url` は `/openai` まで（`/v1` なし）とし、Codexがパスを構築する設計。
