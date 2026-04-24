# Azure Doc Page 1: Models Sold Directly by Azure

- 取得日: 2026-04-25
- URL: https://learn.microsoft.com/en-us/azure/foundry/foundry-models/concepts/models-sold-directly-by-azure?tabs=global-standard-aoai%2Cglobal-standard&pivots=azure-openai

## 概要

Azure AI Foundryで直接提供されるモデルの一覧。GPT-5.4シリーズ、GPT-5.3シリーズ、GPT-5.2シリーズ、GPT-5.1シリーズ、o-series、Soraなど。

## api-version 関連の記述

### BFL (Black Forest Labs) プロバイダAPI

BFLプロバイダAPIのエンドポイントで `api-version=preview` が使用されている例:

```
<resource-name>/providers/blackforestlabs/v1/flux-kontext-pro?api-version=preview
<resource-name>/providers/blackforestlabs/v1/flux-pro-1.1?api-version=preview
```

**注意**: これはBFLサービスプロバイダの独自API形式であり、Azure OpenAI APIとは異なる。

### OpenAI Image API の標準形式

```
https://<resource-name>/openai/deployments/{deployment-id}/images/generations
```

api-version クエリパラメータは含まれていない。`/v1` パスも使用されていない。

## モデル一覧（一部）

| モデルシリーズ | モデルID | Preview/GA |
|---|---|---|
| GPT-5.4 | gpt-5.4, gpt-5.4-mini, gpt-5.4-nano, gpt-5.4-pro | GA |
| GPT-5.3 | gpt-5.3-codex, gpt-5.3-chat | Preview |
| GPT-5.2 | gpt-5.2, gpt-5.2-codex, gpt-5.2-chat | Preview |
| GPT-5.1 | gpt-5.1, gpt-5.1-codex, gpt-5.1-codex-mini, gpt-5.1-chat | Preview/GA |
| GPT-5 | gpt-5, gpt-5-mini, gpt-5-nano, gpt-5-chat | GA |

## デプロイメントタイプ

- Standard (グローバル/リージョン)
- Provisioned managed
- Batch

## 重要な注意事項

- Previewモデルは本番環境での使用非推奨
- gpt-5.1の `reasoning_effort` デフォルトは `none`
- `gpt-5.1-codex` は "Optimized for Codex CLI & Codex VS Code extension" と記載

## ページ1からの結論

このページには **Azure OpenAI Responses API の `api-version` 仕様に関する直接的な記述はない**。
`api-version=preview` はBFLなどの非OpenAIプロバイダのAPIでのみ言及されている。
