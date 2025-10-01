"""
イーウーパスポート スクレイピングアプリケーション
"""
import asyncio
import logging
from urllib.parse import urljoin
from playwright.async_api import async_playwright
import os
from dotenv import load_dotenv
import google_sheet

# 環境変数ファイルを読み込み
load_dotenv()

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


class YiwuScraper:
    """イーウーパスポート スクレイピングクラス"""
    
    def __init__(self):
        self.username = os.environ.get("YIWU_USERNAME")
        self.password = os.environ.get("YIWU_PASSWORD")
        self.base_url = "https://yiwupassport.jp"
        self.login_url = f"{self.base_url}/login"
        self.inquiry_url = f"{self.base_url}/inquiry"
        
        if not self.username or not self.password:
            raise ValueError("YIWU_USERNAME と YIWU_PASSWORD の環境変数を設定してください")
    
    async def login(self, page):
        """ログイン処理"""
        try:
            logger.info("ログインページにアクセス中...")
            await page.goto(self.login_url)
            await page.fill('input[name="email"]', self.username)
            await page.fill('input[name="password"]', self.password)
            await page.click('button[type="submit"]')
            await page.wait_for_load_state("networkidle")
            logger.info("ログイン完了")
        except Exception as e:
            logger.error(f"ログインエラー: {e}")
            raise
    
    async def navigate_to_order_history(self, page):
        """注文状況照会ページに移動"""
        try:
            logger.info("注文状況照会ページに移動中...")
            inquiry_link = page.locator('a:has-text("注文状況照会"), a[href="/inquiry"], a[href="https://yiwupassport.jp/inquiry"]').first
            await inquiry_link.wait_for(state="visible", timeout=10000)
            await inquiry_link.click()
            await page.wait_for_load_state("networkidle")
            logger.info("注文状況照会ページに移動完了")
        except Exception as e:
            logger.error(f"注文状況照会ページ移動エラー: {e}")
            raise
    
    async def extract_order_data(self, cols):
        """注文データを抽出"""
        status = (await cols[0].text_content() or '').strip()
        order_id = (await cols[1].text_content() or '').strip() 
        ordered_at = (await cols[2].text_content() or '').strip()
        estimated_at = (await cols[3].text_content() or '').strip()
        purchased_at = (await cols[4].text_content() or '').strip()
        arrived_china_at = (await cols[5].text_content() or '').strip()
        shippable_at = (await cols[6].text_content() or '').strip()
        detail_link_el = await cols[7].query_selector('a')
        detail_link = await detail_link_el.get_attribute('href') if detail_link_el else ''
        
        return {
            'status': status,
            'orderId': order_id,
            'orderedAt': ordered_at,
            'estimatedAt': estimated_at,
            'purchasedAt': purchased_at,
            'arrivedChinaAt': arrived_china_at,
            'shippableAt': shippable_at,
            'detailLink': detail_link
        }
    
    async def extract_item_data(self, cols, current_order):
        """アイテムデータを抽出"""
        if not current_order:
            return []
        
        inner_table = await cols[0].query_selector('table')
        if not inner_table:
            return []
        
        items = []
        inner_rows = await inner_table.query_selector_all('tbody > tr')
        
        for i_tr in inner_rows:
            i_tds = await i_tr.query_selector_all(':scope > td')
            if len(i_tds) < 2:
                continue
                
            # 画像URL取得
            img_el = await i_tds[0].query_selector('img')
            if img_el:
                image_url = await img_el.get_attribute('src') or ''
            else:
                txt = (await i_tds[0].text_content() or '').strip()
                image_url = '' if txt == '画像無し' else ''
                
            # 商品名取得
            item_name = (await i_tds[1].text_content() or '').strip()
            
            # 結果に追加
            order_data = current_order.copy()
            order_data.update({
                'imageUrl': image_url,
                'itemName': item_name
            })
            items.append(order_data)
        
        return items
    
    async def extract_product_links_from_context(self, context, link):
        """詳細ページから商品リンクを抽出"""
        page = await context.new_page()
        try:
            await page.goto(link)
            await page.wait_for_load_state("networkidle")
            
            # 商品情報テーブルを探す
            tables = page.locator('table.table.table-bordered.table-striped.table-responsive')
            table = tables.nth(0)
            rows = table.locator('tbody > tr')
            row = rows.nth(2)
            cells = row.locator('td > a')
            link = await cells.nth(0).get_attribute('href')
            return link
        finally:
            await page.close()
    
    async def has_next_page(self, page, next_link):
        """次ページの存在確認"""
        if await next_link.count() == 0:
            return False
        
        next_li = page.locator('ul.pagination li').filter(has=page.locator('a[rel="next"]')).first
        li_class = await next_li.get_attribute('class') or ''
        return 'disabled' not in li_class
    
    async def scrape_page_data(self, page):
        """現在ページのデータをスクレイピング"""
        await page.wait_for_selector('table.table.table-bordered.table-striped.table-responsive', timeout=10000)
        
        main_table = await page.query_selector('table.table.table-bordered.table-striped.table-responsive')
        page_results = []
        tbody = await main_table.query_selector('tbody')
        rows = await tbody.query_selector_all(':scope > tr')
        current_order = None
        
        for tr in rows:
            cols = await tr.query_selector_all(':scope > td')
            
            # 受注行（注文概要）の処理
            if len(cols) >= 8 and not await cols[0].get_attribute('colspan'):
                current_order = await self.extract_order_data(cols)
            
            # アイテム行の処理
            elif len(cols) == 1 and await cols[0].get_attribute('colspan'):
                items = await self.extract_item_data(cols, current_order)
                page_results.extend(items)
        
        return page_results
    
    async def scrape_all_pages(self, page):
        """全ページをスクレイピング"""
        results = []
        
        while True:
            page_results = await self.scrape_page_data(page)
            results.extend(page_results)
            
            next_link = page.locator('ul.pagination a[rel="next"]')
            if not await self.has_next_page(page, next_link):
                break
            
            # href 取得と検証
            next_href = await next_link.first.get_attribute('href')
            if not next_href or next_href.strip() == '#' or next_href.strip().lower().startswith('javascript'):
                break
            
            next_url = urljoin(page.url, next_href)
            await page.goto(next_url)
            await page.wait_for_load_state("networkidle")
        
        return results
    
    async def enrich_with_product_links(self, context, results):
        """商品リンクでデータを拡張"""
        tasks = []
        for r in results:
            detail_link = r.get("detailLink", "")
            if detail_link:
                task = self.extract_product_links_from_context(context, detail_link)
                tasks.append((detail_link, task))
        
        # 全てのタスクを並列実行
        results_list = await asyncio.gather(*[task for _, task in tasks], return_exceptions=True)
        
        # 結果を各注文に追加
        for i, (detail_link, _) in enumerate(tasks):
            try:
                product_link = results_list[i]
                if isinstance(product_link, Exception):
                    logger.warning(f"詳細ページ {detail_link} の処理でエラー: {product_link}")
                    product_link = ""
                
                # 該当する注文にリンクを追加
                for r in results:
                    if r.get("detailLink") == detail_link:
                        r["orderLink"] = product_link
            except Exception as e:
                logger.error(f"詳細ページ {detail_link} の処理でエラー: {e}")
                for r in results:
                    if r.get("detailLink") == detail_link:
                        r["orderLink"] = ""
    
    async def run(self):
        """メイン実行メソッド"""
        try:
            logger.info("スクレイピング開始...")
            async with async_playwright() as p:
                # Cloud Runでは headless=True が必要
                browser = await p.chromium.launch(headless=False)
                context = await browser.new_context()
                page = await context.new_page()
                
                # ログインとページ移動
                await self.login(page)
                await self.navigate_to_order_history(page)
                
                # 全ページをスクレイピング
                results = await self.scrape_all_pages(page)
                
                # 商品リンクでデータを拡張
                await self.enrich_with_product_links(context, results)
                
                await browser.close()
                logger.info(f"スクレイピング完了: {len(results)}件のデータを取得")
                return results
                
        except Exception as e:
            logger.error(f"スクレイピングエラー: {e}")
            raise


class DataProcessor:
    """データ処理クラス"""
    
    @staticmethod
    def prepare_google_sheets_data(results):
        """Google Sheets用のデータを準備"""
        from datetime import datetime
        
        headers = [
            "ステータス",
            "注文番号",
            "注文日",
            "見積完了日",
            "買付完了日",
            "中国事務所到着日",
            "発送可能日",
            "注文詳細リンク",
            "商品リンク",
            "商品画像",
            "商品名",
            "色・サイズ等指定",
            "更新日",
        ]
        
        # 現在の日時を取得
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        values = [headers]
        for r in results:
            values.append([
                r.get("status", ""),
                r.get("orderId", ""),
                r.get("orderedAt", ""),
                r.get("estimatedAt", ""),
                r.get("purchasedAt", ""),
                r.get("arrivedChinaAt", ""),
                r.get("shippableAt", ""),
                r.get("detailLink", ""),
                r.get("orderLink", ""),
                r.get("imageUrl", ""),
                r.get("itemName", ""),
                "",  # 色・サイズ等指定（現在は空）
                current_time,  # 更新日
            ])
        
        return values


async def main():
    """メイン実行関数"""
    try:
        logger.info("=== イーウーパスポート スクレイピング開始 ===")
        
        # スクレイピング実行
        scraper = YiwuScraper()
        results = await scraper.run()
        
        # データ処理
        processor = DataProcessor()
        values = processor.prepare_google_sheets_data(results)
        
        # Google Sheetsに書き込み
        logger.info("Google Sheetsに書き込み中...")
        google_sheet.GSheet().write(values)
        
        logger.info("=== スクレイピング完了 ===")
        
    except Exception as e:
        logger.error(f"=== エラーが発生しました: {e} ===")
        raise


if __name__ == "__main__":
    asyncio.run(main())