#!/bin/bash

PROJECT_ID=${PROJECT_ID:-"yiwu-automate"}
SERVICE_NAME=${SERVICE_NAME:-"yiwu-scraper"}
REGION=${REGION:-"asia-northeast1"}
IMAGE="asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME"
SERVICE_ACCOUNT="yiwu-scraper@yiwu-automate.iam.gserviceaccount.com"

if [ -f .env ]; then
    echo ".envファイルから環境変数を読み込み中..."
    export $(cat .env | grep -v '^#' | grep -v '^$' | xargs)
fi

echo "=== デプロイ設定 ==="
echo "プロジェクトID: $PROJECT_ID"
echo "サービス名: $SERVICE_NAME"
echo "リージョン: $REGION"
echo "=================="

echo "Dockerイメージをビルド中..."
docker build --platform linux/amd64 -t $IMAGE .

echo "Artifact Registryにプッシュ中..."
docker push $IMAGE

echo "Cloud Run Jobを更新中..."
gcloud run jobs update $SERVICE_NAME \
  --image $IMAGE \
  --service-account $SERVICE_ACCOUNT \
  --region $REGION \
  --set-env-vars "BUYER_CENTRAL_EMAIL=${BUYER_CENTRAL_EMAIL},BUYER_CENTRAL_PASSWORD=${BUYER_CENTRAL_PASSWORD},GOOGLE_SHEETS_SPREADSHEET_ID=${GOOGLE_SHEETS_SPREADSHEET_ID},GOOGLE_SHEETS_WORKSHEET=${GOOGLE_SHEETS_WORKSHEET},SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL},HEADLESS=true" \
  --memory 2Gi \
  --cpu 2 \
  --task-timeout 3600s

echo "デプロイ完了！"
