# イーウーパスポート スクレイピング

イーウーパスポートの注文状況を自動でスクレイピングし、Google Sheetsに出力するアプリケーションです。

## 機能

- イーウーパスポートにログイン
- 注文状況照会ページから全ページのデータを取得
- 各注文の詳細ページから商品リンクを取得
- Google Sheetsに結果を出力
- 中国事務所到着日の更新時にSlack通知（オプション）

## 必要な環境変数

このアプリケーションは`python-dotenv`を使用して環境変数ファイル（`.env`）から設定を読み込みます。

### 方法1: 環境変数ファイルを使用（推奨）

1. `env.example`をコピーして`.env`ファイルを作成：
```bash
cp env.example .env
```

2. `.env`ファイルを編集して、実際の値を設定：
```bash
# イーウーパスポート ログイン情報
YIWU_USERNAME=your-email@example.com
YIWU_PASSWORD=your-password

# Google Sheets 設定
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id
GOOGLE_SHEETS_WORKSHEET=yiwu

# Slack 通知設定（オプション）
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**注意**: `.env`ファイルは機密情報を含むため、Gitにコミットしないでください。

### 方法2: 直接環境変数を設定

```bash
export YIWU_USERNAME="your-email@example.com"
export YIWU_PASSWORD="your-password"
export GOOGLE_SHEETS_CREDENTIALS_JSON="service_account.json"
export GOOGLE_SHEETS_SPREADSHEET_ID="your-spreadsheet-id"
export GOOGLE_SHEETS_WORKSHEET="yiwu"
export SLACK_WEBHOOK_URL="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"
```

## ローカル実行

1. 依存関係をインストール
```bash
pip install -r requirements.txt
playwright install chromium
```

2. 環境変数を設定（方法1または方法2を使用）

3. スクレイピング実行
```bash
python yiwu_scraper.py
```

## Google Cloud Run デプロイ

### 方法1: 手動デプロイ

1. Google Cloud SDKをインストール
2. プロジェクトIDを設定
3. デプロイスクリプトを実行
```bash
./deploy.sh
```

### 方法2: Cloud Build使用

```bash
gcloud builds submit --config cloudbuild.yaml
```

## Slack通知の設定（オプション）

中国事務所到着日の更新時にSlackへ通知を送信できます。

### 設定手順

1. Slack Workspaceで[Incoming Webhooks](https://api.slack.com/messaging/webhooks)を作成
2. Webhook URLを取得
3. 環境変数`SLACK_WEBHOOK_URL`にWebhook URLを設定

### 通知のタイミング

以下の場合にSlack通知が送信されます：
- 既存の注文番号で、中国事務所到着日（F列）が空欄から値ありに変更された場合
- 新規注文で、中国事務所到着日に初めから値が入っている場合

**注意**: `SLACK_WEBHOOK_URL`が設定されていない場合、通知機能は無効化され、エラーなく動作します。

## 必要な権限

- Google Sheets API
- Google Drive API (読み取り専用)

## 注意事項

- Cloud Runでは`headless=True`でブラウザを起動
- タイムアウトは3600秒（1時間）に設定
- メモリは2GB、CPUは2コアに設定
