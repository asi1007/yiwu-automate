from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

SEARCH_INPUT = 'input[placeholder="注文番号 / 商品名 / 店舗名 / SKU"]'
ORDER_ROW = "tr.relative"
ALL_TAB_LABEL = "全て"
# 検索ボタンは2つある。1つ目は商品名検索、2つ目が注文検索
SEARCH_BUTTON_INDEX = 1
SETTLE_SECONDS = 4

_STATUS_LABELS = (
    "対応待ち", "対応中", "支払い待ち", "支払い済み", "分割払い",
    "入荷待ち", "受取済み", "受領済み", "対応完了", "キャンセル",
)
# 追跡番号の後ろにボタンの文言がそのまま続くので、そこで切る
_TRACKING_STOP = "カートに追加"


@dataclass(frozen=True)
class OrderStatus:
    order_number: str
    status: str = ""
    created_at: str = ""
    ordered_at: str = ""
    paid_at: str = ""
    warehoused_at: str = ""
    tracking: str = ""
    product_name: str = ""
    found: bool = True

    @classmethod
    def not_found(cls, order_number: str) -> "OrderStatus":
        return cls(order_number=order_number, status="(該当なし)", found=False)

    @property
    def is_paid(self) -> bool:
        return bool(self.paid_at)

    @property
    def is_warehoused(self) -> bool:
        return bool(self.warehoused_at)


def _timestamp(text: str, label: str) -> str:
    matched = re.search(rf"{label}：(\d{{4}}-\d{{2}}-\d{{2}}(?: \d{{2}}:\d{{2}}:\d{{2}})?)", text)
    return matched.group(1) if matched else ""


def parse_order_row(row_text: str) -> OrderStatus:
    text = re.sub(r"\s+", " ", row_text or "").strip()

    order_matched = re.search(r"注文番号：(\S+?)\s*コピー", text)
    order_number = order_matched.group(1) if order_matched else ""

    status = ""
    if order_matched:
        after = text[order_matched.end():]
        status = next((s for s in _STATUS_LABELS if after.startswith(s)), "")
    if not status:
        status = next((s for s in _STATUS_LABELS if s in text), "")

    tracking = ""
    tracking_matched = re.search(r"追跡番号：(.+)", text)
    if tracking_matched:
        tracking = tracking_matched.group(1).split(_TRACKING_STOP)[0].strip()

    return OrderStatus(
        order_number=order_number,
        status=status,
        created_at=_timestamp(text, "作成"),
        ordered_at=_timestamp(text, "注文"),
        paid_at=_timestamp(text, "引落"),
        warehoused_at=_timestamp(text, "入庫"),
        tracking=tracking,
        product_name=text.split("任意名")[0].strip()[:60],
    )


async def open_all_orders_tab(page, base_url: str) -> None:
    """注文一覧を開いて「全て」タブにする。

    既定のタブでは 1 行も出ない（状態別タブが絞り込んでいる）。
    """
    await page.goto(f"{base_url}/order/list?keys=order-list")
    await page.wait_for_load_state("networkidle")
    tab = page.locator("[role=tab], .el-tabs__item").filter(has_text=ALL_TAB_LABEL)
    await tab.first.click()
    await asyncio.sleep(SETTLE_SECONDS)


async def lookup_order(page, order_number: str) -> OrderStatus:
    """注文番号で検索して状態を返す。「全て」タブを開いた後に呼ぶこと。"""
    box = page.locator(SEARCH_INPUT).first
    await box.click()
    await box.fill("")
    # fill() だけでは検索に反映されない。キー入力として送る
    await box.type(order_number, delay=30)
    await page.locator('button:has-text("検索")').nth(SEARCH_BUTTON_INDEX).click()
    await asyncio.sleep(SETTLE_SECONDS)

    rows = page.locator(ORDER_ROW)
    if await rows.count() == 0:
        logger.warning("注文が見つかりません: %s", order_number)
        return OrderStatus.not_found(order_number)
    return parse_order_row(await rows.first.text_content() or "")


async def lookup_orders(order_numbers: list[str]) -> list[OrderStatus]:
    from playwright.async_api import async_playwright

    from yiwu_scraper import BuyerCentralScraper

    scraper = BuyerCentralScraper()
    results: list[OrderStatus] = []
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=scraper.headless)
        page = await (await browser.new_context()).new_page()
        try:
            await scraper.login(page)
            await scraper.dismiss_mandatory_announcements(page)
            await open_all_orders_tab(page, scraper.BASE_URL)
            for order_number in order_numbers:
                results.append(await lookup_order(page, order_number))
        finally:
            await browser.close()
    return results


def format_order_status(status: OrderStatus) -> str:
    if not status.found:
        return f"{status.order_number}: 該当なし"
    lines = [
        f"{status.order_number}: {status.status}",
        f"    作成 {status.created_at or '--'} / 注文 {status.ordered_at or '--'}"
        f" / 引落 {status.paid_at or '--'} / 入庫 {status.warehoused_at or '--'}",
    ]
    if status.tracking:
        lines.append(f"    追跡 {status.tracking}")
    if status.product_name:
        lines.append(f"    {status.product_name}")
    return "\n".join(lines)
