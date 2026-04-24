# Azure Codex 0.124.0: 公式バイナリ vs Azureフォーク 比較調査報告

- 調査日: 2026-04-24
- 対象リポジトリ: `git@github.com:amabile4/codex.git` (fork of `https://github.com/openai/codex.git`)
- 比較対象タグ: `rust-v0.124.0` (upstream) vs `azure/release-0.124.0` (fork)
- Azureエンドポイント: `https://ram4-for-codex.services.ai.azure.com/openai/v1` (Azure AI Foundry)

---

## 1. 調査目的

以下3パターンの構成で、①で問題が発生するが③で解消するケースのうち、②（設定変更のみ）でも解消するものを特定する。

| パターン | バイナリ | 設定 |
|---|---|---|
| ① MS Learn推奨 | 公式 0.124.0 | `base_url=".../openai/v1"`, `wire_api="responses"`, api-versionなし |
| ② 設定変更 | 公式 0.124.0 | ①に加え `query_params={api-version="preview"}` |
| ③ Azureフォーク | フォーク 0.124.0 | フォーク独自の5箇所のコード変更を含む |

---

## 2. 使用設定（config.toml）

```toml
# C:\Users\ram\.codex\config.toml
model = "gpt-5.4"
model_reasoning_effort = "medium"

[model_providers.azure]
name = "Azure OpenAI"
base_url = "https://ram4-for-codex.services.ai.azure.com/openai/v1"
env_key = "AZURE_OPENAI_API_KEY"
wire_api = "responses"

[profiles.azure_foundry]
model = "gpt-5.1-codex-mini"
model_provider = "azure"
approval_policy = "never"
model_reasoning_effort = "medium"
```

---

## 3. フォーク(③)のコード変更（git diff 証跡）

### 3.1 変更ファイル一覧

```
$ git diff rust-v0.124.0..azure/release-0.124.0 --stat

 .github/workflows/build-and-release.yml            |   68 +
 .github/workflows/close-stale-contributor-prs.yml  |    3 +-
 .github/workflows/rust-release-prepare.yml         |    3 +-
 .github/workflows/rust-release.yml                 |    6 +-
 codex-rs/Cargo.lock                                |  204 +--
 codex-rs/core/src/client.rs                        |   25 +-
 codex-rs/core/src/client_tests.rs                  |   39 +-
 codex-rs/core/src/compact_remote.rs                |   27 +
 codex-rs/core/src/compact_tests.rs                 |   58 +
 codex-rs/core/src/context_manager/normalize.rs     |   17 +
 codex-rs/core/src/mcp_tool_call_tests.rs           |   19 +-
 codex-rs/core/src/turn_metadata.rs                 |   21 +-
 codex-rs/core/src/turn_metadata_tests.rs           |   21 +-
 codex-rs/core/tests/responses_headers.rs           |   38 +-
 codex-rs/core/tests/suite/client_websockets.rs     |   37 +-
 codex-rs/core/tests/suite/turn_state.rs            |   11 +-
 codex-rs/protocol/src/models.rs                    |   17 +
 18 files changed, 2107 insertions(+), 169 deletions(-)
```

### 3.2 上流0.124.0に既に含まれるAzure対応（フォーク不要）

以下は `rust-v0.124.0` タグの時点で既に上流に存在するコード。フォーク固有の変更ではない。

**store=true for Azure** (`codex-rs/core/src/client.rs` L887):

```rust
// upstream rust-v0.124.0 のコード（既に存在）
store: provider.is_azure_responses_endpoint(),
```

**Azure検出関数** (`codex-rs/codex-api/src/provider.rs` L88-127):

```rust
// upstream rust-v0.124.0 のコード（既に存在）
pub fn is_azure_responses_endpoint(&self) -> bool {
    is_azure_responses_provider(&self.name, Some(&self.base_url))
}

pub fn is_azure_responses_provider(name: &str, base_url: Option<&str>) -> bool {
    if name.eq_ignore_ascii_case("azure") {
        true
    } else if let Some(base_url) = base_url {
        matches_azure_responses_base_url(base_url)
    } else {
        false
    }
}

fn matches_azure_responses_base_url(base_url: &str) -> bool {
    let base_url = base_url.to_ascii_lowercase();
    const AZURE_MARKERS: [&str; 6] = [
        "openai.azure.",
        "cognitiveservices.azure.",
        "aoai.azure.",
        "azure-api.",
        "azurefd.",
        "windows.net/openai",
    ];
    AZURE_MARKERS.iter().any(|marker| base_url.contains(marker))
}
```

**注意**: `services.ai.azure.com`（Azure AI Foundry）は6つのAZURE_MARKERSのいずれにもマッチしない。ただし `model_provider = "azure"` により name="azure" となるため、`is_azure_responses_provider()` は `true` を返す（name のcase-insensitive一致が先に評価されるため）。

### 3.3 フォーク固有の変更 A: reasoning.encrypted_content のスキップ

**ファイル**: `codex-rs/core/src/client.rs` L851

```diff
-        let include = if reasoning.is_some() {
+        let include = if reasoning.is_some() && !provider.is_azure_responses_endpoint() {
             vec!["reasoning.encrypted_content".to_string()]
         } else {
             Vec::new()
         };
```

### 3.4 フォーク固有の変更 B: client_metadata のスキップ

**ファイル**: `codex-rs/core/src/client.rs` L894-902

```diff
-            client_metadata: Some(HashMap::from([(
-                X_CODEX_INSTALLATION_ID_HEADER.to_string(),
-                self.client.state.installation_id.clone(),
-            )])),
+            client_metadata: if !provider.is_azure_responses_endpoint() {
+                Some(HashMap::from([(
+                    X_CODEX_INSTALLATION_ID_HEADER.to_string(),
+                    self.client.state.installation_id.clone(),
+                )]))
+            } else {
+                None
+            },
```

### 3.5 フォーク固有の変更 C: turn metadata の Base64 エンコード

**ファイル**: `codex-rs/core/src/turn_metadata.rs` L69-78

```diff
     fn to_header_value(&self) -> Option<String> {
-        serde_json::to_string(self).ok()
+        // Azure fork: encode turn metadata as Base64 so HTTP headers stay ASCII-safe.
+        use base64::prelude::*;
+
+        serde_json::to_string(self)
+            .ok()
+            .map(|json| BASE64_STANDARD.encode(json))
     }
```

**merge関数もBase64対応** (`codex-rs/core/src/turn_metadata.rs` L82-99):

```diff
 fn merge_responsesapi_client_metadata(
     header: &str,
     responsesapi_client_metadata: Option<&HashMap<String, String>>,
 ) -> Option<String> {
+    use base64::prelude::*;
+
     let responsesapi_client_metadata = responsesapi_client_metadata?;
-    let mut metadata = serde_json::from_str::<serde_json::Map<String, Value>>(header).ok()?;
+    let decoded = BASE64_STANDARD.decode(header).ok()?;
+    let mut metadata = serde_json::from_slice::<serde_json::Map<String, Value>>(&decoded).ok()?;
     for (key, value) in responsesapi_client_metadata {
         metadata
             .entry(key.clone())
             .or_insert_with(|| Value::String(value.clone()));
     }
-    serde_json::to_string(&metadata).ok()
+    serde_json::to_string(&metadata)
+        .ok()
+        .map(|json| BASE64_STANDARD.encode(json))
 }
```

**parse_turn_metadata_header もBase64検証** (`codex-rs/core/src/client.rs` L1558-1568):

```diff
-/// Parses per-turn metadata into an HTTP header value.
+/// Parses the already-encoded per-turn metadata into an HTTP header value.
 ///
 /// Invalid values are treated as absent so callers can compare and propagate
-/// metadata with the same sanitization path used when constructing headers.
+/// metadata with the same Base64 sanitization path used when constructing
+/// headers.
 fn parse_turn_metadata_header(turn_metadata_header: Option<&str>) -> Option<HeaderValue> {
-    turn_metadata_header.and_then(|value| HeaderValue::from_str(value).ok())
+    use base64::prelude::*;
+
+    turn_metadata_header
+        .filter(|value| BASE64_STANDARD.decode(value).is_ok())
+        .and_then(|value| HeaderValue::from_str(value).ok())
 }
```

### 3.6 フォーク固有の変更 D: compaction時の孤立メッセージ除去

**ファイル**: `codex-rs/core/src/compact_remote.rs` L254-284

```diff
     compacted_history.retain(should_keep_compacted_history_item);
+    remove_orphaned_assistant_messages(&mut compacted_history);
     insert_initial_context_before_last_real_user_or_summary(compacted_history, initial_context)
 }

+/// Removes assistant `Message` items that lost their paired `Reasoning` during
+/// the `retain()` pass. The Azure Responses API rejects a message whose
+/// reasoning was stripped:
+///
+///   "Item 'msg_…' of type 'message' was provided without its required
+///    'reasoning' item: 'rs_…'"
+fn remove_orphaned_assistant_messages(items: &mut Vec<ResponseItem>) {
+    let mut i = 0;
+    while i < items.len() {
+        if let ResponseItem::Message {
+            id: Some(_), role, ..
+        } = &items[i]
+        {
+            if role == "assistant" {
+                let preceded_by_reasoning =
+                    i > 0 && matches!(&items[i - 1], ResponseItem::Reasoning { .. });
+                if !preceded_by_reasoning {
+                    items.remove(i);
+                    continue;
+                }
+            }
+        }
+        i += 1;
+    }
+}
```

### 3.7 フォーク固有の変更 E: serde属性の変更

**ファイル**: `codex-rs/protocol/src/models.rs`

```diff
 pub enum ResponseItem {
     Message {
-        #[serde(default, skip_serializing)]
+        #[serde(default, skip_serializing_if = "Option::is_none")]
         id: Option<String>,
```

```diff
     Reasoning {
-        #[serde(default, skip_serializing)]
+        #[serde(default, skip_serializing_if = "String::is_empty")]
         id: String,
```

```diff
     LocalShellCall {
-        #[serde(default, skip_serializing)]
+        #[serde(default, skip_serializing_if = "Option::is_none")]
         id: Option<String>,
```

```diff
     FunctionCall {
-        #[serde(default, skip_serializing)]
+        #[serde(default, skip_serializing_if = "Option::is_none")]
         id: Option<String>,
```

```diff
 fn should_serialize_reasoning_content(content: &Option<Vec<ReasoningItemContent>>) -> bool {
     match content {
         Some(content) => !content
             .iter()
             .any(|c| matches!(c, ReasoningItemContent::ReasoningText { .. })),
-        None => false,
+        None => true,
     }
 }
```

**テストも追従** (`codex-rs/protocol/src/models.rs` L1995-2008):

```diff
-        for (json_literal, expected_id, expected_action, expected_status, expect_roundtrip) in cases
+        for (json_literal, expected_id, expected_action, expected_status, _expect_roundtrip) in cases
         ...
-            let mut expected_serialized: serde_json::Value = serde_json::from_str(json_literal)?;
-            if !expect_roundtrip && let Some(obj) = expected_serialized.as_object_mut() {
-                obj.remove("id");
-            }
+            let expected_serialized: serde_json::Value = serde_json::from_str(json_literal)?;
```

---

## 4. curl検証証跡

### 4.1 検証環境

```bash
# 環境変数（長さ84文字のAPIキーが設定済みであることを確認）
$ echo "API_KEY set: $([ -n "$AZURE_OPENAI_API_KEY" ] && echo 'YES (length='${#AZURE_OPENAI_API_KEY}')' || echo 'NO')"
API_KEY set: YES (length=84)

# エンドポイント情報
BASE_URL="https://ram4-for-codex.services.ai.azure.com/openai"
MODEL="gpt-5.1-codex-mini"   # profiles.azure_foundry で指定されているモデル
```

### 4.2 テスト1: エンドポイント・api-version 有効性

**テスト1a: /v1/responses（MS Learn推奨パス、api-versionなし）**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t1a2.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello in one word."}'
```

結果: **HTTP 200 PASS**

---

**テスト1b: /responses?api-version=preview**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t1b2.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/responses?api-version=preview" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello in one word."}'
```

結果: **HTTP 404 FAIL**

```json
{"error":{"code":"404","message": "Resource not found"}}
```

**→ `api-version=preview` はAzure AI Foundryで無効**

---

**テスト1c: /responses?api-version=2025-04-01-preview**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t1c2.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/responses?api-version=2025-04-01-preview" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello in one word."}'
```

結果: **HTTP 200 PASS**

---

**テスト1a（誤モデル名 gpt-5.4 でのエラー）**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t1a.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.4","input":"Say hello in one word."}'
```

結果: **HTTP 404**

```json
{
  "error": {
    "type": "invalid_request_error",
    "code": "DeploymentNotFound",
    "message": "The API deployment for this resource does not exist. If you created the deployment within the last 5 minutes, please wait a moment and try again."
  }
}
```

**→ config.toml の `model = "gpt-5.4"` はデフォルトモデル名だが、実際のAzureデプロイメント名は `gpt-5.1-codex-mini`。profiles.azure_foundry 経由で利用する場合は問題なし。**

### 4.3 テスト2: client_metadata 受け入れ確認

フォーク変更Bの対象フィールド。公式バイナリは `client_metadata` を送信するが、Azureが受け入れるか確認。

**テスト2a: /v1/responses + client_metadata**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t2a.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello.","store":true,"client_metadata":{"x-codex-installation-id":"test-123"}}'
```

結果: **HTTP 200 PASS**

**テスト2b: /responses?api-version=2025-04-01-preview + client_metadata**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t2b.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/responses?api-version=2025-04-01-preview" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello.","store":true,"client_metadata":{"x-codex-installation-id":"test-123"}}'
```

結果: **HTTP 200 PASS**

**→ Azure AI Foundry は `client_metadata` を受け入れる。フォークの変更B（スキップ）はこのエンドポイントでは不要の可能性。**

### 4.4 テスト3: reasoning.encrypted_content 受け入れ確認

フォーク変更Aの対象フィールド。公式バイナリは `include=["reasoning.encrypted_content"]` を送信するが、Azureが受け入れるか確認。

**テスト3a: /v1/responses + reasoning.encrypted_content**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t3a.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Think about 42.","store":true,"reasoning":{"effort":"medium"},"include":["reasoning.encrypted_content"]}'
```

結果: **HTTP 200 PASS**

**テスト3b: /responses?api-version=2025-04-01-preview + reasoning.encrypted_content**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t3b.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/responses?api-version=2025-04-01-preview" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Think about 42.","store":true,"reasoning":{"effort":"medium"},"include":["reasoning.encrypted_content"]}'
```

結果: **HTTP 200 PASS**

**→ Azure AI Foundry は `reasoning.encrypted_content` を受け入れる。フォークの変更A（スキップ）はこのエンドポイントでは不要の可能性。**

### 4.5 テスト4: previous_response_id（store=true の動作確認）

上流0.124.0はAzure向けに `store=true` を送信するため、これが正しく機能するか確認。

**テスト4a: store=true でリクエスト**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t6.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello.","store":true,"client_metadata":{"x-codex-installation-id":"test-123"},"reasoning":{"effort":"medium"},"include":["reasoning.encrypted_content"]}'
```

結果: **HTTP 200 PASS**

レスポンス（冒頭）:

```json
{
  "id": "resp_0d22781c590b8b830069eb7e23fc948196a34367afd756f42b",
  "object": "response",
  "created_at": 1777040932,
  "status": "completed",
  "background": false,
  "completed_at": 1777040932,
  "content_filters": [
    {
      "blocked": false,
      "source_type": "prompt",
      "content_filter_raw": [],
      "content_filter_results": {
        "violence": {
          "filtered": false,
          "severity": "safe"
        },
        "sexual": {
          "filtered": false,
```

**テスト4b: previous_response_id で続き**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t4.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"What did I say?","store":true,"previous_response_id":"resp_0d22781c590b8b830069eb7e23fc948196a34367afd756f42b"}'
```

結果: **HTTP 200 PASS**

**→ `store=true` + `previous_response_id` は正常動作。上流0.124.0のコードで対応済み。**

### 4.6 テスト5: compact エンドポイント

**テスト5a: /v1/responses/compact**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t5c.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses/compact" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","previous_response_id":"resp_0d22781c590b8b830069eb7e23fc948196a34367afd756f42b"}'
```

結果: **HTTP 200 PASS**

**テスト5b: /responses/compact?api-version=2025-04-01-preview**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t5b.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/responses/compact?api-version=2025-04-01-preview" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","previous_response_id":"resp_0d22781c590b8b830069eb7e23fc948196a34367afd756f42b"}'
```

結果: **HTTP 500 FAIL**

```json
{
  "error": {
    "message": "The server had an error processing your request. Sorry about that! You can retry your request, or contact us through an Azure support request at: https://go.microsoft.com/fwlink/?linkid=2213926 if you keep seeing this error. (Please include the request ID b7d93ce8-c2b0-4b95-b228-434af8232b9a in your email.)",
    "type": "server_error",
    "param": null,
    "code": null
  }
}
```

**→ compact エンドポイントは `/v1` パスでのみ動作。api-version パラメータ経由では500エラー。**

### 4.7 テスト6: 全フィールド同時送信

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t6.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"Say hello.","store":true,"client_metadata":{"x-codex-installation-id":"test-123"},"reasoning":{"effort":"medium"},"include":["reasoning.encrypted_content"]}'
```

結果: **HTTP 200 PASS**

**→ フォーク変更A・Bの対象フィールドを含む全フィールド同時送信が成功。**

### 4.8 テスト7: マルチバイト文字入力

**テスト7a: 日本語を直接 -d で渡した場合**

```bash
$ curl -s -w "\n%{http_code}" -o /tmp/azure-t7.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d '{"model":"gpt-5.1-codex-mini","input":"東京の天気を一言で。","store":true}'
```

結果: **HTTP 400 FAIL**（WindowsのbashでUTF-8が正しく渡らない）

```json
{
  "error": {
    "message": "Invalid body: encountered a unicode decode error when parsing this JSON value. Please check the value to ensure it is valid unicode.",
    "type": "invalid_request_error",
    "param": null,
    "code": "invalid_json"
  }
}
```

**テスト7b: JSONファイルから送信（UTF-8エンコーディング保証）**

```bash
$ printf '{"model":"%s","input":"東京の天気を一言で。","store":true}' "gpt-5.1-codex-mini" > /tmp/azure-t7-body.json

$ file /tmp/azure-t7-body.json
JSON text data

$ xxd /tmp/azure-t7-body.json | head -5
00000000: 7b22 6d6f 6465 6c22 3a22 6770 742d 352e  {"model":"gpt-5.
00000010: 312d 636f 6465 782d 6d69 6e69 222c 2269  1-codex-mini","i
00000020: 6e70 7574 223a 22e6 9db1 e4ba ace3 81ae  nput":".........
00000030: e5a4 a9e6 b097 e382 92e4 b880 e8a8 80e3  ................
00000040: 81a7 e380 8222 2c22 7374 6f72 6522 3a74  .....","store":t

$ curl -s -w "\n%{http_code}" -o /tmp/azure-t7b.json \
  "https://ram4-for-codex.services.ai.azure.com/openai/v1/responses" \
  -H "api-key: ${AZURE_OPENAI_API_KEY}" \
  -H "Content-Type: application/json" \
  -d @/tmp/azure-t7-body.json
```

結果: **HTTP 200 PASS**

**→ マルチバイト文字はリクエストbody内では問題なし。テスト7aのエラーはWindows bashのエンコーディング問題であり、Azure APIの問題ではない。**

---

## 5. 検証結果まとめ

### 5.1 エンドポイント/URLパス比較

| URLパス | 結果 | 備考 |
|---|---|---|
| `/v1/responses` | ✅ 200 | MS Learn推奨パス。全フィールド受け入れ |
| `/v1/responses/compact` | ✅ 200 | リモートcompaction対応 |
| `/responses?api-version=preview` | ❌ 404 | `preview` は無効なapi-version値 |
| `/responses?api-version=2025-04-01-preview` | ✅ 200 | 正しいapi-version形式 |
| `/responses/compact?api-version=2025-04-01-preview` | ❌ 500 | compactはapi-version経由でエラー |

### 5.2 フィールド受け入れ（/v1/responses）

| フィールド | 結果 | フォーク変更 |
|---|---|---|
| `client_metadata` | ✅ 受け入れ | B: スキップ → 不要の可能性 |
| `include=["reasoning.encrypted_content"]` | ✅ 受け入れ | A: スキップ → 不要の可能性 |
| `store=true` | ✅ 受け入れ | 上流0.124.0に既に対応済み |
| `previous_response_id` | ✅ 動作 | 上流0.124.0に既に対応済み |
| 全フィールド同時 | ✅ 受け入れ | — |

### 5.3 フォーク変更の必要性判定

| 変更 | curl検証結果 | 判定 | 備考 |
|---|---|---|---|
| A. `encrypted_content` スキップ | Azure APIが受け入れ | **不要の可能性** | ただしレスポンスに含まれない可能性あり |
| B. `client_metadata` スキップ | Azure APIが受け入れ | **不要の可能性** | Azureが無視している可能性 |
| C. Base64 turn metadata | curlで検証不可 | **要個別確認** | HTTP header内のマルチバイト問題 |
| D. 孤立メッセージ除去 | curlで検証不可 | **要個別確認** | compaction後のAzure APIバリデーション |
| E. serde属性変更 | curlで検証不可 | **要個別確認** | フィールドの送信有無の違い |

---

## 6. ②（設定変更のみ）で解消可能なケースの判定

### ②の `api-version = "preview"` について

**結論: `api-version=preview` はAzure AI Foundryで無効（404）**。

正しくは `api-version=2025-04-01-preview` を使用する必要があるが、これでも `/responses/compact` が500エラーになる。

一方、MS Learn推奨の `/v1` パス（api-versionなし）は全てのエンドポイントで正常動作する。

### ②で解消可能なケース

**A・Bについては、①（MS Learn推奨 /v1 パス）の時点でAzureがフィールドを受け入れることが確認された**。したがって:

- ①で問題が発生するケース ≠ A・B（Azure APIレベルでは受け入れられるため）
- ②の `api-version` 変更は追加的な効果を持たない（①と同じ結果）
- むしろ `/v1` パスの方が安定（compactも動作する）

**C・D・Eについてはcurlでは再現不可**。これらは実際のCodexセッション内で以下のタイミングで発生する:

- C: turn metadata HTTP headerにマルチバイト文字が含まれる場合
- D: リモートcompaction後にreasoningが除去され、messageのみが残る場合
- E: 通信履歴の再送時に `id:null` や空の reasoning_content がシリアライズされる場合

これらを検証するには、実際にCodexセッションを長時間実行し、compactionがトリガーされる状況を再現する必要がある。

---

## 7. C/D/E Python再現検証（2026-04-25 実施）

検証スクリプト: `docs/azure-cde-repro-test.py`

### 7.1 テストコードでの検証可否

| 変更 | テストファイル | cargo test コマンド | 上流に存在 |
|---|---|---|---|
| C: Base64 turn metadata | `codex-rs/core/src/turn_metadata_tests.rs` | `cargo test -p codex-core turn_metadata` | テストあり（Base64前提） |
| D: 孤立メッセージ除去 | `codex-rs/core/src/compact_tests.rs:570-627` | `cargo test -p codex-core process_compacted_history_removes_orphaned` | **テストなし** |
| E: serde属性変更 | `codex-rs/protocol/src/models.rs:1995-2008` | `cargo test -p codex-protocol roundtrips_web_search_call_actions` | **テストあり（フォーク追従済み）** |

**注意**: CのテストはフォークのBase64実装を前提としているため、上流コードでは `decode_turn_metadata_header` がBase64デコードを期待して失敗する。上流では `serde_json::from_str` を直接呼ぶべき。

Dのテスト `process_compacted_history_removes_orphaned_assistant_messages` は **フォークにのみ存在**（上流 `rust-v0.124.0` にはない）。

### 7.2 C: Base64 turn metadata 検証結果

**問題の本質**: HTTP header値は ASCII のみ可能（RFC 7230）。マルチバイト文字を含むJSONを直接ヘッダーに設定すると、クライアント側でエラー。

**テストC-1: 非ASCII JSONをそのままヘッダーに設定（上流の挙動）**

```python
metadata = {
    "session_id": "test-session",
    "workspaces": {
        "C:\\Users\\ram\\日本語プロジェクト\\repo": { ... }
    }
}
raw_json = json.dumps(metadata, ensure_ascii=False)
headers = {"x-codex-turn-metadata": raw_json}
requests.post(url, headers=headers, ...)
```

結果:

```
ERROR: 'latin-1' codec can't encode characters in position 109-117: ordinal not in range(256)
```

**→ Python requestsライブラリが非ASCIIヘッダーを拒否。Rustの `HeaderValue::from_str()` も同様に失敗する。上流では `.ok()` でヘッダーがサイレントに欠落する。**

**テストC-2: Base64 エンコード後ヘッダーに設定（フォークの挙動）**

```python
encoded = base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
headers = {"x-codex-turn-metadata": encoded}
requests.post(url, headers=headers, ...)
```

結果: **HTTP 200 PASS**

**テストC-3: ヘッダーなしでリクエスト**

結果: **HTTP 200**

**判定**:
- ✅ **問題は再現可能**: マルチバイト文字パスで作業すると上流はヘッダー欠落
- 影響範囲: テレメトリ/オブザーバビリティのデータ損失。API自体はヘッダーなしでも動作
- Rust再現: `TurnMetadataBag::to_header_value()` が非ASCII JSONを返し、`parse_turn_metadata_header()` → `HeaderValue::from_str()` が失敗

### 7.3 D: 孤立メッセージ除去 検証結果

**テストD-Step1: セッション作成**

```python
resp = requests.post(V1_URL, json={
    "model": MODEL,
    "input": "Think about the number 7.",
    "store": True,
    "reasoning": {"effort": "medium"},
})
# → HTTP 200
# → response_id: resp_01a16c90e3fca4cd0069ebe4cf5bd88194bd49748a5fe4f9e1
# → reasoning items: 1, assistant message items: 1
```

**テストD-Step2: 孤立したassistantメッセージのみをcompactに送信**

```python
orphaned_msg = {"type": "message", "id": "msg_01a16c...", "role": "assistant", "content": [...]}
resp = requests.post(COMPACT_URL, json={
    "model": MODEL,
    "previous_response_id": response_id,
    "input": [orphaned_msg],  # reasoningなし
})
```

結果: **HTTP 400**

```json
{
  "error": {
    "message": "Duplicate item found with id msg_01a16c90e3fca4cd0069ebe4d00e6c8194bced4a277d2890fb. Remove duplicate items from your input and try again.",
    "type": "invalid_request_error",
    "param": "input"
  }
}
```

**→ 予想していた "without its required reasoning item" エラーではなく "Duplicate item" エラー。`previous_response_id` で取得済みのアイテムと同じ id を送信したため。**

**テストD-Step3: 正しいペア（reasoning + message）を送信**

結果: **HTTP 400**（同じく "Duplicate item" エラー）

**判定**:
- compact エンドポイントの `input` に `previous_response_id` に既に含まれる id を持つアイテムを送信すると "Duplicate item" エラーになる
- フォークのコードコメントにある "without its required reasoning item" エラーは、**異なるシナリオ**（compact結果を次回リクエストのinputとして送信する際）で発生する可能性
- Python での完全な再現には、compaction の実際のフロー（内部で行われるアイテムの編集→再送）をシミュレートする必要がある
- **cargo test での検証**: `process_compacted_history_removes_orphaned_assistant_messages` が上流にないため、上流コードで `cargo test` を実行すると、孤立メッセージが除去されず compact リクエストに含まれる

### 7.4 E: serde属性変更 検証結果

**テストE-1a: id ありの assistant message を /v1/responses に送信**

```python
{"type": "message", "id": "msg_test_123", "role": "assistant",
 "content": [{"type": "output_text", "text": "hi there"}]}
```

結果: **HTTP 200 PASS**

**テストE-1b: id なしの assistant message を /v1/responses に送信**

```python
{"type": "message", "role": "assistant",
 "content": [{"type": "output_text", "text": "hi there"}]}
```

結果: **HTTP 200 PASS**

**テストE-2: reasoning item の content フィールド確認**

Azure からのレスポンスの reasoning item に含まれる `content` キーを確認:

```
reasoning item: content キーあり=False
```

**→ Azure は reasoning item の content キーを省略して返す。上流の `skip_serializing` と同様の形式。**

**テストE-3a: id を含めて compact に送信（フォークの挙動: skip_serializing_if）**

```python
resp = requests.post(COMPACT_URL, json={
    "model": MODEL,
    "previous_response_id": response_id,
    "input": [reasoning_item_with_id, message_item_with_id],
})
```

結果: **HTTP 400 FAIL**

```json
{
  "error": {
    "message": "Duplicate item found with id rs_0356cf6fc1c5af130069ebe4daa93c8196a0be88c82a422228. Remove duplicate items from your input and try again.",
    "type": "invalid_request_error"
  }
}
```

**テストE-3b: id を除外して compact に送信（上流の挙動: skip_serializing）**

```python
reasoning_no_id = {k: v for k, v in reasoning_item.items() if k != "id"}
message_no_id = {k: v for k, v in message_item.items() if k != "id"}
resp = requests.post(COMPACT_URL, json={
    "model": MODEL,
    "previous_response_id": response_id,
    "input": [reasoning_no_id, message_no_id],
})
```

結果: **HTTP 200 PASS**

### 7.5 E の検証から得られた重要な発見

**上流の `skip_serializing`（id を常に省略）は、compact エンドポイントで正しい動作をする。**

| 送信形式 | /v1/responses | /v1/responses/compact |
|---|---|---|
| id あり | ✅ 200 | ❌ 400 (Duplicate) |
| id なし | ✅ 200 | ✅ 200 |

フォークの `skip_serializing_if = "Option::is_none"` は id が存在する場合にシリアライズするが、compact エンドポイントではこれが "Duplicate item" エラーを引き起こす可能性がある。

ただし、実際の compaction フローでは:
- クライアントがアイテムを新規に構築する際は `id = None` である可能性が高い
- API レスポンスから取得したアイテムをそのまま compact に送信することはない
- フォークの compact テストでは `id: Some("msg_abc")` を使っているが、これはインメモリテストであり実際のHTTPリクエストではない

**結論**: E の変更は compact エンドポイントの動作に影響を与える可能性があるが、実際の compaction フローでのアイテムの id の有無によって結果が異なる。フォークが実際に正常動作しているという事実から、実際のフローでは id なしで送信されている可能性が高い。

---

## 8. テストコードによる検証可否まとめ

### 8.1 各変更のテスト・再現方法

| 変更 | cargo test | Python再現 | 実データ再現 | 備考 |
|---|---|---|---|---|
| A. encrypted_content skip | 不要（API受け入れ確認済み） | 不要 | 不要 | curlで対応済み |
| B. client_metadata skip | 不要（API受け入れ確認済み） | 不要 | 不要 | curlで対応済み |
| C. Base64 turn metadata | `cargo test -p codex-core turn_metadata` | ✅ 再現済み | マルチバイトパスでcodex実行 | テレメトリ損失のみ |
| D. 孤立メッセージ除去 | `cargo test -p codex-core process_compacted_history_removes_orphaned` | ⚠️ 部分的 | 長時間セッションでcompactionトリガー | フォークにのみテストあり |
| E. serde属性変更 | `cargo test -p codex-protocol roundtrips_web_search_call_actions` | ✅ 再現済み | HTTPリクエストキャプチャで比較 | **idなしの方がcompactで安全** |

### 8.2 今後のアクション

1. **C の実データ再現**: マルチバイト文字を含むディレクトリパス（例: `C:\Users\ram\日本語プロジェクト\repo`）で `codex exec` を実行し、`x-codex-turn-metadata` ヘッダーが送信されているか確認
   - 上流バイナリ: ヘッダー欠落（テレメトリデータなし）
   - フォーク: ヘッダーあり（Base64エンコード済み）

2. **D の実データ再現**: 公式バイナリで長時間セッションを実行し、compaction がトリガーされた際にエラーが発生するか確認
   - `codex` を起動し、多数のターンを実行して compaction を誘発
   - フォークの `remove_orphaned_assistant_messages` が存在しない場合の挙動を確認

3. **E の影響範囲の確認**: フォークの compact テスト (`compact_tests.rs`) に `id: Some(...)` を含むアイテムがあるが、実際の compact リクエストで id が送信されるか確認
   - `RUST_LOG=debug` で HTTP リクエストボディをキャプチャ
   - フォークと上流でシリアライズされた JSON を比較

4. **フォークの最小化**: A・Bが不要、Eが逆効果の可能性を踏まえ、フォークの差分を C（Base64）と D（孤立メッセージ除去）に絞り込めるか検討

---

## 9. 公式ドキュメントに基づく api-version の正しい設定（2026-04-25 追加調査）

### 9.1 調査経緯
3つの公式ドキュメントを調査した結果、**既存の404エラーはURL構造の違いが原因**であることが判明。

### 9.2 公式ドキュメントからの主要発見

#### ページ1: Azure Models Directly Sold (learn.microsoft.com)
- `api-version=preview` は **BFLプロバイダAPI** でのみ使用例がある
- Azure OpenAI APIでは **直接的な記述なし**

#### ページ2: Azure OpenAI REST API v1 Preview Reference (最重要)
```
POST {endpoint}/openai/v1/responses?api-version=preview
```
- **正しい形式**: `/openai/v1/responses?api-version=preview`
- `api-version=preview` は `/v1` パスと組み合わせて使用
- `api-version` パラメータは **省略可能**（デフォルト: v1）

#### ページ3: OpenAI Codex Config Advanced (公式推奨)
```toml
[model_providers.azure]
base_url = "https://YOUR_PROJECT_NAME.openai.azure.com/openai"  # /v1 なし
query_params = { api-version = "2025-04-01-preview" }  # 日付形式推奨
```

### 9.3 CodexのURL構築ロジック（コード確認）
- `base_url` + `/` + `"responses"` + `?` + `query_params` の単純結合
- `/v1` の自動挿入 **なし**
- 現在の設定で構築されるURL:
  ```rust
  base_url = "https://ram4-for-codex.services.ai.azure.com/openai/v1"
  query_params = { api-version = "preview" }
  → Result: https://ram4-for-codex.services.ai.azure.com/openai/v1/responses?api-version=preview
  ```

### 9.4 新たなcurl検証結果（最重要）

| テスト | URL | 結果 | 備考 |
|---|---|---|---|
| **既存テスト1b** | `/openai/responses?api-version=preview` | ❌ 404 | **`/v1` パスが欠落** |
| **新規テスト** | `/openai/v1/responses?api-version=preview` | ✅ 200 | **MS Learn公式形式** |
| **新規テスト** | `/openai/v1/responses/compact?api-version=preview` | ✅ 200 | **compactも正常動作** |
| **OpenAI推奨形式** | `/openai/responses?api-version=2025-04-01-preview` | ✅ 200 | **公式設定に準拠** |

### 9.5 ②（設定変更のみ）の再評価

**結論: `api-version=preview` はAzure AI Foundryで有効（ただし正しい形式で）**

- ②の `api-version="preview"` は **動作するが、形式が重要**
  - ✅ **正解**: `/openai/v1/responses?api-version=preview` 
  - ❌ 誤り: `/openai/responses?api-version=preview`（404）

- **②の設定変更で解消可能なケース**
  - ①と②はURL形式が異なるだけでAPI動作自体は同じ
  - `/v1/responses`（api-versionなし）と `/v1/responses?api-version=preview` のどちらも正常動作
  - ②に変更してもA・Bについては追加効果なし（どちらの形式でも受け入れられる）

- **ベストプラクティス**
  ```toml
  # 選択肢1: MS Learn v1 API形式（推奨）
  [model_providers.azure]
  base_url = "https://ram4-for-codex.services.ai.azure.com/openai/v1"
  query_params = { api-version = "preview" }  # 追加可能（省略時もデフォルトv1）
  
  # 選択肢2: OpenAI推奨形式
  [model_providers.azure]
  base_url = "https://ram4-for-codex.services.ai.azure.com/openai"  # /v1 なし
  query_params = { api-version = "2025-04-01-preview" }
  ```

### 9.6 フォーク変更の再判定

| 変更 | curl検証結果 | 結果 |
|---|---|---|
| A・B (`encrypted_content`, `client_metadata` スキップ) | `/v1` パスで正常動作 | **不要** |
| C (Base64 turn metadata) | curl検証不可 | **検証継続中** |
| D (孤立メッセージ除去) | curl検証不可 | **検証継続中** |
| E (serde属性変更) | idなしの方がcompactで安全 | **注意が必要** |

**重要**: A・Bは不要に変わったが、②の `api-version="preview"` は問題なく動作するため、フォークは依然としてC・Dが必要。

---

## 10. C/D/E Python再テスト結果（api-version=preview 対応）（2026-04-25 実施）

テストスクリプト: `docs/azure-cde-repro-test.py` (v2)

### 10.1 テスト環境

```
エンドポイント (v1):           {BASE_URL}/v1/responses
エンドポイント (v1+preview):   {BASE_URL}/v1/responses?api-version=preview
Compact (v1):                  {BASE_URL}/v1/responses/compact
Compact (v1+preview):          {BASE_URL}/v1/responses/compact?api-version=preview
モデル: gpt-5.1-codex-mini
```

### 10.2 テストC: Base64 turn metadata（api-version=preview 追加検証）

| テスト | 内容 | HTTP | 結果 |
|---|---|---|---|
| C-1 | Raw JSON（非ASCII）ヘッダー | ERROR | latin-1エンコード失敗（上流と同じ） |
| C-2 | Base64エンコードヘッダー | 200 | PASS |
| C-3 | ヘッダーなし | 200 | PASS（テレメトリ損失のみ） |
| **C-4** | **api-version=preview + Base64ヘッダー** | **200** | **PASS（新規確認）** |

**結論**: api-version=preview でも Base64ヘッダーは正常に受け入れられる。Cの問題（非ASCIIヘッダー欠落）はapi-versionに関係なく発生するクライアント側問題。

### 10.3 テストD: 孤立assistantメッセージ（api-version=preview 追加検証）

| テスト | 内容 | HTTP | 結果 |
|---|---|---|---|
| D-Step1 | セッション作成(store=true) | 200 | OK（response_id取得） |
| D-Step2 | 孤立assistant msg → compact | 400 | Duplicate item（id重複） |
| D-Step3 | ペア構造(reasoning+msg) → compact | 400 | Duplicate item（id重複） |
| **D-Step4** | **preview + idなし → compact** | **200** | **PASS（新規確認）** |

**結論**: api-version=preview でも id なしのアイテムで compact が正常動作。Dの"without its required reasoning"エラーは、compactエンドポイントではなく、**次回レスポンスリクエスト時にストアされたアイテムの整合性チェック**で発生する可能性が高い。

### 10.4 テストE: serde属性変更（api-version=preview 追加検証）

| テスト | 内容 | HTTP | 結果 |
|---|---|---|---|
| E-1a | id付きassistant msg → responses | 200 | PASS |
| E-1b | idなしassistant msg → responses | 200 | PASS |
| E-2a | reasoning content確認 | 200 | Azureはcontentキーを省略して返す |
| E-3a | id付き → compact | 400 | Duplicate item（フォークの挙動で問題） |
| E-3b | idなし → compact | 200 | PASS（上流の挙動で安全） |
| E-3c | content除外(id付き) → compact | 400 | Duplicate item（idが残っているため） |
| **E-4** | **preview + idなし → compact** | **200** | **PASS（新規確認）** |
| **E-4** | **preview + id付き → compact** | **400** | **Duplicate item（api-version問わず同様）** |

**結論**: api-version=preview でも id 付きアイテムは compact で Duplicate item エラーになる。これはapi-versionに依存しないAzure API側の仕様。

### 10.5 api-version=preview の全体的な結論

| エンドポイント | api-versionなし | api-version=preview |
|---|---|---|
| `/v1/responses` | 200 | 200 |
| `/v1/responses/compact`（idなし） | 200 | 200 |
| `/v1/responses/compact`（idあり） | 400 | 400 |
| Base64ヘッダー受け入れ | 200 | 200 |

**api-version=preview は api-versionなしと全く同じAPI動作**を示す。両者間で挙動の差異なし。

### 10.6 フォーク変更の最終判定（更新）

| 変更 | 判定 | 根拠 |
|---|---|---|
| A. `encrypted_content` スキップ | **不要** | api-version問わずAzure APIが受け入れ |
| B. `client_metadata` スキップ | **不要** | api-version問わずAzure APIが受け入れ |
| C. Base64 turn metadata | **必要（テレメトリ用途）** | 非ASCIIヘッダーがサイレントに欠落。API動作への影響なし |
| D. 孤立メッセージ除去 | **必要（要確認）** | Python再現では"Duplicate item"のみ。実際のcompactionフローでの検証が必要 |
| E. serde属性変更 | **逆効果の可能性** | id付きアイテムがcompactでDuplicate itemエラー。上流の`skip_serializing`（id常に省略）が安全 |
