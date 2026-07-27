import os
import re
import logging
import time
from datetime import datetime, date
import gspread
from gspread.exceptions import APIError
from gspread.utils import rowcol_to_a1
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
HEADER_NAMES = ["状態", "注文番号", "到着日"]
OVERDUE_COL_NAMES = ["商品名", "購入日", "到着日", "状態", "注文番号"]
OVERDUE_THRESHOLD_DAYS = 14


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
        status_col = col_map["状態"]
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

    @staticmethod
    def _complete_year(mmdd: str, today: date) -> date | None:
        match = re.match(r"^\s*(\d{1,2})[-/](\d{1,2})\s*$", mmdd)
        if not match:
            return None
        month, day = int(match.group(1)), int(match.group(2))
        try:
            purchased = date(today.year, month, day)
        except ValueError:
            return None
        if purchased > today:
            purchased = date(today.year - 1, month, day)
        return purchased

    @staticmethod
    def _extract_overdue_orders(
        all_data: list[list[str]],
        cols: dict[str, int],
        today: date,
        threshold_days: int,
    ) -> list[dict]:
        status_col = cols["状態"]
        arrival_col = cols["到着日"]
        order_col = cols["注文番号"]
        purchase_col = cols["購入日"]
        name_col = cols["商品名"]
        max_col = max(status_col, arrival_col, order_col, purchase_col, name_col)
        seen: set[str] = set()
        overdue: list[dict] = []
        for i in range(HEADER_ROW_INDEX + 1, len(all_data)):
            row = all_data[i]
            if len(row) <= max_col:
                continue
            if row[status_col].strip() != "未発送":
                continue
            arrival = row[arrival_col].strip()
            if arrival and arrival != "#N/A":
                continue
            order_raw = row[order_col].strip()
            if not order_raw:
                continue
            purchased = GSheet._complete_year(row[purchase_col], today)
            if purchased is None:
                continue
            days_elapsed = (today - purchased).days
            if days_elapsed <= threshold_days:
                continue
            order_number = order_raw.split("\n")[0].strip()
            if order_number in seen:
                continue
            seen.add(order_number)
            overdue.append({
                "order_number": order_number,
                "product_name": row[name_col].strip(),
                "purchase_date": row[purchase_col].strip(),
                "days_elapsed": days_elapsed,
            })
        return overdue

    def get_overdue_orders(
        self, today: date, threshold_days: int = OVERDUE_THRESHOLD_DAYS
    ) -> list[dict]:
        all_data = getattr(self, "_all_data", None)
        if all_data is None:
            all_data = self._execute_with_retry(self.ws.get_all_values)
        header = all_data[HEADER_ROW_INDEX]
        cols = {}
        for name in OVERDUE_COL_NAMES:
            for idx, cell in enumerate(header):
                if cell.strip() == name:
                    cols[name] = idx
                    break
        missing = [n for n in OVERDUE_COL_NAMES if n not in cols]
        if missing:
            raise ValueError(f"ヘッダーに必要な列が見つかりません: {missing}")
        overdue = self._extract_overdue_orders(all_data, cols, today, threshold_days)
        overdue.sort(key=lambda o: o["days_elapsed"], reverse=True)
        logger.info(f"発注から{threshold_days}日超の未到着: {len(overdue)}件")
        return overdue

    def get_unshipped_rows(self) -> list[dict]:
        self._all_data = self._execute_with_retry(self.ws.get_all_values)
        if len(self._all_data) <= HEADER_ROW_INDEX:
            logger.warning("ヘッダー行が見つかりません")
            return []
        header = self._all_data[HEADER_ROW_INDEX]
        self._col_map = self._find_header_columns(header)
        rows = self._extract_unshipped_rows(self._all_data, self._col_map)
        logger.info(f"未発送かつ到着日未記入の行: {len(rows)}件")
        return rows

    def get_all_order_numbers(self) -> set[str]:
        all_data = getattr(self, "_all_data", None)
        col_map = getattr(self, "_col_map", None)
        if all_data is None or col_map is None:
            all_data = self._execute_with_retry(self.ws.get_all_values)
            header = all_data[HEADER_ROW_INDEX]
            col_map = self._find_header_columns(header)
        order_col = col_map["注文番号"]
        order_numbers: set[str] = set()
        for i in range(HEADER_ROW_INDEX + 1, len(all_data)):
            row = all_data[i]
            if len(row) <= order_col:
                continue
            order_raw = row[order_col].strip()
            if not order_raw:
                continue
            for o in order_raw.split("\n"):
                o = o.strip()
                if o:
                    order_numbers.add(o)
        return order_numbers

    @staticmethod
    def _match_orders(
        unshipped_rows: list[dict], warehoused_orders: dict[str, str]
    ) -> list[dict]:
        matches: list[dict] = []
        for row in unshipped_rows:
            order_numbers = row["order_numbers"]
            matched_dates: list[str] = []
            all_matched = True
            for order_num in order_numbers:
                if order_num in warehoused_orders:
                    matched_dates.append(warehoused_orders[order_num])
                else:
                    all_matched = False
                    break
            if not all_matched or not matched_dates:
                continue
            latest_dt = max(
                datetime.strptime(d, "%Y-%m-%d %H:%M:%S") for d in matched_dates
            )
            arrival_date = latest_dt.strftime("%m/%d")
            matches.append({
                "sheet_row": row["sheet_row"],
                "order_numbers": order_numbers,
                "arrival_date": arrival_date,
            })
        return matches

    def update_arrival_dates(
        self, unshipped_rows: list[dict], warehoused_orders: dict[str, str]
    ) -> int:
        matches = self._match_orders(unshipped_rows, warehoused_orders)
        if not matches:
            logger.warning("マッチする注文がありません")
            return 0

        all_data = self._execute_with_retry(self.ws.get_all_values)
        header = all_data[HEADER_ROW_INDEX]
        col_map = self._find_header_columns(header)

        updated_count = 0
        for match in matches:
            cell = rowcol_to_a1(match["sheet_row"], col_map["到着日"] + 1)
            self._execute_with_retry(self.ws.update, cell, [[match["arrival_date"]]])
            logger.info(
                f"[更新] 行{match['sheet_row']}: "
                f"注文番号={','.join(match['order_numbers'])}, "
                f"到着日={match['arrival_date']}"
            )
            self.slack_notifier.send_arrival_notification(
                ",".join(match["order_numbers"]), match["arrival_date"]
            )
            updated_count += 1

        logger.info(f"到着日更新完了: {updated_count}件")
        return updated_count
