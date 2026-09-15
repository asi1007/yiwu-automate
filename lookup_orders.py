from __future__ import annotations

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env")

from order_lookup import format_order_status, lookup_orders

logger = logging.getLogger(__name__)


def _collect_order_numbers(args: argparse.Namespace) -> list[str]:
    numbers = list(args.orders)
    if args.from_sheet:
        numbers.extend(_order_numbers_from_sheet(args.from_sheet))
    seen: list[str] = []
    for number in numbers:
        cleaned = number.strip()
        if cleaned and cleaned not in seen:
            seen.append(cleaned)
    return seen


def _order_numbers_from_sheet(rows: str) -> list[str]:
    """仕入管理シートの行番号から注文番号を引く（例: --from-sheet 157,161,167）"""
    import google_sheet

    wanted = {int(r) for r in rows.split(",") if r.strip()}
    sheet = google_sheet.GSheet()
    all_values = sheet._execute_with_retry(sheet.ws.get_all_values)
    header = all_values[google_sheet.HEADER_ROW_INDEX]
    column = next(i for i, cell in enumerate(header) if cell.strip() == "注文番号")
    found: list[str] = []
    for row_number in sorted(wanted):
        index = row_number - 1
        if index >= len(all_values):
            continue
        cell = all_values[index][column] if column < len(all_values[index]) else ""
        found.extend(part.strip() for part in str(cell).splitlines() if part.strip())
    return found


def main() -> int:
    parser = argparse.ArgumentParser(description="イーウーの注文状況を注文番号で調べる")
    parser.add_argument("orders", nargs="*", help="注文番号（例: Y0806-260717002）")
    parser.add_argument("--from-sheet", help="仕入管理シートの行番号から引く（例: 157,161,167）")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(levelname)s %(message)s",
    )

    order_numbers = _collect_order_numbers(args)
    if not order_numbers:
        parser.error("注文番号を渡すか --from-sheet を指定してください")

    print(f"{len(order_numbers)}件を照会します")
    results = asyncio.run(lookup_orders(order_numbers))
    print()
    for status in results:
        print(format_order_status(status))

    missing = [s for s in results if not s.found]
    unpaid = [s for s in results if s.found and not s.is_paid]
    not_warehoused = [s for s in results if s.found and not s.is_warehoused]
    print()
    print(f"該当なし {len(missing)}件 / 未払い {len(unpaid)}件 / 未入庫 {len(not_warehoused)}件")
    return 0


if __name__ == "__main__":
    sys.exit(main())
