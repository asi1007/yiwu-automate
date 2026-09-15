# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web scraping application that automates order status checking on Yiwu Passport (yiwupassport.jp) and exports data to Google Sheets. The application uses Playwright for browser automation and can be deployed to Google Cloud Run.

## Architecture

- **yiwu_scraper.py**: Main scraping application with YiwuScraper class that handles login, navigation, and data extraction
- **google_sheet.py**: Google Sheets integration using gspread library and service account authentication
- **drive_monitor.py**: Google Drive monitoring system that watches for new OCS/TW files and extracts ASIN/tracking data
- **run_monitor.py**: Execution script for the Drive monitoring system
- **service_account.json**: Google Cloud service account credentials for Sheets API access
- **Deployment**: Supports both local execution and Google Cloud Run deployment

## Development Commands

### Local Development
```bash
# Install dependencies
pip install -r requirements.txt
playwright install chromium

# Run the scraper
python yiwu_scraper.py

# Run the Google Drive monitor
python run_monitor.py
```

### Environment Setup
The application requires a `.env` file with:
```bash
YIWU_USERNAME=your-email@example.com
YIWU_PASSWORD=your-password
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=your-spreadsheet-id
GOOGLE_SHEETS_WORKSHEET=yiwu
```

### Cloud Deployment
```bash
# Manual deployment
./deploy.sh

# Using Cloud Build
gcloud builds submit --config cloudbuild.yaml
```

## Key Dependencies

- **playwright**: Browser automation for web scraping
- **gspread**: Google Sheets API integration
- **google-auth**: Google Cloud authentication
- **google-api-python-client**: Google Drive API for file monitoring
- **python-dotenv**: Environment variable management

## Configuration Notes

- Cloud Run deployment uses headless browser mode
- Memory: 2GB, CPU: 2 cores, timeout: 3600 seconds
- The application scrapes all pages of order history and extracts product links from detail pages
- Google Sheets integration requires service account with Sheets and Drive API permissions
- Drive monitor watches for OCS files (tracking in G2, ASIN in G17+) and TW files (tracking in A12, ASIN in K16+)
- Processed data is written to the "invoice" sheet with filename, file type, tracking number, and ASIN list

## 到着遅延アラート（daily note + Todoist）

`_report_overdue_orders` が **購入から 14 日超・未発送・到着日が空**の注文を集約し、2 箇所へ出す。

| 出力先 | 何のため |
|---|---|
| daily note「## Claude Code ログ」 | その日の記録。**流れて消える** |
| **Todoist（プロジェクト `benrii`）** | 対応するまで残る。優先度 3 |

### 重複を作らない

毎朝 6 時に走るので、**同じ注文でタスクを増やさない**。
`find_existing_task` が本文の `[到着遅延]` マーカーと**注文番号**で既存タスクを探し、

- 無ければ作る
- あって経過日数が変わっていれば**本文を書き換える**（`42日経過` を最新に）
- 変わっていなければ何もしない

注文番号が空の行は**商品名の先頭 40 文字**で同一性を見る。仕入管理には注文番号が無い行が実在する
（2026-03-21 のジュエリー袋 5 行など）。

### 設定

`.env` に `TODOIST_API_TOKEN` と `TODOIST_PROJECT_ID` を置く。**未設定ならスキップして本処理は止めない。**
Todoist API は **`/api/v1/`**（`/rest/v2/` は 410）。

タスクを完了しても、到着日が空のままなら翌朝また作られる。**到着日を埋めるのが本来の解消**。

## 注文状況の照会（lookup_orders.py）

注文番号で `yp.buyer-central.com` を引き、**買付・支払い・入庫のどこまで進んだか**を返す。
滞留の原因が仕入先側か倉庫側かイーウーの作業かを切り分けるために使う。

```bash
python3 lookup_orders.py Y0806-260717002        # 注文番号を直接
python3 lookup_orders.py --from-sheet 157,161   # 仕入管理シートの行番号から
```

「注文番号」列は**1セルに複数の注文番号が改行で入る**ことがあるので分解して全部照会する。

### 画面の癖

`order_lookup.py` にまとめてある。UI が変わったらここだけ直す。

- **「全て」タブを開くまで 1 行も出ない**（初期表示は状態別タブで 0 件）
- **検索ボタンは 2 つ。1 つ目は商品名検索、2 つ目が注文検索**
- **`fill()` は効かない。** `click` → `type` でキー入力として入れる
- 追跡番号の後ろにボタンの文言が続くので「カートに追加」で切る

「受領済み」なのに**入庫日が空の行が実在する**。入庫の有無だけで未着と判断しないこと
（`_fill_missing_dates` が実行日で補完する対象）。

手順の説明はスキル `yiwu-order-status` にある。
