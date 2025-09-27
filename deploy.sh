#!/bin/bash

# プロジェクトIDとサービス名を設定
PROJECT_ID="your-project-id"
SERVICE_NAME="yiwu-scraper"
REGION="asia-northeast1"

# 環境変数を設定
export YIWU_USERNAME="kochatomoki@gmail.com"
export YIWU_PASSWORD="Yamada0402"
export GOOGLE_SHEETS_CREDENTIALS_JSON="service_account.json"
export GOOGLE_SHEETS_SPREADSHEET_ID="1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"
export GOOGLE_SHEETS_WORKSHEET="yiwu"

# Dockerイメージをビルド
echo "Dockerイメージをビルド中..."
docker build -t gcr.io/$PROJECT_ID/$SERVICE_NAME .

# Google Container Registryにプッシュ
echo "Google Container Registryにプッシュ中..."
docker push gcr.io/$PROJECT_ID/$SERVICE_NAME

# Cloud Runにデプロイ
echo "Cloud Runにデプロイ中..."
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --set-env-vars YIWU_USERNAME=$YIWU_USERNAME \
  --set-env-vars YIWU_PASSWORD=$YIWU_PASSWORD \
  --set-env-vars GOOGLE_SHEETS_CREDENTIALS_JSON=$GOOGLE_SHEETS_CREDENTIALS_JSON \
  --set-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=$GOOGLE_SHEETS_SPREADSHEET_ID \
  --set-env-vars GOOGLE_SHEETS_WORKSHEET=$GOOGLE_SHEETS_WORKSHEET \
  --memory 2Gi \
  --cpu 2 \
  --timeout 3600

echo "デプロイ完了！"
