import asyncio
import json
import re
import logging
import sys
from datetime import datetime
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import google_sheet
import write_daily_note

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
    ORDER_LIST_URL = f"{BASE_URL}/order/list?keys=order-list"

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

    @staticmethod
    async def _extract_product_name(block) -> str:
        td0 = block.locator("td.data-td").first
        td0_text = (await td0.text_content() or "").strip()
        name = re.split(r"任意名", td0_text)[0].strip()
        return name

    async def scrape_page_orders(self, page) -> dict[str, dict[str, str]]:
        orders: dict[str, dict[str, str]] = {}
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
            row_text = (await block.text_content() or "").strip()
            warehouse_date = self._parse_warehouse_date(row_text)
            product_name = await self._extract_product_name(block)
            orders[order_num] = {
                "date": warehouse_date,
                "product_name": product_name,
            }
        return orders

    @staticmethod
    def _fill_missing_dates(
        orders: dict[str, dict[str, str]], today: str
    ) -> None:
        for info in orders.values():
            if not info["date"]:
                info["date"] = today

    async def _scrape_page_with_retry(self, page, max_retries: int = 3) -> dict[str, dict[str, str]]:
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

    async def scrape_all_pages(self, page) -> dict[str, dict[str, str]]:
        all_orders: dict[str, dict[str, str]] = {}
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
            old_first = page.locator("tr.relative .hover-copy-box span:first-child").first
            old_text = (await old_first.text_content() or "").strip()
            await next_btn.click()
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

    RECEIVED_TAB_PATTERNS = [
        r"^(受取済み|入庫済み)\(\d+\)$",
        r"^受領中\(\d+\)$",
    ]

    async def _scrape_tab(self, page, tab_pattern: str) -> dict[str, dict[str, str]]:
        tab = page.locator(f"text=/{tab_pattern}/").first
        if await tab.count() == 0:
            logger.info(f"タブが見つかりません（スキップ）: {tab_pattern}")
            return {}
        await tab.click()
        await page.wait_for_load_state("networkidle")
        await asyncio.sleep(3)
        return await self.scrape_all_pages(page)

    async def run(self) -> dict[str, dict[str, str]]:
        logger.info(f"スクレイピング開始... (Headless: {self.headless})")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context()
            page = await context.new_page()
            await self.login(page)
            await page.goto(self.ORDER_LIST_URL)
            await page.wait_for_load_state("networkidle")
            await asyncio.sleep(3)
            orders: dict[str, dict[str, str]] = {}
            for tab_pattern in self.RECEIVED_TAB_PATTERNS:
                orders.update(await self._scrape_tab(page, tab_pattern))
            await browser.close()
        today = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self._fill_missing_dates(orders, today)
        return orders


def _format_overdue_line(order: dict) -> str:
    return (
        f"- {order['order_number']} {order['product_name'][:40]} "
        f"購入 {order['purchase_date']}"
        f"（{order['days_elapsed']}日経過・未到着）"
    )


def _report_overdue_orders(sheet: google_sheet.GSheet) -> None:
    today = datetime.now().date()
    overdue = sheet.get_overdue_orders(today)
    if not overdue:
        return
    lines = [_format_overdue_line(order) for order in overdue]
    for line in lines:
        logger.warning(f"[到着遅延] {line}")
    try:
        path = write_daily_note.append_under_section(
            "## Claude Code ログ",
            f"到着遅延アラート ({len(overdue)}件)",
            lines,
            datetime.now(),
        )
        logger.info(f"到着遅延アラートを daily note に追記しました: {path}")
    except Exception as e:
        logger.error(f"daily note への追記に失敗しました: {e}")


async def main():
    logger.info("=== 到着日自動更新 開始 ===")

    sheet = google_sheet.GSheet()
    unshipped_rows = sheet.get_unshipped_rows()
    _report_overdue_orders(sheet)
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

    sheet_order_numbers = sheet.get_all_order_numbers()
    not_in_sheet = sorted(set(warehoused_orders.keys()) - sheet_order_numbers)
    if not_in_sheet:
        logger.info(f"シートに存在しない入庫済み注文: {len(not_in_sheet)}件")
        for order_num in not_in_sheet:
            info = warehoused_orders[order_num]
            logger.info(
                f"  [シート未登録] {order_num} "
                f"(入庫日: {info['date']}, 商品名: {info['product_name']})"
            )

    order_dates = {k: v["date"] for k, v in warehoused_orders.items()}
    updated = sheet.update_arrival_dates(unshipped_rows, order_dates)
    logger.info(f"=== 到着日自動更新 完了 ({updated}件更新) ===")


if __name__ == "__main__":
    asyncio.run(main())
