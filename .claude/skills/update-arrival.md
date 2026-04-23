---
name: update-arrival
description: /update-arrival コマンド - buyer-central.comから入庫済み注文をスクレイピングし、Googleスプレッドシートの到着日を更新してSlack通知を送信する
user_invocable: true
---

# 到着日更新コマンド

buyer-central.comの入庫済み注文をスクレイピングし、仕入管理シートの到着日を自動更新する。

## 実行手順

1. Cloud Run Jobを実行する:

```bash
gcloud run jobs execute yiwu-scraper \
  --project=yiwu-automate \
  --region=asia-northeast1 \
  --wait
```

2. 実行結果を確認する:

```bash
gcloud run jobs executions list \
  --job=yiwu-scraper \
  --project=yiwu-automate \
  --region=asia-northeast1 \
  --limit=1
```

3. ログを確認する:

```bash
gcloud logging read "resource.type=cloud_run_job AND resource.labels.job_name=yiwu-scraper" \
  --project=yiwu-automate \
  --limit=20 \
  --format="table(timestamp, jsonPayload.message)"
```

## ローカル実行（デバッグ用）

```bash
cd /Users/wadaatsushi/Documents/automation/procurements/automate-yiwu
python yiwu_scraper.py
```

## 処理内容

1. Googleスプレッドシート「仕入管理」からステータスが「未発送」かつ到着日が空の行を取得
2. buyer-central.com にログインし、入庫済み（status=6）の注文一覧をスクレイピング
3. 注文番号をマッチングし、到着日（MM/DD形式）をシートに書き込み
4. 更新した行ごとにSlackへ入庫完了通知を送信
