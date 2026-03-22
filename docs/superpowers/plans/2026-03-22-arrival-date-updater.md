# 到着日自動更新機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Google Sheets「仕入管理」シートの未発送行に対して、yp.buyer-central.com の入庫済みデータを照合し、到着日を自動更新する。

**Architecture:** 既存の `yiwu_scraper.py` を buyer-central.com 対応の `BuyerCentralScraper` に書き換え、`google_sheet.py` を新しいシート構造（仕入管理シート、ヘッダー名で動的列特定）に対応させる。`main()` で Sheets読み込み → スクレイピング → マッチング＆書き込みの順に実行。

**Tech Stack:** Python 3, Playwright (async), gspread, google-auth, python-dotenv

**Spec:** `docs/superpowers/specs/2026-03-22-arrival-date-updater-design.md`

---

## ファイル構成

| ファイル | 変更種別 | 責務 |
|---------|---------|------|
| `yiwu_scraper.py` | 書き換え | buyer-central.com へのログイン、入庫済み注文データのスクレイピング |
| `google_sheet.py` | 書き換え | 仕入管理シートの読み込み、到着日の書き込み |
| `slack_notifier.py` | 修正 | 通知文言を「入庫完了通知」に変更 |
| `.env` | 修正 | 環境変数をbuyer-central.com用に変更 |
| `tests/test_google_sheet.py` | 新規 | GSheet のマッチング・読み込みロジックのテスト |
| `tests/__init__.py` | 新規 | テストパッケージ初期化 |
| `tests/test_scraper.py` | 新規 | BuyerCentralScraper のデータ抽出ロジックのテスト |

---

### Task 1: .env の更新

**Files:**
- Modify: `.env`

- [ ] **Step 1: .env ファイルを更新**

旧環境変数を削除し、新しい環境変数に置き換える。

```bash
# 旧変数を削除、新変数を追加
# YIWU_USERNAME → BUYER_CENTRAL_EMAIL
# YIWU_PASSWORD → BUYER_CENTRAL_PASSWORD
# GOOGLE_SHEETS_SPREADSHEET_ID → 新しいID
# GOOGLE_SHEETS_WORKSHEET → 仕入管理
```

`.env` の内容（実際の値は auto-order/.env と既存 .env から取得）:
```
# buyer-central.com ログイン情報
BUYER_CENTRAL_EMAIL=<auto-order/.envのYIWUPASSPORT_EMAILの値>
BUYER_CENTRAL_PASSWORD=<auto-order/.envのYIWUPASSPORT_PASSWORDの値>

# Google Sheets 設定
GOOGLE_SHEETS_CREDENTIALS_JSON=service_account.json
GOOGLE_SHEETS_SPREADSHEET_ID=<仕入管理スプレッドシートのID>
GOOGLE_SHEETS_WORKSHEET=仕入管理

# Slack通知
SLACK_WEBHOOK_URL=<既存の.envのSLACK_WEBHOOK_URLの値>

# ブラウザ設定
HEADLESS=true
```

- [ ] **Step 2: コミット**

```bash
git add .env
git commit -m "chore: update .env for buyer-central.com migration"
```

---

### Task 2: slack_notifier.py の文言更新

**Files:**
- Modify: `slack_notifier.py:37-44`

- [ ] **Step 1: 通知文言を変更**

`slack_notifier.py` の `send_arrival_notification` メソッド内の文言を変更:

```python
# 変更前
"text": f"🚚 *中国事務所到着通知*",
# ...
"text": "🚚 中国事務所到着通知",

# 変更後
"text": f"📦 *入庫完了通知*",
# ...
"text": "📦 入庫完了通知",
```

また、モジュールおよびクラス・メソッドの docstring を全て削除する（CLAUDE.md の開発原則に従い、コード自体を自己説明的にする）。

- [ ] **Step 2: コミット**

```bash
git add slack_notifier.py
git commit -m "fix: update Slack notification message for buyer-central.com"
```

---

### Task 3: google_sheet.py の書き換え — 読み込みロジック

**Files:**
- Modify: `google_sheet.py`
- Create: `tests/test_google_sheet.py`

- [ ] **Step 1: tests ディレクトリと __init__.py を作成**

```bash
mkdir -p tests
touch tests/__init__.py
```

- [ ] **Step 2: テストファイルを作成 — ヘッダー検出と未発送行抽出のテスト**

`tests/test_google_sheet.py`:

```python
import pytest


SAMPLE_HEADER = [
    "備考", "行番号", "画像", "ASIN", "商品名", "ステータス",
    "購入日", "買付完了日", "到着日", "梱包依頼日", "発送日",
    "受領日", "", "", "", "状態", " 注文番号"
]

SAMPLE_DATA = [
    ["", "", "", "", ""], # row 1 (ラベル)
    ["", "", "", "", ""], # row 2 (ラベル)
    ["", "", "", "", ""], # row 3 (ラベル)
    SAMPLE_HEADER,        # row 4 (ヘッダー)
    # row 5: 未発送、到着日なし、注文番号あり
    ["", "5", "", "B0TEST1", "商品A", "未発送",
     "03/18", "", "", "", "",
     "", "", "", "", "", "P260318001YP806"],
    # row 6: 未発送、到着日あり（スキップ対象）
    ["", "6", "", "B0TEST2", "商品B", "未発送",
     "03/17", "", "03/20", "", "",
     "", "", "", "", "", "P260317003YP806"],
    # row 7: 未発送、到着日が#N/A（対象）
    ["", "7", "", "B0TEST3", "商品C", "未発送",
     "03/16", "", "#N/A", "", "",
     "", "", "", "", "", "P260316001YP806"],
    # row 8: 発送済み（スキップ対象）
    ["", "8", "", "B0TEST4", "商品D", "発送済み",
     "03/15", "", "", "", "",
     "", "", "", "", "", "P260315001YP806"],
    # row 9: 未発送、複数注文番号
    ["", "9", "", "B0TEST5", "商品E", "未発送",
     "03/14", "", "", "", "",
     "", "", "", "", "", "P260314001YP806\nP260314002YP806"],
]


class TestFindHeaderColumns:
    def test_finds_status_order_arrival_columns(self):
        from google_sheet import GSheet
        col_map = GSheet._find_header_columns(SAMPLE_HEADER)
        assert col_map["ステータス"] == 5
        assert col_map["注文番号"] == 16
        assert col_map["到着日"] == 8


class TestExtractUnshippedRows:
    def test_extracts_unshipped_rows_without_arrival_date(self):
        from google_sheet import GSheet
        col_map = {"ステータス": 5, "注文番号": 16, "到着日": 8}
        rows = GSheet._extract_unshipped_rows(SAMPLE_DATA, col_map)
        # row 5(到着日空), row 7(#N/A), row 9(到着日空) の3行が対象
        assert len(rows) == 3
        assert rows[0]["row_index"] == 5  # 0-indexed in SAMPLE_DATA, 実際の行番号は6
        assert rows[0]["order_numbers"] == ["P260318001YP806"]

    def test_skips_rows_with_arrival_date(self):
        from google_sheet import GSheet
        col_map = {"ステータス": 5, "注文番号": 16, "到着日": 8}
        rows = GSheet._extract_unshipped_rows(SAMPLE_DATA, col_map)
        order_nums = [r["order_numbers"][0] for r in rows]
        assert "P260317003YP806" not in order_nums

    def test_handles_multiple_order_numbers(self):
        from google_sheet import GSheet
        col_map = {"ステータス": 5, "注文番号": 16, "到着日": 8}
        rows = GSheet._extract_unshipped_rows(SAMPLE_DATA, col_map)
        multi_row = [r for r in rows if len(r["order_numbers"]) > 1][0]
        assert multi_row["order_numbers"] == ["P260314001YP806", "P260314002YP806"]
```

- [ ] **Step 3: テストを実行して失敗を確認**

Run: `python -m pytest tests/test_google_sheet.py -v`
Expected: FAIL（`_find_header_columns` と `_extract_unshipped_rows` が未実装）

- [ ] **Step 4: google_sheet.py を書き換え — 不要なコードを削除し、読み込みロジックを実装**

`google_sheet.py` の全体を書き換え。以下を実装:

- 不要な定数を削除: `COL_ORDER_ID`, `COL_ARRIVAL_DATE`, `COL_IMAGE`, `COL_ITEM_NAME`, `COL_COLOR_SIZE`, `DEFAULT_NUM_COLS`, `BATCH_SIZE`, `BATCH_WAIT_TIME`
- 不要なメソッドを削除: `write`, `_should_update_row`, `_update_existing_order`, `_add_new_order`, `update_table_range`, `get_table_id`, `_get_num_cols`
- 不要な import を削除: `googleapiclient.discovery`, `googleapiclient.errors`
- `self.service` と `self.sheet_id` の初期化コードを削除
- 全ての docstring を削除（CLAUDE.md の開発原則に準拠）
- ヘッダー行定数を追加: `HEADER_ROW_INDEX = 3`（0始まり、4行目）
- `_find_header_columns(header_row: list[str]) -> dict[str, int]`: ヘッダー名「ステータス」「注文番号」「到着日」の列インデックスを返す静的メソッド。注文番号はスペース付き「 注文番号」にも対応（strip して比較）。
- `_extract_unshipped_rows(all_data: list[list[str]], col_map: dict[str, int]) -> list[dict]`: 未発送かつ到着日が空（空文字 or `#N/A`）の行を抽出する静的メソッド。各行を `{"row_index": int, "order_numbers": list[str], "sheet_row": int}` として返す。`row_index` は `all_data` 内のインデックス、`sheet_row` はシート上の行番号（1始まり）。注文番号は改行で分割。
- `get_unshipped_rows() -> list[dict]`: 上記を組み合わせた公開メソッド。

```python
HEADER_ROW_INDEX = 3
HEADER_NAMES = ["ステータス", "注文番号", "到着日"]

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
```

- [ ] **Step 5: テストを実行して通過を確認**

Run: `python -m pytest tests/test_google_sheet.py -v`
Expected: PASS (3 tests)

- [ ] **Step 6: コミット**

```bash
git add google_sheet.py tests/__init__.py tests/test_google_sheet.py
git commit -m "feat: rewrite google_sheet.py with header-based column detection and unshipped row extraction"
```

---

### Task 4: google_sheet.py — マッチング＆書き込みロジック

**Files:**
- Modify: `google_sheet.py`
- Modify: `tests/test_google_sheet.py`

- [ ] **Step 1: マッチングロジックのテストを追加**

`tests/test_google_sheet.py` に追加:

```python
class TestMatchOrders:
    def test_single_order_match(self):
        from google_sheet import GSheet
        unshipped = [
            {"row_index": 5, "order_numbers": ["P260318001YP806"], "sheet_row": 6},
        ]
        warehoused = {"P260318001YP806": "2026-03-20 14:53:44"}
        matches = GSheet._match_orders(unshipped, warehoused)
        assert len(matches) == 1
        assert matches[0]["sheet_row"] == 6
        assert matches[0]["arrival_date"] == "03/20"

    def test_multi_order_all_matched(self):
        from google_sheet import GSheet
        unshipped = [
            {"row_index": 9, "order_numbers": ["P260314001YP806", "P260314002YP806"], "sheet_row": 10},
        ]
        warehoused = {
            "P260314001YP806": "2026-03-18 10:00:00",
            "P260314002YP806": "2026-03-20 15:00:00",
        }
        matches = GSheet._match_orders(unshipped, warehoused)
        assert len(matches) == 1
        assert matches[0]["arrival_date"] == "03/20"  # 最も遅い日付

    def test_multi_order_partial_match_skipped(self):
        from google_sheet import GSheet
        unshipped = [
            {"row_index": 9, "order_numbers": ["P260314001YP806", "P260314002YP806"], "sheet_row": 10},
        ]
        warehoused = {"P260314001YP806": "2026-03-18 10:00:00"}
        matches = GSheet._match_orders(unshipped, warehoused)
        assert len(matches) == 0

    def test_no_match(self):
        from google_sheet import GSheet
        unshipped = [
            {"row_index": 5, "order_numbers": ["P260399999YP806"], "sheet_row": 6},
        ]
        warehoused = {"P260318001YP806": "2026-03-20 14:53:44"}
        matches = GSheet._match_orders(unshipped, warehoused)
        assert len(matches) == 0

    def test_date_format_mm_dd(self):
        from google_sheet import GSheet
        unshipped = [
            {"row_index": 5, "order_numbers": ["P260101001YP806"], "sheet_row": 6},
        ]
        warehoused = {"P260101001YP806": "2026-01-05 09:30:00"}
        matches = GSheet._match_orders(unshipped, warehoused)
        assert matches[0]["arrival_date"] == "01/05"
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `python -m pytest tests/test_google_sheet.py::TestMatchOrders -v`
Expected: FAIL（`_match_orders` が未実装）

- [ ] **Step 3: マッチングロジックを実装**

`google_sheet.py` に追加:

```python
from datetime import datetime

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
```

- [ ] **Step 4: テストを実行して通過を確認**

Run: `python -m pytest tests/test_google_sheet.py::TestMatchOrders -v`
Expected: PASS (5 tests)

- [ ] **Step 5: `update_arrival_dates` メソッドを実装**

```python
from gspread.utils import rowcol_to_a1

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
```

- [ ] **Step 6: コミット**

```bash
git add google_sheet.py tests/test_google_sheet.py
git commit -m "feat: add order matching logic and arrival date update method"
```

---

### Task 5: yiwu_scraper.py の書き換え — BuyerCentralScraper

**Files:**
- Modify: `yiwu_scraper.py`
- Create: `tests/test_scraper.py`

- [ ] **Step 1: データ抽出ヘルパーのテストを作成**

`tests/test_scraper.py`:

```python
import pytest


class TestParseWarehouseDate:
    def test_extracts_warehouse_date(self):
        from yiwu_scraper import BuyerCentralScraper
        date_text = "作成：2026-03-18 21:41:34注文：2026-03-19 11:19:25引落：2026-03-19 16:21:38入庫：2026-03-20 14:53:44"
        result = BuyerCentralScraper._parse_warehouse_date(date_text)
        assert result == "2026-03-20 14:53:44"

    def test_returns_empty_when_no_warehouse_date(self):
        from yiwu_scraper import BuyerCentralScraper
        date_text = "作成：2026-03-18 21:41:34注文：2026-03-19 11:19:25"
        result = BuyerCentralScraper._parse_warehouse_date(date_text)
        assert result == ""

    def test_handles_empty_string(self):
        from yiwu_scraper import BuyerCentralScraper
        result = BuyerCentralScraper._parse_warehouse_date("")
        assert result == ""
```

- [ ] **Step 2: テストを実行して失敗を確認**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: FAIL（`BuyerCentralScraper` が未定義）

- [ ] **Step 3: yiwu_scraper.py を書き換え**

既存の `YiwuScraper` と `DataProcessor` を全て削除し、`BuyerCentralScraper` を実装:

全ての docstring を削除する（CLAUDE.md の開発原則に準拠）。

```python
import asyncio
import json
import re
import logging
import sys
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import google_sheet

load_dotenv()


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }
        if record.exc_info and record.exc_info[0]:
            log_entry["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_entry, ensure_ascii=False)


handler = logging.StreamHandler(sys.stdout)
handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[handler])
logger = logging.getLogger(__name__)


class BuyerCentralScraper:
    BASE_URL = "https://yp.buyer-central.com"
    LOGIN_URL = f"{BASE_URL}/login"
    ORDER_LIST_URL = f"{BASE_URL}/order/list?status=6&keys=order-list"

    def __init__(self):
        self.email = os.environ.get("BUYER_CENTRAL_EMAIL")
        self.password = os.environ.get("BUYER_CENTRAL_PASSWORD")
        headless_str = os.environ.get("HEADLESS", "true").lower()
        self.headless = headless_str in ("true", "1", "yes")
        if not self.email or not self.password:
            raise ValueError(
                "BUYER_CENTRAL_EMAIL と BUYER_CENTRAL_PASSWORD の環境変数を設定してください"
            )

    async def login(self, page) -> None:
        logger.info("ログインページにアクセス中...")
        await page.goto(self.LOGIN_URL)
        await page.wait_for_load_state("networkidle")
        await page.fill(
            'input[placeholder="アカウントをご入力してください"]', self.email
        )
        await page.fill(
            'input[placeholder="パスワードをご入力してください"]', self.password
        )
        await page.click('button:has-text("ログイン")')
        try:
            await page.wait_for_url("**/home", timeout=10000)
            logger.info("ログイン完了")
        except Exception:
            raise RuntimeError("ログインに失敗しました。認証情報を確認してください。")

    @staticmethod
    def _parse_warehouse_date(date_text: str) -> str:
        match = re.search(r"入庫：(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", date_text)
        return match.group(1) if match else ""

    async def scrape_page_orders(self, page) -> dict[str, str]:
        orders: dict[str, str] = {}
        blocks = page.locator("tr.relative")
        count = await blocks.count()
        for i in range(count):
            block = blocks.nth(i)
            order_num_el = block.locator(".hover-copy-box span:first-child")
            if await order_num_el.count() == 0:
                continue
            order_num = (await order_num_el.first.text_content() or "").strip()
            if not order_num:
                continue
            tds = block.locator("td.data-td")
            td_count = await tds.count()
            if td_count < 4:
                continue
            date_td = tds.nth(3)
            date_text = (await date_td.text_content() or "").strip()
            warehouse_date = self._parse_warehouse_date(date_text)
            if warehouse_date:
                orders[order_num] = warehouse_date
        return orders

    async def _scrape_page_with_retry(self, page, max_retries: int = 3) -> dict[str, str]:
        for attempt in range(max_retries):
            try:
                await page.wait_for_selector("tr.relative", timeout=15000)
                return await self.scrape_page_orders(page)
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"ページスクレイピング失敗。リトライ ({attempt + 1}/{max_retries}): {e}")
                    await asyncio.sleep(2)
                else:
                    logger.error(f"ページスクレイピング失敗。最大リトライ回数に到達: {e}")
                    raise

    async def scrape_all_pages(self, page) -> dict[str, str]:
        all_orders: dict[str, str] = {}
        page_num = 1
        while True:
            logger.info(f"ページ {page_num} をスクレイピング中...")
            page_orders = await self._scrape_page_with_retry(page)
            all_orders.update(page_orders)
            logger.info(f"  {len(page_orders)}件の注文を取得")

            next_btn = page.locator(
                'button:has-text("keyboard_arrow_right"):not([disabled])'
            )
            if await next_btn.count() == 0:
                break
            # 現在のブロック数を記憶
            old_first = page.locator("tr.relative .hover-copy-box span:first-child").first
            old_text = (await old_first.text_content() or "").strip()
            await next_btn.click()
            # 新しいデータの読み込みを待機（先頭注文番号が変わるまで）
            for _ in range(30):
                await asyncio.sleep(0.5)
                new_first = page.locator("tr.relative .hover-copy-box span:first-child").first
                if await new_first.count() > 0:
                    new_text = (await new_first.text_content() or "").strip()
                    if new_text != old_text:
                        break
            page_num += 1

        logger.info(f"全ページスクレイピング完了: 合計 {len(all_orders)}件")
        return all_orders

    async def run(self) -> dict[str, str]:
        logger.info(f"スクレイピング開始... (Headless: {self.headless})")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()
            await self.login(page)
            await page.goto(self.ORDER_LIST_URL)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            orders = await self.scrape_all_pages(page)
            await browser.close()
        return orders


async def main():
    logger.info("=== 到着日自動更新 開始 ===")

    sheet = google_sheet.GSheet()
    unshipped_rows = sheet.get_unshipped_rows()
    if not unshipped_rows:
        logger.info("更新対象の行がありません")
        logger.info("=== 到着日自動更新 完了 ===")
        return

    scraper = BuyerCentralScraper()
    warehoused_orders = await scraper.run()
    if not warehoused_orders:
        logger.warning("入庫済み注文が見つかりません")
        logger.info("=== 到着日自動更新 完了 ===")
        return

    logger.info(f"未発送行: {len(unshipped_rows)}件, 入庫済み注文: {len(warehoused_orders)}件")
    updated = sheet.update_arrival_dates(unshipped_rows, warehoused_orders)
    logger.info(f"=== 到着日自動更新 完了 ({updated}件更新) ===")


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 4: テストを実行して通過を確認**

Run: `python -m pytest tests/test_scraper.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: コミット**

```bash
git add yiwu_scraper.py tests/test_scraper.py
git commit -m "feat: replace YiwuScraper with BuyerCentralScraper for buyer-central.com"
```

---

### Task 6: 統合テスト — ローカル実行

**Files:**
- (なし — 既存ファイルを使用)

- [ ] **Step 1: HEADLESS=false で実行して動作確認**

`.env` で一時的に `HEADLESS=false` に変更し、ブラウザの動作を目視確認:

```bash
cd /Users/wadaatsushi/Documents/automation/automate-yiwu
python yiwu_scraper.py
```

確認ポイント:
- buyer-central.com へのログインが成功するか
- 入庫済みタブのデータが全ページ取得できるか
- Google Sheets の未発送行とのマッチングが正しく行われるか
- 到着日がMM/DD形式で正しく書き込まれるか
- Slack通知が送信されるか

- [ ] **Step 2: HEADLESS=true に戻す**

`.env` の `HEADLESS=true` に戻す。

- [ ] **Step 3: 全テストを実行**

Run: `python -m pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 4: コミット**

```bash
git add -A
git commit -m "test: verify integration with buyer-central.com and Google Sheets"
```
