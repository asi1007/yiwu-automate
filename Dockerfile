# Python 3.11の公式イメージを使用
FROM python:3.11-slim

# 作業ディレクトリを設定
WORKDIR /app

# システムの依存関係をインストール
RUN apt-get update && apt-get install -y \
    wget \
    gnupg \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Playwrightの依存関係をインストール
RUN pip install playwright
RUN playwright install chromium
RUN playwright install-deps chromium

# アプリケーションの依存関係をコピーしてインストール
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# アプリケーションコードをコピー
COPY . .

# ポート8080を公開（Cloud Runのデフォルト）
EXPOSE 8080

# アプリケーションを実行
CMD ["python", "yiwu_scraper.py"]
