---
name: update-arrival
description: /update-arrival コマンド - buyer-central.comから入庫済み注文をスクレイピングし、Googleスプレッドシートの到着日を更新してSlack通知を送信する
user_invocable: true
---

# 到着日更新コマンド

buyer-central.comの入庫済み注文をスクレイピングし、仕入管理シートの到着日を自動更新する。

## 実行手順

ローカルで実行する:

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/automate-yiwu
python yiwu_scraper.py
```

## 自動実行

launchdで毎朝6時に自動実行（スリープ復帰後にも実行される）:
- plist: `~/Library/LaunchAgents/com.wadaatsushi.yiwu-scraper.plist`
- ログ: `/tmp/yiwu_scraper.log`

## 処理内容

1. Googleスプレッドシート「仕入管理」から状態が「未発送」かつ到着日が空の行を取得
2. buyer-central.com にログインし、「受取済み」「受領中」両タブの注文一覧をスクレイピング
3. 注文番号をマッチングし、到着日（MM/DD形式）をシートに書き込み
   - 入庫日がある行はその日付を使用
   - 入庫日が無い行（受領中・入庫日未確定の受取済み）は**実行日（今日）**を到着日として使用
4. 更新した行ごとにSlackへ入庫完了通知を送信
5. シート全行の注文番号と比較し、サイトにあるがシートにない注文番号を商品名付きで一覧表示

## 注意事項

- 対象タブは「受取済み(数字)」と「受領中(数字)」の2つ（`RECEIVED_TAB_PATTERNS`）
- 入庫済みタブの表示名は「受取済み(数字)」（旧「入庫済み(数字)」から変更あり、両対応済み）
- 入庫日は行全体テキストから `入庫：YYYY-MM-DD HH:MM:SS` を正規表現抽出する（td列位置はサイト改修で変わるため固定しない）
- 「受取済み」タブでも `入庫：` ラベルはあるが日付値が空の行が存在する。この場合も実行日で到着日を補填する（`_fill_missing_dates`）
- 到着日は一度埋まれば `未発送かつ到着日空` の抽出条件から外れるため、実行日は初回検知時に1回だけ確定し、再実行で上書きされない
- Keepa `images` フィールドからの画像取得にフォールバック対応済み（`imagesCSV` が空の場合）
