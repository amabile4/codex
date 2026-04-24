#!/usr/bin/env python3
"""
Azure Codex 0.124.0: フォーク変更 C/D/E の再現テスト (v2)

フォーク(③)のコード変更のうち、curl検証で確認できなかった3箇所について、
PythonでAzure APIに直接リクエストを送り、問題を再現する。

v2 変更点:
  - api-version=preview クエリパラメータ対応を追加
  - /v1 パス + api-version=preview の組み合わせテストを追加
  - D/E の compact テストで api-version=preview 版も実行

使い方:
  export AZURE_OPENAI_API_KEY="your-key"
  export AZURE_BASE_URL="https://ram4-for-codex.services.ai.azure.com/openai"
  export DEPLOYMENT_NAME="gpt-5.1-codex-mini"
  python3 azure-cde-repro-test.py
"""

import base64
import json
import os
import sys
import requests

BASE_URL = os.environ.get(
    "AZURE_BASE_URL", "https://ram4-for-codex.services.ai.azure.com/openai"
)
MODEL = os.environ.get("DEPLOYMENT_NAME", "gpt-5.1-codex-mini")
API_KEY = os.environ.get("AZURE_OPENAI_API_KEY", "")

if not API_KEY:
    print("ERROR: AZURE_OPENAI_API_KEY environment variable is required")
    sys.exit(1)

# URL パターン: v1 パス（api-version なし）と v1+preview
V1_URL = f"{BASE_URL}/v1/responses"
V1_PREVIEW_URL = f"{BASE_URL}/v1/responses?api-version=preview"
COMPACT_URL = f"{BASE_URL}/v1/responses/compact"
COMPACT_PREVIEW_URL = f"{BASE_URL}/v1/responses/compact?api-version=preview"
HEADERS = {
    "api-key": API_KEY,
    "Content-Type": "application/json",
}


def sep(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


# ============================================================
# C: Base64 turn metadata の検証
# ============================================================
# この問題はクライアント側（Rust HTTPライブラリ）で発生する。
# HTTP header に非ASCII文字を含められないため、マルチバイト文字を
# 含むパスで作業すると x-codex-turn-metadata ヘッダーが欠落する。
# Azure API側には直接関係しないが、テレメトリデータが失われる。
# ============================================================

def test_c_multibyte_header():
    sep("C: x-codex-turn-metadata ヘッダーのマルチバイト文字テスト")

    # 日本語を含む turn metadata（Rustの TurnMetadataBag のJSON表現をシミュレート）
    metadata_with_multibyte = {
        "session_id": "test-session",
        "thread_source": "user",
        "turn_id": "turn-1",
        "workspaces": {
            # マルチバイト文字を含むパスキー
            "C:\\Users\\ram\\日本語プロジェクト\\repo": {
                "latest_git_commit_hash": "abc123",
                "has_changes": False,
            }
        },
        "sandbox": "none",
    }

    # --- 上流の挙動: raw JSON をヘッダーに設定 ---
    raw_json = json.dumps(metadata_with_multibyte, ensure_ascii=False)
    print(f"[Upstream] Raw JSON ({len(raw_json.encode('utf-8'))} bytes):")
    print(f"  {raw_json[:100]}...")

    # Python requests で非ASCIIヘッダーを送れるか検証
    print("\n  [Test C-1] Raw JSON (非ASCII) を x-codex-turn-metadata ヘッダーで送信:")
    try:
        # Python requests は非ASCIIヘッダーを拒否する可能性がある
        raw_headers = {
            **HEADERS,
            "x-codex-turn-metadata": raw_json,
        }
        resp = requests.post(V1_URL, headers=raw_headers,
                           json={"model": MODEL, "input": "hello", "store": True},
                           timeout=30)
        print(f"  → HTTP {resp.status_code} (非ASCIIヘッダーが通った)")
    except Exception as e:
        print(f"  → ERROR: {e}")
        print(f"  → これは上流（Rust）でも同様に HeaderValue::from_str が失敗する状況")
        print(f"  → 上流ではヘッダーがサイレントに欠落する（.ok()で無視）")

    # --- フォークの挙動: Base64 エンコードしてヘッダーに設定 ---
    encoded = base64.b64encode(raw_json.encode("utf-8")).decode("ascii")
    print(f"\n  [Test C-2] Base64 encoded ({len(encoded)} chars):")
    print(f"  {encoded[:80]}...")

    b64_headers = {
        **HEADERS,
        "x-codex-turn-metadata": encoded,
    }
    resp = requests.post(V1_URL, headers=b64_headers,
                        json={"model": MODEL, "input": "hello", "store": True},
                        timeout=30)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code < 300:
        print(f"  → PASS: Base64エンコードならAzureが受け入れる")
    else:
        print(f"  → FAIL: {resp.text[:300]}")

    # --- 補足: ヘッダー欠落の影響確認 ---
    print("\n  [Test C-3] ヘッダーなしでリクエスト:")
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={"model": MODEL, "input": "hello", "store": True},
                        timeout=30)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code < 300:
        print(f"  → INFO: ヘッダーなしでもAPI自体は動作する")
        print(f"  → 影響: テレメトリ/オブザーバビリティのデータ損失のみ")
    else:
        print(f"  → FAIL: {resp.text[:300]}")

    # --- C-4: api-version=preview でヘッダー送信 ---
    print("\n  [Test C-4] api-version=preview + Base64ヘッダーで送信:")
    resp = requests.post(V1_PREVIEW_URL, headers=b64_headers,
                        json={"model": MODEL, "input": "hello", "store": True},
                        timeout=30)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code < 300:
        print(f"  → PASS: api-version=preview でも Base64ヘッダー受け入れ")
    else:
        print(f"  → FAIL: {resp.text[:300]}")


# ============================================================
# D: Orphaned assistant message の検証
# ============================================================
# compaction 後に reasoning が除去され、assistant メッセージだけが
# 残った場合、Azure API がバリデーションエラーを返すか確認する。
# フォークの remove_orphaned_assistant_messages() はこれを防ぐ。
# ============================================================

def test_d_orphaned_messages():
    sep("D: 孤立した assistant メッセージのバリデーションエラー確認")

    # Step 1: store=true でセッションを開始し、response_id を取得
    print("  [Step 1] セッション開始 (store=true)...")
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={
                            "model": MODEL,
                            "input": "Think about the number 7.",
                            "store": True,
                            "reasoning": {"effort": "medium"},
                        }, timeout=60)
    if resp.status_code >= 300:
        print(f"  → FAIL: セッション開始に失敗: {resp.text[:300]}")
        return

    data = resp.json()
    response_id = data.get("id", "")
    print(f"  → response_id: {response_id}")

    # レスポンスから reasoning + message のペアを確認
    output_items = data.get("output", [])
    reasoning_items = [i for i in output_items if i.get("type") == "reasoning"]
    message_items = [i for i in output_items if i.get("type") == "message" and i.get("role") == "assistant"]
    print(f"  → reasoning items: {len(reasoning_items)}")
    print(f"  → assistant message items: {len(message_items)}")

    # Step 2: 孤立した assistant メッセージ（reasoningなし）を compact エンドポイントに送信
    if message_items:
        orphaned_msg = message_items[0].copy()
        print(f"\n  [Step 2] 孤立した assistant メッセージのみを compact に送信:")
        print(f"  → 送信する item: type={orphaned_msg.get('type')}, id={orphaned_msg.get('id')}")

        # reasoning がペアになっていない assistant メッセージのみを input に含める
        compact_payload = {
            "model": MODEL,
            "previous_response_id": response_id,
            "input": [orphaned_msg],
        }
        resp = requests.post(COMPACT_URL, headers=HEADERS,
                            json=compact_payload, timeout=60)
        print(f"  → HTTP {resp.status_code}")
        if resp.status_code >= 400:
            error_text = resp.text[:500]
            print(f"  → エラー内容: {error_text}")
            if "without its required" in error_text or "reasoning" in error_text.lower():
                print(f"  → ★ これがフォーク変更Dで防ぐエラー ★")
            else:
                print(f"  → 別のエラー（形式の問題の可能性）")
        else:
            print(f"  → PASS: Azure は孤立メッセージを受け入れた（エラーにならない）")

    # Step 3: 正しい構造（reasoning + message ペア）で送信
    if reasoning_items and message_items:
        print(f"\n  [Step 3] 正しい構造 (reasoning + message ペア) で送信:")
        correct_payload = {
            "model": MODEL,
            "previous_response_id": response_id,
            "input": [reasoning_items[0], message_items[0]],
        }
        resp = requests.post(COMPACT_URL, headers=HEADERS,
                            json=correct_payload, timeout=60)
        print(f"  → HTTP {resp.status_code}")
        if resp.status_code < 300:
            print(f"  → PASS: ペア構造なら正常動作")
        else:
            print(f"  → FAIL: {resp.text[:300]}")

    # Step 4: api-version=preview で compact エンドポイント検証
    if message_items:
        print(f"\n  [Step 4] api-version=preview で compact エンドポイント検証:")
        # 新しいセッションを作成（previous_response_id 用）
        resp = requests.post(V1_PREVIEW_URL, headers=HEADERS,
                            json={
                                "model": MODEL,
                                "input": "Think about the number 9.",
                                "store": True,
                                "reasoning": {"effort": "medium"},
                            }, timeout=60)
        if resp.status_code < 300:
            data2 = resp.json()
            rid2 = data2.get("id", "")
            print(f"  → 新セッション: {rid2}")
            output2 = data2.get("output", [])
            msg2 = [i for i in output2 if i.get("type") == "message" and i.get("role") == "assistant"]
            rs2 = [i for i in output2 if i.get("type") == "reasoning"]

            # id なしアイテムで compact をテスト
            if msg2:
                m_no_id = {k: v for k, v in msg2[0].items() if k != "id"}
                input_items = []
                if rs2:
                    r_no_id = {k: v for k, v in rs2[0].items() if k != "id"}
                    input_items.append(r_no_id)
                input_items.append(m_no_id)

                resp = requests.post(COMPACT_PREVIEW_URL, headers=HEADERS,
                                    json={
                                        "model": MODEL,
                                        "previous_response_id": rid2,
                                        "input": input_items,
                                    }, timeout=60)
                print(f"  → api-version=preview + compact: HTTP {resp.status_code}")
                if resp.status_code < 300:
                    print(f"  → PASS: api-version=preview + compact 正常動作")
                else:
                    print(f"  → FAIL: {resp.text[:300]}")
        else:
            print(f"  → セッション作成失敗: {resp.text[:200]}")


# ============================================================
# E: Serde属性変更 (skip_serializing vs skip_serializing_if) の検証
# ============================================================
# 上流: #[serde(skip_serializing)] → id フィールドは常に送信されない
# フォーク: #[serde(skip_serializing_if = "Option::is_none")] → id がある時は送信
#
# また:
# 上流: should_serialize_reasoning_content(None) = false → content:null が送信される
# フォーク: should_serialize_reasoning_content(None) = true → content フィールドが省略される
# ============================================================

def test_e_serde_differences():
    sep("E: serde属性変更の検証 (id と content フィールド)")

    # E-1: assistant message に id を含めるかどうか
    print("  [Test E-1a] id ありの assistant message を responses に送信:")
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={
                            "model": MODEL,
                            "input": [
                                {"type": "message", "role": "user",
                                 "content": [{"type": "input_text", "text": "hello"}]},
                                # id 付き assistant message（フォークの skip_serializing_if では送信される）
                                {"type": "message", "id": "msg_test_123", "role": "assistant",
                                 "content": [{"type": "output_text", "text": "hi there"}]},
                            ],
                            "store": True,
                        }, timeout=30)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  → エラー: {resp.text[:300]}")
        if "id" in resp.text.lower():
            print(f"  → id フィールドが原因の可能性")
    else:
        print(f"  → PASS: id 付き assistant message は受け入れられた")

    print("\n  [Test E-1b] id なしの assistant message を responses に送信:")
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={
                            "model": MODEL,
                            "input": [
                                {"type": "message", "role": "user",
                                 "content": [{"type": "input_text", "text": "hello"}]},
                                # id なし assistant message（上流の skip_serializing と同じ）
                                {"type": "message", "role": "assistant",
                                 "content": [{"type": "output_text", "text": "hi there"}]},
                            ],
                            "store": True,
                        }, timeout=30)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code >= 400:
        print(f"  → エラー: {resp.text[:300]}")
    else:
        print(f"  → PASS: id なし assistant message は受け入れられた")

    # E-2: reasoning の content フィールド (null vs 省略)
    print("\n  [Test E-2a] reasoning item に content:null を含めて送信:")
    print("  (上流の挙動: should_serialize_reasoning_content(None)=false → content:null が送信される)")
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={
                            "model": MODEL,
                            "input": "Think about 7.",
                            "store": True,
                            "reasoning": {"effort": "medium"},
                        }, timeout=60)
    print(f"  → HTTP {resp.status_code}")
    if resp.status_code < 300:
        data = resp.json()
        for item in data.get("output", []):
            if item.get("type") == "reasoning":
                has_content = "content" in item
                content_val = item.get("content")
                print(f"  → reasoning item: content キーあり={has_content}, 値={content_val}")
                if content_val is None:
                    print(f"  → Azure が content:null を返した（上流のシリアライズと同じ形式）")
                elif not has_content:
                    print(f"  → Azure が content キーを省略（フォークの skip_serializing_if と同じ形式）")
                break
    else:
        print(f"  → エラー: {resp.text[:300]}")

    # E-3: compact エンドポイントで id 付き/なし items を送信
    print("\n  [Test E-3] compact エンドポイントでの id あり/なし比較:")
    # まずセッションを作成
    resp = requests.post(V1_URL, headers=HEADERS,
                        json={
                            "model": MODEL,
                            "input": "Think about 42.",
                            "store": True,
                            "reasoning": {"effort": "medium"},
                        }, timeout=60)
    if resp.status_code >= 300:
        print(f"  → セッション作成失敗: {resp.text[:200]}")
        return

    data = resp.json()
    response_id = data.get("id", "")
    print(f"  → response_id: {response_id}")

    # reasoning と message を取得
    output_items = data.get("output", [])
    reasoning_item = None
    assistant_item = None
    for item in output_items:
        if item.get("type") == "reasoning" and reasoning_item is None:
            reasoning_item = item
        if item.get("type") == "message" and item.get("role") == "assistant" and assistant_item is None:
            assistant_item = item

    if reasoning_item and assistant_item:
        # id を含めた場合（フォークの挙動）
        print(f"\n  [Test E-3a] id を含めて compact に送信 (フォークの挙動):")
        r_with_id = reasoning_item.copy()
        m_with_id = assistant_item.copy()
        # id が含まれていることを確認
        print(f"    reasoning id: {r_with_id.get('id', '(なし)')}")
        print(f"    message id: {m_with_id.get('id', '(なし)')}")

        resp = requests.post(COMPACT_URL, headers=HEADERS,
                            json={
                                "model": MODEL,
                                "previous_response_id": response_id,
                                "input": [r_with_id, m_with_id],
                            }, timeout=60)
        print(f"    → HTTP {resp.status_code}")
        if resp.status_code >= 400:
            print(f"    → エラー: {resp.text[:300]}")

        # id を除外した場合（上流の挙動: skip_serializing で id が常に省略される）
        print(f"\n  [Test E-3b] id を除外して compact に送信 (上流の挙動):")
        r_no_id = {k: v for k, v in reasoning_item.items() if k != "id"}
        m_no_id = {k: v for k, v in assistant_item.items() if k != "id"}

        resp = requests.post(COMPACT_URL, headers=HEADERS,
                            json={
                                "model": MODEL,
                                "previous_response_id": response_id,
                                "input": [r_no_id, m_no_id],
                            }, timeout=60)
        print(f"    → HTTP {resp.status_code}")
        if resp.status_code >= 400:
            print(f"    → エラー: {resp.text[:300]}")
        else:
            print(f"    → PASS: id なしでも compact は動作した")

        # content:null のみを除外（フォークの should_serialize_reasoning_content 変更）
        print(f"\n  [Test E-3c] reasoning の content キーを除外して送信 (フォークの挙動):")
        r_no_content = {k: v for k, v in reasoning_item.items()
                       if k != "content" or v is not None}
        resp = requests.post(COMPACT_URL, headers=HEADERS,
                            json={
                                "model": MODEL,
                                "previous_response_id": response_id,
                                "input": [r_no_content, m_with_id],
                            }, timeout=60)
        print(f"    → HTTP {resp.status_code}")
        if resp.status_code >= 400:
            print(f"    → エラー: {resp.text[:300]}")
        else:
            print(f"    → PASS: content 省略でも動作")

        # E-4: api-version=preview で id なし compact テスト
        print(f"\n  [Test E-4] api-version=preview で id なし compact テスト:")
        # 新しいセッションを作成
        resp = requests.post(V1_PREVIEW_URL, headers=HEADERS,
                            json={
                                "model": MODEL,
                                "input": "Think about 99.",
                                "store": True,
                                "reasoning": {"effort": "medium"},
                            }, timeout=60)
        if resp.status_code < 300:
            data4 = resp.json()
            rid4 = data4.get("id", "")
            output4 = data4.get("output", [])
            rs4 = None
            msg4 = None
            for item in output4:
                if item.get("type") == "reasoning" and rs4 is None:
                    rs4 = item
                if item.get("type") == "message" and item.get("role") == "assistant" and msg4 is None:
                    msg4 = item

            if rs4 and msg4:
                r4_no_id = {k: v for k, v in rs4.items() if k != "id"}
                m4_no_id = {k: v for k, v in msg4.items() if k != "id"}
                resp = requests.post(COMPACT_PREVIEW_URL, headers=HEADERS,
                                    json={
                                        "model": MODEL,
                                        "previous_response_id": rid4,
                                        "input": [r4_no_id, m4_no_id],
                                    }, timeout=60)
                print(f"    → api-version=preview + idなし compact: HTTP {resp.status_code}")
                if resp.status_code < 300:
                    print(f"    → PASS: api-version=preview + idなし compact 正常動作")
                else:
                    print(f"    → FAIL: {resp.text[:300]}")

                # id ありでテスト
                resp = requests.post(COMPACT_PREVIEW_URL, headers=HEADERS,
                                    json={
                                        "model": MODEL,
                                        "previous_response_id": rid4,
                                        "input": [rs4, msg4],
                                    }, timeout=60)
                print(f"    → api-version=preview + idあり compact: HTTP {resp.status_code}")
                if resp.status_code >= 400:
                    print(f"    → FAIL (id重複エラーの可能性): {resp.text[:300]}")
            else:
                print(f"    → reasoning/message 取得失敗")
        else:
            print(f"    → セッション作成失敗: {resp.text[:200]}")


# ============================================================
# メイン
# ============================================================

if __name__ == "__main__":
    print(f"Azure Codex C/D/E 再現テスト v2")
    print(f"エンドポイント (v1):           {V1_URL}")
    print(f"エンドポイント (v1+preview):   {V1_PREVIEW_URL}")
    print(f"Compact (v1):                  {COMPACT_URL}")
    print(f"Compact (v1+preview):          {COMPACT_PREVIEW_URL}")
    print(f"モデル: {MODEL}")
    print()

    test_c_multibyte_header()
    test_d_orphaned_messages()
    test_e_serde_differences()

    print(f"\n{'='*60}")
    print(f"  テスト完了")
    print(f"{'='*60}")
