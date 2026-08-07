#!/bin/bash

PROJECT_ID=${PROJECT_ID:-"yiwu-automate"}
SERVICE_NAME=${SERVICE_NAME:-"yiwu-scraper"}
REGION=${REGION:-"asia-northeast1"}
SERVICE_ACCOUNT="yiwu-scraper@${PROJECT_ID}.iam.gserviceaccount.com"

echo "=== Cloud Scheduler セットアップ ==="
echo "プロジェクトID: $PROJECT_ID"
echo "ジョブ名: ${SERVICE_NAME}-daily"
echo "リージョン: $REGION"
echo "スケジュール: 毎日 10:00 (JST)"
echo "=================================="

gcloud scheduler jobs create http "${SERVICE_NAME}-daily" \
  --project="$PROJECT_ID" \
  --location="$REGION" \
  --schedule="0 10 * * *" \
  --time-zone="Asia/Tokyo" \
  --uri="https://${REGION}-run.googleapis.com/apis/run.googleapis.com/v1/namespaces/${PROJECT_ID}/jobs/${SERVICE_NAME}:run" \
  --http-method=POST \
  --oauth-service-account-email="$SERVICE_ACCOUNT" \
  --description="毎日10時に到着日自動更新を実行"

if [ $? -eq 0 ]; then
  echo "Cloud Scheduler ジョブの作成完了！"
  echo "確認: gcloud scheduler jobs list --project=$PROJECT_ID --location=$REGION"
else
  echo "エラー: ジョブの作成に失敗しました"
  echo "既存ジョブがある場合は update を使用してください:"
  echo "  gcloud scheduler jobs update http ${SERVICE_NAME}-daily \\"
  echo "    --project=$PROJECT_ID --location=$REGION \\"
  echo "    --schedule='0 10 * * *' --time-zone=Asia/Tokyo"
fi
