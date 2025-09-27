# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web scraping application that automates order status checking on Yiwu Passport (yiwupassport.jp) and exports data to Google Sheets. The application uses Playwright for browser automation and can be deployed to Google Cloud Run.

## Architecture

- **yiwu_scraper.py**: Main scraping application with YiwuScraper class that handles login, navigation, and data extraction
- **google_sheet.py**: Google Sheets integration using gspread library and service account authentication
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
- **python-dotenv**: Environment variable management

## Configuration Notes

- Cloud Run deployment uses headless browser mode
- Memory: 2GB, CPU: 2 cores, timeout: 3600 seconds
- The application scrapes all pages of order history and extracts product links from detail pages
- Google Sheets integration requires service account with Sheets and Drive API permissions