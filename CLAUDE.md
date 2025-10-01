# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a web scraping application that automates order status checking on Yiwu Passport (yiwupassport.jp) and exports data to Google Sheets. The application uses Playwright for browser automation and can be deployed to Google Cloud Run.

## Architecture

- **yiwu_scraper.py**: Main scraping application with YiwuScraper class that handles login, navigation, and data extraction
- **google_sheet.py**: Google Sheets integration using gspread library and service account authentication
- **drive_monitor.py**: Google Drive monitoring system that watches for new OCS/TW files and extracts ASIN/tracking data
- **run_monitor.py**: Execution script for the Drive monitoring system
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

# Run the Google Drive monitor
python run_monitor.py
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
- **google-api-python-client**: Google Drive API for file monitoring
- **python-dotenv**: Environment variable management

## Configuration Notes

- Cloud Run deployment uses headless browser mode
- Memory: 2GB, CPU: 2 cores, timeout: 3600 seconds
- The application scrapes all pages of order history and extracts product links from detail pages
- Google Sheets integration requires service account with Sheets and Drive API permissions
- Drive monitor watches for OCS files (tracking in G2, ASIN in G17+) and TW files (tracking in A12, ASIN in K16+)
- Processed data is written to the "invoice" sheet with filename, file type, tracking number, and ASIN list