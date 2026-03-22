import pytest


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
