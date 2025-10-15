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
        
        # Headlessモードの設定（デフォルトはTrue）
        headless_str = os.environ.get("HEADLESS", "true").lower()
        self.headless = headless_str in ("true", "1", "yes")
        
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
    
    async def extract_product_links_from_context(self, context, link, max_retries=3):
        """
        詳細ページから商品リンクと色・サイズ等指定を抽出（複数商品対応）
        
        Args:
            context: ブラウザコンテキスト
            link: 詳細ページのURL
            max_retries: 最大リトライ回数
            
        Returns:
            List[Dict[str, str]]: 商品データのリスト [{"productLink": "...", "colorSize": "..."}, ...]
        """
        page = await context.new_page()
        
        for attempt in range(max_retries):
            try:
                # タイムアウトを60秒に延長
                await page.goto(link, timeout=60000)
                await page.wait_for_load_state("networkidle", timeout=60000)
                
                # すべての商品セクション（h3見出し「商品1」「商品2」など）を取得
                product_sections = page.locator('h3:text-matches("商品\\\\d+")')
                section_count = await product_sections.count()
                
                product_data = []
                
                # 各商品セクションから商品リンクと色・サイズ等指定を抽出
                for i in range(section_count):
                    # i番目の商品セクションの次にあるテーブルを取得
                    # 「注文情報」セクション内のすべてのテーブルを取得
                    tables = page.locator('table.table.table-bordered.table-striped.table-responsive')
                    
                    # i番目のテーブルを取得（商品iに対応）
                    if i < await tables.count():
                        table = tables.nth(i)
                        
                        # テーブル内の行を走査
                        rows = table.locator('tbody > tr')
                        row_count = await rows.count()
                        
                        product_link = ""
                        color_size = ""
                        
                        for row_idx in range(row_count):
                            row = rows.nth(row_idx)
                            # tdとthの両方を取得
                            cells = row.locator('td, th')
                            cells_count = await cells.count()
                            
                            # すべてのセルをループして、thとtdのペアを処理
                            for cell_idx in range(cells_count - 1):
                                cell = cells.nth(cell_idx)
                                next_cell = cells.nth(cell_idx + 1)
                                
                                # 現在のセルがthかどうか確認
                                tag_name = await cell.evaluate('el => el.tagName')
                                if tag_name == 'TH':
                                    cell_text = (await cell.text_content() or '').strip()
                                    
                                    # 色・サイズ等指定を取得
                                    if cell_text == '色・サイズ等指定':
                                        color_size = (await next_cell.text_content() or '').strip()
                                        # 改行を空白に置換して1行にする
                                        color_size = ' '.join(color_size.split())
                                    
                                    # URLを取得
                                    elif cell_text == 'URL':
                                        link_element = await next_cell.query_selector('a')
                                        if link_element:
                                            product_link = await link_element.get_attribute('href')
                        
                        # 結果に追加
                        product_data.append({
                            "productLink": product_link or "",
                            "colorSize": color_size or ""
                        })
                
                await page.close()
                return product_data
                
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"詳細ページ {link} の読み込みに失敗。リトライします（{attempt + 1}/{max_retries}）: {e}")
                    await asyncio.sleep(2)  # 2秒待機してリトライ
                else:
                    logger.warning(f"詳細ページ {link} の処理でエラー: {e}")
                    await page.close()
                    return []  # リトライ上限に達したら空リストを返す
    
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
    
    async def enrich_with_product_links(self, context, results, batch_size=10):
        """
        商品リンクと色・サイズ等指定でデータを拡張（複数商品対応）
        
        Args:
            context: ブラウザコンテキスト
            results: スクレイピング結果のリスト
            batch_size: 並列処理のバッチサイズ
        """
        # 詳細リンクのリストを作成（重複を除外）
        detail_links = []
        seen_links = set()
        for r in results:
            detail_link = r.get("detailLink", "")
            if detail_link and detail_link not in seen_links:
                detail_links.append(detail_link)
                seen_links.add(detail_link)
        
        logger.info(f"{len(detail_links)}件の詳細ページから商品リンクと色・サイズ等指定を取得します")
        
        # バッチ処理で並列実行
        product_links = {}  # {detail_link: [{"productLink": "...", "colorSize": "..."}, ...]}
        for i in range(0, len(detail_links), batch_size):
            batch = detail_links[i:i + batch_size]
            logger.info(f"バッチ {i // batch_size + 1}/{(len(detail_links) + batch_size - 1) // batch_size} を処理中...")
            
            # バッチ内のタスクを並列実行
            tasks = [self.extract_product_links_from_context(context, link) for link in batch]
            results_list = await asyncio.gather(*tasks, return_exceptions=True)
            
            # 結果を辞書に格納
            for j, detail_link in enumerate(batch):
                product_data = results_list[j]
                if isinstance(product_data, Exception):
                    logger.warning(f"詳細ページ {detail_link} の処理でエラー: {product_data}")
                    product_links[detail_link] = []
                else:
                    product_links[detail_link] = product_data if product_data else []
            
            # バッチ間で待機（サーバー負荷を考慮）
            if i + batch_size < len(detail_links):
                await asyncio.sleep(1)
        
        # 結果を各注文に追加（順序で紐付け）
        detail_link_indices = {}  # 各detail_linkの現在のインデックスを追跡
        
        for r in results:
            detail_link = r.get("detailLink", "")
            
            # このdetail_linkで何番目のアイテムか
            if detail_link not in detail_link_indices:
                detail_link_indices[detail_link] = 0
            
            index = detail_link_indices[detail_link]
            product_data_list = product_links.get(detail_link, [])
            
            # インデックスに対応する商品データを割り当て
            if index < len(product_data_list):
                product_data = product_data_list[index]
                r["orderLink"] = product_data.get("productLink", "")
                r["colorSize"] = product_data.get("colorSize", "")
            else:
                r["orderLink"] = ""
                r["colorSize"] = ""
            
            detail_link_indices[detail_link] += 1
    
    async def run(self):
        """メイン実行メソッド"""
        try:
            logger.info(f"スクレイピング開始... (Headless: {self.headless})")
            async with async_playwright() as p:
                # Headlessモードを環境変数で制御（デフォルトはTrue）
                browser = await p.chromium.launch(headless=self.headless)
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
                r.get("colorSize", ""),  # 色・サイズ等指定
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