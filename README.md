# kintone-dify-sample

kintoneとDifyを連携させるサンプルプロジェクトです。

## 概要

このプロジェクトは、kintoneのデータをDifyと連携させ、kintone内のデータをベースとして、AIによる高度な分析や処理を実現するためのサンプル実装です。FastAPIを使用したバックエンドAPIサーバーとして実装されています。

## 必要要件

- Python 3.12以上
- uv（Pythonパッケージマネージャー）
- ngrok
- kintoneアカウント
- Difyアカウント

## セットアップ

### 1. uvのインストール
uvのインストールについては、[公式リポジトリ](https://github.com/astral-sh/uv)を参照してください。

### 2. ngrokのセットアップ
1. [ngrokの公式サイト](https://ngrok.com/)からアカウント作成とインストール
2. 認証トークンの設定:
```bash
ngrok config add-authtoken あなたの認証トークン
```

### 3. プロジェクトのセットアップ
1. リポジトリのクローン
```bash
git clone https://github.com/mahm/kintone-dify-sample.git
cd kintone-dify-sample
```

2. 依存パッケージのインストール
```bash
uv sync
```

3. 設定ファイルの作成
```bash
cp config.yaml.sample config.yaml
```

4. `config.yaml`の編集
詳しくは下部のconfig.yamlの解説を参照してください。

## 起動方法

開発サーバーの起動:
```bash
./run_local.sh
```

サーバーはデフォルトで http://localhost:8000 で起動します。
ngrokによって自動的に公開URLが生成されます。

webhookは以下のように設定します。

- メソッド: POST
- URL: https://{ngrokの公開URL}/webhook

## config.yamlの解説

### 基本構造

`config.yaml`は以下の2つの主要セクションで構成されています：

1. `kintone`セクション：kintoneの基本設定
2. `pairs`セクション：kintoneアプリとDifyの連携設定

### 詳細設定手順

#### 1. kintoneの基本設定

```yaml
kintone:
  base_url: "https://あなたのサブドメイン.cybozu.com"
```

#### 2. 連携ペアの設定

`pairs`セクションでは、複数のkintoneアプリとDifyの連携を設定できます。各ペアは以下の要素で構成されます：

```yaml
pairs:
  - name: "連携の名前" # 例: "inquiry-processing"
    kintone_app_id: アプリID番号 # 例: 123
    kintone_token: "APIトークン" # 例: "abcd1234..."
    dify_api_key: "DifyのAPIキー" # 例: "dify_sk_..."

    # kintoneからDifyへのフィールドマッピング
    kintone_to_dify:
      # difyのフィールド名: "kintoneのフィールドコード"の形式で列挙する
      # 具体例:
      inquiry_email: "Email"
      inquiry_text: "InquiryContent"

    # Difyからkintoneへのフィールドマッピング
    dify_to_kintone:
      # kintoneのフィールドコード: "difyの出力キー"の形式で列挙する
      # 具体例:
      customer_id: "customer_id"
      reply_draft: "reply_draft"
```

### 設定例

実際の使用例を示します：

```yaml
kintone:
  base_url: "https://example.cybozu.com"

pairs:
  - name: "お問い合わせ処理"
    kintone_app_id: 123
    kintone_token: "abcd1234efgh5678"
    dify_api_key: "dify_sk_xxxxxxxxxxxxx"
    
    kintone_to_dify:
      customer_email: "メールアドレス"
      inquiry_content: "問い合わせ内容"
    
    dify_to_kintone:
      回答案: "ai_response"
      顧客分類: "customer_category"

  - name: "商品レビュー分析"
    kintone_app_id: 124
    kintone_token: "ijkl9012mnop3456"
    dify_api_key: "dify_sk_yyyyyyyyyyyy"
    
    kintone_to_dify:
      review_text: "レビュー本文"
      rating: "評価"
    
    dify_to_kintone:
      感情分析: "sentiment_score"
      重要ポイント: "key_points"
```

### 注意事項

- 各フィールドコードは、kintoneアプリの実際のフィールドコードと完全に一致する必要があります
- Difyのフィールド名は、設定したDifyワークフローの入出力と一致させる必要があります
- APIトークンは適切な権限（読み取り/書き込み）が付与されていることを確認してください
- 複数の連携ペアを設定する場合は、それぞれのアプリIDとトークンが正しく対応していることを確認してください


## ライセンス

Apache License 2.0
