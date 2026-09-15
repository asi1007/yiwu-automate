from __future__ import annotations

import pytest

from order_lookup import OrderStatus, parse_order_row

ROW_WITH_WAREHOUSE = (
    "1元URL运动眼镜防滑绳 可调节眼镜绳任意名: --注文番号：Y0806-260717002 コピー受領済み"
    "1688detail.1688.comこの店舗のすべての注文を表示担当者：徐雪兰"
    "商品代金：3850.00 元中国内送料等：702.00 元純支払額：4552.00 元"
    "入荷倉庫：義鳥倉庫追跡番号：圆通速递(YTO):YT7633929242145カートに追加リピート注文"
    "作成：2026-07-17 13:26:22注文：2026-07-20 15:06:46引落：2026-07-20 16:20:23"
    "入庫：2026-07-21 15:13:32"
)
ROW_WITHOUT_WAREHOUSE = (
    "1元URL带镜港度戒指圈任意名: --注文番号：Y0806-260704009 コピー受領済み1688detail.1688.com"
    "追跡番号：韵达快递:435258557383139カートに追加リピート注文"
    "作成：2026-07-04 14:05:50注文：2026-07-06 10:20:00引落：2026-07-06 16:11:00"
)


class TestParseOrderRow:
    def test_注文番号を取り出す(self) -> None:
        assert parse_order_row(ROW_WITH_WAREHOUSE).order_number == "Y0806-260717002"

    def test_状態を取り出す(self) -> None:
        assert parse_order_row(ROW_WITH_WAREHOUSE).status == "受領済み"

    def test_日付を取り出す(self) -> None:
        got = parse_order_row(ROW_WITH_WAREHOUSE)
        assert got.created_at == "2026-07-17 13:26:22"
        assert got.ordered_at == "2026-07-20 15:06:46"
        assert got.paid_at == "2026-07-20 16:20:23"
        assert got.warehoused_at == "2026-07-21 15:13:32"

    def test_追跡番号は後続の文言を巻き込まない(self) -> None:
        got = parse_order_row(ROW_WITH_WAREHOUSE)
        assert got.tracking == "圆通速递(YTO):YT7633929242145"
        assert "カートに追加" not in got.tracking

    def test_入庫日が無くても他を取れる(self) -> None:
        got = parse_order_row(ROW_WITHOUT_WAREHOUSE)
        assert got.order_number == "Y0806-260704009"
        assert got.status == "受領済み"
        assert got.warehoused_at == ""
        assert got.tracking == "韵达快递:435258557383139"

    def test_改行や連続空白を潰して読む(self) -> None:
        got = parse_order_row("注文番号：Y0806-1\n コピー  受領済み1688 \n 作成：2026-07-04 14:05:50")
        assert got.order_number == "Y0806-1"

    def test_支払い済みかどうかを引落で判断する(self) -> None:
        assert parse_order_row(ROW_WITH_WAREHOUSE).is_paid is True
        assert parse_order_row("注文番号：X コピー対応待ち1688").is_paid is False

    def test_倉庫に入ったかを入庫で判断する(self) -> None:
        assert parse_order_row(ROW_WITH_WAREHOUSE).is_warehoused is True
        assert parse_order_row(ROW_WITHOUT_WAREHOUSE).is_warehoused is False


class TestOrderStatus:
    def test_見つからなかった注文を表せる(self) -> None:
        missing = OrderStatus.not_found("Y0806-999")
        assert missing.order_number == "Y0806-999"
        assert missing.found is False
        assert missing.status == "(該当なし)"

    def test_見つかった注文はfoundがTrue(self) -> None:
        assert parse_order_row(ROW_WITH_WAREHOUSE).found is True
