# 到着日自動更新機能 設計書

## 概要

Google Sheets「仕入管理」シートの未発送行に対して、yp.buyer-central.com の入庫済みデータを照合し、到着日を自動更新する。

既存の yiwupassport.jp 向けスクレイパーを buyer-central.com 対応に書き換える（サイト移行に伴う対応）。

## 全体フロー

```
1. Google Sheets「仕入管理」シートを読み込み
   - 4行目ヘッダーから「ステータス」「注文番号」「到着日」列を動的特定
   - ステータス=「未発送」かつ到着日が空の行を抽出

2. yp.buyer-central.com にログイン
   - 入庫済みタブの全ページから注文番号と入庫日時を取得

3. マッチング＆書き込み
   - シートの注文番号とbuyer-central.comの注文番号を突き合わせ
   - マッチした行の到着日列にMM/DD形式で入庫日時を書き込み
   - 更新時にSlack通知を送信
```

## 変更対象ファイル

### yiwu_scraper.py

`YiwuScraper` クラスを `BuyerCentralScraper` に置き換え。`DataProcessor` クラスは削除。

#### ログイン

- URL: `https://yp.buyer-central.com/login`
- メールアドレス: `input[placeholder="アカウントをご入力してください"]`
- パスワード: `input[placeholder="パスワードをご入力してください"]`
- ログインボタン: `button:has-text("ログイン")`
- ログイン後 `expect_navigation` でページ遷移を待つ

#### 入庫済みデータ取得

- `https://yp.buyer-central.com/order/list?status=6&keys=order-list` に遷移
- 入庫済みタブ（`.q-tab__label:has-text("入庫済み")`）をクリック
- 各注文ブロック（`tr.relative`）から以下を抽出:
  - 注文番号: `.hover-copy-box span:first-child`
  - 入庫日時: 日時列内の「入庫：」ラベルの後のテキスト
- ページネーション: 全ページを順にスクレイピング
  - `keyboard_arrow_right` ボタンで次ページに遷移
  - ボタンが無効（disabled）になるまでループ

#### 出力

`dict[str, str]`: `{注文番号: 入庫日時}` の辞書

#### 削除するメソッド

- `navigate_to_order_history`
- `extract_order_data`
- `extract_item_data`
- `extract_product_links_from_context`
- `has_next_page`
- `scrape_page_data`
- `scrape_all_pages`
- `enrich_with_product_links`
- `DataProcessor` クラス全体

### google_sheet.py

#### 変更点

- 対象スプレッドシートID: `1xH_-D8XbdP2kdx5U7cWmYwiOHBcLoO621h--sEnAvL0`
- 対象ワークシート: `仕入管理`
- ヘッダー行: 4行目から列名を動的に特定

#### 読み込み

- 全データ取得し、4行目ヘッダーから「ステータス」「注文番号」「到着日」列のインデックスを特定
- ステータス=「未発送」かつ到着日が空（空文字 or `#N/A`）の行を抽出
- 1セルに複数注文番号がある場合（改行区切り）、全てを対象にする

#### 書き込み

- マッチした行の到着日列にMM/DD形式で書き込み
- 複数注文番号の場合、そのうち1つでもマッチすれば到着日を書き込み
- 更新した行についてSlack通知を送信

#### 残す部分

- 認証ロジック（サービスアカウント / Workload Identity）
- `_execute_with_retry`（APIクォータ対策）

#### 削除するメソッド/定数

- `write`, `_should_update_row`, `_update_existing_order`, `_add_new_order`
- `update_table_range`, `get_table_id`, `_get_num_cols`
- 列インデックス定数（`COL_ORDER_ID` 等） → ヘッダー名ベースの動的特定に変更
- `BATCH_SIZE`, `BATCH_WAIT_TIME` 等のバッチ定数

### .env

```bash
# buyer-central.com ログイン情報
BUYER_CENTRAL_EMAIL=atsushi.wada@shinshira-import.jp
BUYER_CENTRAL_PASSWORD=（実際のパスワード）

# Google Sheets 設定
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=1xH_-D8XbdP2kdx5U7cWmYwiOHBcLoO621h--sEnAvL0
GOOGLE_SHEETS_WORKSHEET=仕入管理

# Slack通知
SLACK_WEBHOOK_URL=（既存のWebhook URL）

# ブラウザ設定
HEADLESS=true
```

削除する環境変数: `YIWU_USERNAME`, `YIWU_PASSWORD`

## Google Sheets データ構造

### 仕入管理シート（ヘッダー: 4行目）

| 列名 | 用途 |
|------|------|
| ステータス | 「未発送」でフィルタリング |
| 注文番号 | buyer-central.comの注文番号とマッチング（P形式: `P260318001YP806`） |
| 到着日 | 入庫日時をMM/DD形式で書き込み |

- 列位置はヘッダー名で動的に特定（列移動に対応）
- 注文番号セルに改行区切りで複数番号が入る場合あり

## buyer-central.com サイト構造

### 入庫済み注文一覧

- テーブル構造: Quasar Frameworkベース（Vue.js SPA）
- 注文ブロック: `tr.relative` 内に注文番号ヘッダーと商品行
- 注文番号: `.hover-copy-box span:first-child` のテキスト
- 日時列HTML構造:
  ```html
  <div class="flex flex-col gap-1">
    <div><span class="text-text2">作成：</span><span>2026-03-18 21:41:34</span></div>
    <div><span class="text-text2">注文：</span><span>2026-03-19 11:19:25</span></div>
    <div><span class="text-text2">引落：</span><span>2026-03-19 16:21:38</span></div>
    <div><span class="text-text2">入庫：</span><span>2026-03-20 14:53:44</span></div>
  </div>
  ```
- ページネーション: `keyboard_arrow_right` ボタンで次ページ遷移

## エラーハンドリング

- ログイン失敗: エラーログ出力して終了
- ページスクレイピングのタイムアウト: リトライ（最大3回）
- Google Sheets API クォータ超過: `_execute_with_retry` で指数バックオフ
- マッチング結果0件: 警告ログのみ（正常終了）

## ログ

- CLAUDE.mdのログ管理ルールに従いJSON形式の構造化ログ
- 出力内容: 処理開始/終了、未発送行数、入庫済み注文数、マッチ件数、更新件数

## Slack通知

- 到着日が更新された行ごとに通知
- 既存の `send_arrival_notification` を再利用
- 注文番号と到着日を含むメッセージ
