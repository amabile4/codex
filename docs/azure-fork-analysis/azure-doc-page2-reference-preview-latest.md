# Azure Doc Page 2: REST API v1 Preview Reference

- 取得日: 2026-04-25
- URL: https://learn.microsoft.com/en-us/azure/foundry/openai/reference-preview-latest

## 概要

Azure OpenAI in Microsoft Foundry Models REST API v1 preview の公式リファレンス。
新しい v1 preview API リリースについての詳細。

## api-version 仕様（最重要）

### api-version パラメータ

| 項目 | 値 |
|---|---|
| パラメータ名 | `api-version` |
| 場所 | query |
| **必須** | **No** |
| 説明 | "The explicit Microsoft Foundry Models API version to use for this request. **v1 if not otherwise specified.**" |

**重要**: `api-version` は v1 preview API では **省略可能**。省略時は `v1` がデフォルト。

### エンドポイント形式

すべてのエンドポイントが以下の形式を使用:

```
POST {endpoint}/openai/v1/responses?api-version=preview
GET  {endpoint}/openai/v1/responses/{response_id}?api-version=preview
DELETE {endpoint}/openai/v1/responses/{response_id}?api-version=preview
GET  {endpoint}/openai/v1/responses/{response_id}/input_items?api-version=preview
```

**endpoint の定義**: `https://{your-resource-name}.openai.azure.com`

### エンドポイント一覧（抜粋）

| API | メソッド | パス |
|---|---|---|
| Create speech | POST | `/openai/v1/audio/speech?api-version=preview` |
| Create transcription | POST | `/openai/v1/audio/transcriptions?api-version=preview` |
| Create translation | POST | `/openai/v1/audio/translations?api-version=preview` |
| Create chat completion | POST | `/openai/v1/chat/completions?api-version=preview` |
| Create embedding | POST | `/openai/v1/embeddings?api-version=preview` |
| **Create response** | **POST** | **`/openai/v1/responses?api-version=preview`** |
| **Get response** | **GET** | **`/openai/v1/responses/{response_id}?api-version=preview`** |
| **Delete response** | **DELETE** | **`/openai/v1/responses/{response_id}?api-version=preview`** |
| **List input items** | **GET** | **`/openai/v1/responses/{response_id}/input_items?api-version=preview`** |

## 既存curlテスト結果との比較

| パターン | URL | 結果 | 備考 |
|---|---|---|---|
| テスト1a | `/openai/v1/responses` (api-versionなし) | ✅ 200 | api-version省略→デフォルトv1 |
| テスト1b | `/openai/responses?api-version=preview` | ❌ 404 | **`/v1` パスが欠落** |
| テスト1c | `/openai/responses?api-version=2025-04-01-preview` | ✅ 200 | 旧形式（v1パスなし） |
| **MS Learn公式** | **`/openai/v1/responses?api-version=preview`** | **未テスト** | **これが正しい形式** |

### キーの発見

1. **`api-version=preview` は `/openai/v1/` パスと組み合わせて使用するのが正しい形式**
2. テスト1bが404だったのは、`/openai/responses`（`/v1`なし）に `api-version=preview` を指定したため
3. `/openai/v1/responses?api-version=preview` の組み合わせは **未検証**

## 認証

- トークンベース認証推奨
- API キー認証もサポート
- `api-key` ヘッダー または Bearer トークン

## ページ2からの結論

**`api-version=preview` は Azure AI Foundry で有効だが、`/openai/v1/` パスと組み合わせる必要がある。**
既存テストでは `/openai/responses` に `preview` を指定して404だったが、これはパスが間違っていた可能性が高い。
`/openai/v1/responses?api-version=preview` の検証が必要。
