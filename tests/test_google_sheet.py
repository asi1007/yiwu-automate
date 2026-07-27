import pytest
from datetime import date


class TestCompleteYear:
    def test_uses_current_year_for_past_date(self):
        from google_sheet import GSheet
        assert GSheet._complete_year("02-26", date(2026, 7, 28)) == date(2026, 2, 26)

    def test_rolls_back_to_previous_year_for_future_date(self):
        from google_sheet import GSheet
        assert GSheet._complete_year("12-30", date(2026, 7, 28)) == date(2025, 12, 30)

    def test_accepts_slash_separator(self):
        from google_sheet import GSheet
        assert GSheet._complete_year("03/18", date(2026, 7, 28)) == date(2026, 3, 18)

    def test_returns_none_for_invalid(self):
        from google_sheet import GSheet
        assert GSheet._complete_year("", date(2026, 7, 28)) is None
        assert GSheet._complete_year("abc", date(2026, 7, 28)) is None


OVERDUE_HEADER = ["商品名", "購入日", "到着日", "状態", "注文番号"]
OVERDUE_COLS = {"商品名": 0, "購入日": 1, "到着日": 2, "状態": 3, "注文番号": 4}
OVERDUE_DATA = [
    [], [], [],
    OVERDUE_HEADER,
    ["商品A", "02-26", "", "未発送", "Y0806-001"],        # 152日 → 遅延
    ["商品A", "02-26", "", "未発送", "Y0806-001"],        # 同一注文の重複行 → 集約
    ["商品B", "07-20", "", "未発送", "Y0806-002"],        # 8日 → 対象外
    ["商品C", "07-01", "07/05", "未発送", "Y0806-003"],   # 到着日あり → 対象外
    ["商品D", "01-10", "", "発送済み", "Y0806-004"],       # 未発送でない → 対象外
    ["商品E", "07-10", "", "未発送", "Y0806-005"],        # 18日 → 遅延
]


class TestExtractOverdueOrders:
    def test_extracts_overdue_and_aggregates(self):
        from google_sheet import GSheet
        today = date(2026, 7, 28)
        result = GSheet._extract_overdue_orders(OVERDUE_DATA, OVERDUE_COLS, today, 14)
        orders = {r["order_number"] for r in result}
        assert orders == {"Y0806-001", "Y0806-005"}

    def test_reports_days_elapsed(self):
        from google_sheet import GSheet
        today = date(2026, 7, 28)
        result = GSheet._extract_overdue_orders(OVERDUE_DATA, OVERDUE_COLS, today, 14)
        by_order = {r["order_number"]: r for r in result}
        assert by_order["Y0806-005"]["days_elapsed"] == 18
        assert by_order["Y0806-001"]["product_name"] == "商品A"
        assert by_order["Y0806-001"]["purchase_date"] == "02-26"

    def test_deduplicates_by_order_number(self):
        from google_sheet import GSheet
        today = date(2026, 7, 28)
        result = GSheet._extract_overdue_orders(OVERDUE_DATA, OVERDUE_COLS, today, 14)
        assert sum(1 for r in result if r["order_number"] == "Y0806-001") == 1


SAMPLE_HEADER = [
    "備考", "行番号", "画像", "ASIN", "商品名", "ステータス",
    "購入日", "買付完了日", "到着日", "梱包依頼日", "発送日",
    "受領日", "", "", "", "状態", " 注文番号"
]

SAMPLE_DATA = [
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    ["", "", "", "", ""],
    SAMPLE_HEADER,
    ["", "5", "", "B0TEST1", "商品A", "未発送",
     "03/18", "", "", "", "",
     "", "", "", "", "", "P260318001YP806"],
    ["", "6", "", "B0TEST2", "商品B", "未発送",
     "03/17", "", "03/20", "", "",
     "", "", "", "", "", "P260317003YP806"],
    ["", "7", "", "B0TEST3", "商品C", "未発送",
     "03/16", "", "#N/A", "", "",
     "", "", "", "", "", "P260316001YP806"],
    ["", "8", "", "B0TEST4", "商品D", "発送済み",
     "03/15", "", "", "", "",
     "", "", "", "", "", "P260315001YP806"],
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
        assert len(rows) == 3
        assert rows[0]["row_index"] == 4
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
        assert matches[0]["arrival_date"] == "03/20"

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
