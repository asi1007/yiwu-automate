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


class TestFillMissingDates:
    def test_fills_empty_date_with_today(self):
        from yiwu_scraper import BuyerCentralScraper
        orders = {
            "A001": {"date": "2026-03-20 14:53:44", "product_name": "x"},
            "A002": {"date": "", "product_name": "y"},
        }
        today = "2026-07-27 00:00:00"
        BuyerCentralScraper._fill_missing_dates(orders, today)
        assert orders["A001"]["date"] == "2026-03-20 14:53:44"
        assert orders["A002"]["date"] == today

    def test_leaves_all_present_dates_untouched(self):
        from yiwu_scraper import BuyerCentralScraper
        orders = {"A001": {"date": "2026-03-20 14:53:44", "product_name": "x"}}
        BuyerCentralScraper._fill_missing_dates(orders, "2026-07-27 00:00:00")
        assert orders["A001"]["date"] == "2026-03-20 14:53:44"
