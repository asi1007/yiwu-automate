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
2. buyer-central.com にログインし、入庫済みの注文一覧をスクレイピング
3. 注文番号をマッチングし、到着日（MM/DD形式）をシートに書き込み
4. 更新した行ごとにSlackへ入庫完了通知を送信
5. シート全行の注文番号と比較し、サイトにあるがシートにない注文番号を商品名付きで一覧表示

## 注意事項

- 入庫済みタブの表示名は「受取済み(数字)」（旧「入庫済み(数字)」から変更あり、両対応済み）
- 入庫日は行全体テキストから `入庫：YYYY-MM-DD HH:MM:SS` を正規表現抽出する（td列位置はサイト改修で変わるため固定しない）
- Keepa `images` フィールドからの画像取得にフォールバック対応済み（`imagesCSV` が空の場合）
