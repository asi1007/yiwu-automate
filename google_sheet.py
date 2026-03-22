import os
import logging
import time
import gspread
from gspread.exceptions import APIError
from google.oauth2.service_account import Credentials
from google.auth import default
from slack_notifier import SlackNotifier

logger = logging.getLogger(__name__)

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.readonly",
]

MAX_RETRIES = 5
INITIAL_BACKOFF = 2
MAX_BACKOFF = 120

HEADER_ROW_INDEX = 3
HEADER_NAMES = ["ステータス", "注文番号", "到着日"]


class GSheet:

    def __init__(self, credentials_file=None, spreadsheet_id=None, worksheet_name=None):
        self.credentials_file = credentials_file or os.environ.get(
            "GOOGLE_SHEETS_CREDENTIALS_JSON", "service_account.json"
        )
        self.spreadsheet_id = spreadsheet_id or os.environ.get(
            "GOOGLE_SHEETS_SPREADSHEET_ID", "1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls"
        )
        self.worksheet_name = worksheet_name or os.environ.get(
            "GOOGLE_SHEETS_WORKSHEET", "yiwu"
        )

        if not self.spreadsheet_id:
            raise RuntimeError("環境変数 GOOGLE_SHEETS_SPREADSHEET_ID を設定してください")

        if os.path.exists(self.credentials_file):
            logger.info(f"サービスアカウントファイル {self.credentials_file} から認証します")
            creds = Credentials.from_service_account_file(self.credentials_file, scopes=SCOPES)
        else:
            logger.info("Workload Identity（Application Default Credentials）で認証します")
            creds, _ = default(scopes=SCOPES)

        gc = gspread.authorize(creds)
        sh = gc.open_by_key(self.spreadsheet_id)
        self.ws = sh.worksheet(self.worksheet_name)

        self.slack_notifier = SlackNotifier()

    def _execute_with_retry(self, func, *args, **kwargs):
        backoff = INITIAL_BACKOFF

        for attempt in range(MAX_RETRIES):
            try:
                return func(*args, **kwargs)
            except APIError as e:
                is_quota_error = '429' in str(e) or 'Quota exceeded' in str(e)

                if is_quota_error:
                    if attempt < MAX_RETRIES - 1:
                        wait_time = min(backoff * (2 ** attempt), MAX_BACKOFF)
                        logger.warning(f"APIクォータ超過。{wait_time}秒待機後にリトライします（{attempt + 1}/{MAX_RETRIES}）")
                        time.sleep(wait_time)
                    else:
                        logger.error(f"最大リトライ回数に達しました: {e}")
                        raise
                else:
                    raise
            except Exception as e:
                logger.error(f"予期しないエラー: {e}")
                raise

    @staticmethod
    def _find_header_columns(header_row: list[str]) -> dict[str, int]:
        col_map: dict[str, int] = {}
        for idx, cell in enumerate(header_row):
            stripped = cell.strip()
            if stripped in HEADER_NAMES:
                col_map[stripped] = idx
        missing = [name for name in HEADER_NAMES if name not in col_map]
        if missing:
            raise ValueError(f"ヘッダーに必要な列が見つかりません: {missing}")
        return col_map

    @staticmethod
    def _extract_unshipped_rows(
        all_data: list[list[str]], col_map: dict[str, int]
    ) -> list[dict]:
        status_col = col_map["ステータス"]
        order_col = col_map["注文番号"]
        arrival_col = col_map["到着日"]
        rows: list[dict] = []
        for i in range(HEADER_ROW_INDEX + 1, len(all_data)):
            row = all_data[i]
            if len(row) <= max(status_col, order_col, arrival_col):
                continue
            status = row[status_col].strip()
            arrival = row[arrival_col].strip()
            order_raw = row[order_col].strip()
            if status != "未発送":
                continue
            if arrival and arrival != "#N/A":
                continue
            if not order_raw:
                continue
            order_numbers = [o.strip() for o in order_raw.split("\n") if o.strip()]
            rows.append({
                "row_index": i,
                "order_numbers": order_numbers,
                "sheet_row": i + 1,
            })
        return rows

    def get_unshipped_rows(self) -> list[dict]:
        all_data = self._execute_with_retry(self.ws.get_all_values)
        if len(all_data) <= HEADER_ROW_INDEX:
            logger.warning("ヘッダー行が見つかりません")
            return []
        header = all_data[HEADER_ROW_INDEX]
        col_map = self._find_header_columns(header)
        rows = self._extract_unshipped_rows(all_data, col_map)
        logger.info(f"未発送かつ到着日未記入の行: {len(rows)}件")
        return rows
