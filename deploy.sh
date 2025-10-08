#!/bin/bash

# .envファイルから環境変数を読み込み（存在する場合）
if [ -f .env ]; then
    echo ".envファイルから環境変数を読み込み中..."
    export $(cat .env | grep -v '^#' | xargs)
else
    echo ".envファイルが見つかりません。デフォルト値を使用します。"
fi

# プロジェクトIDとサービス名を設定（環境変数から取得、なければデフォルト値）
PROJECT_ID=${PROJECT_ID:-"yiwu-automate"}
SERVICE_NAME=${SERVICE_NAME:-"yiwu-scraper"}
REGION=${REGION:-"asia-northeast1"}

# 環境変数を設定（環境変数から取得、なければデフォルト値）
export YIWU_USERNAME=${YIWU_USERNAME:-"kochatomoki@gmail.com"}
export YIWU_PASSWORD=${YIWU_PASSWORD:-"Yamada0402"}
export GOOGLE_SHEETS_CREDENTIALS_JSON=${GOOGLE_SHEETS_CREDENTIALS_JSON:-"service_account.json"}
export GOOGLE_SHEETS_SPREADSHEET_ID=${GOOGLE_SHEETS_SPREADSHEET_ID:-"1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"}
export GOOGLE_SHEETS_WORKSHEET=${GOOGLE_SHEETS_WORKSHEET:-"yiwu"}

# 設定を表示
echo "=== デプロイ設定 ==="
echo "プロジェクトID: $PROJECT_ID"
echo "サービス名: $SERVICE_NAME"
echo "リージョン: $REGION"
echo "Yiwuユーザー名: $YIWU_USERNAME"
echo "Google Sheets Spreadsheet ID: $GOOGLE_SHEETS_SPREADSHEET_ID"
echo "=================="

# Dockerイメージをビルド
echo "Dockerイメージをビルド中..."
docker build --platform linux/amd64 -t asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME .

# Artifact Registryにプッシュ
echo "Artifact Registryにプッシュ中..."
docker push asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME

# Cloud Run Jobを作成・更新
echo "Cloud Run Jobを作成・更新中..."
# 既存のジョブがあるかチェック
if gcloud run jobs describe $SERVICE_NAME --region=$REGION >/dev/null 2>&1; then
  echo "既存のジョブを更新中..."
  gcloud run jobs replace /dev/stdin --region=$REGION <<EOF
apiVersion: run.googleapis.com/v1
kind: Job
metadata:
  name: $SERVICE_NAME
  annotations:
    run.googleapis.com/launch-stage: BETA
spec:
  template:
    spec:
      template:
        spec:
          containers:
          - image: asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME
            env:
            - name: YIWU_USERNAME
              value: "$YIWU_USERNAME"
            - name: YIWU_PASSWORD
              value: "$YIWU_PASSWORD"
            - name: GOOGLE_SHEETS_CREDENTIALS_JSON
              value: "$GOOGLE_SHEETS_CREDENTIALS_JSON"
            - name: GOOGLE_SHEETS_SPREADSHEET_ID
              value: "$GOOGLE_SHEETS_SPREADSHEET_ID"
            - name: GOOGLE_SHEETS_WORKSHEET
              value: "$GOOGLE_SHEETS_WORKSHEET"
            resources:
              limits:
                cpu: 2000m
                memory: 2Gi
          restartPolicy: Never
          timeoutSeconds: 3600
EOF
else
  echo "新しいジョブを作成中..."
  gcloud run jobs create $SERVICE_NAME \
    --image asia-northeast1-docker.pkg.dev/$PROJECT_ID/$SERVICE_NAME/$SERVICE_NAME \
    --region $REGION \
    --set-env-vars YIWU_USERNAME=$YIWU_USERNAME \
    --set-env-vars YIWU_PASSWORD=$YIWU_PASSWORD \
    --set-env-vars GOOGLE_SHEETS_CREDENTIALS_JSON=$GOOGLE_SHEETS_CREDENTIALS_JSON \
    --set-env-vars GOOGLE_SHEETS_SPREADSHEET_ID=$GOOGLE_SHEETS_SPREADSHEET_ID \
    --set-env-vars GOOGLE_SHEETS_WORKSHEET=$GOOGLE_SHEETS_WORKSHEET \
    --memory 2Gi \
    --cpu 2 \
    --task-timeout 3600 \
    --max-retries 3
fi

echo "デプロイ完了！"
