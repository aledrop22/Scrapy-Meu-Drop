import tempfile
import unittest
from datetime import date
from pathlib import Path

from sales_reporting import (
    SalesRepository,
    classify_movement,
    parse_event_datetime,
    parse_quantity,
)


class SalesReportingTests(unittest.TestCase):
    def test_parses_date_formats_and_quantities(self):
        self.assertEqual(
            parse_event_datetime("10/10/2026 15:42:08").isoformat(),
            "2026-10-10T15:42:08",
        )
        self.assertEqual(
            parse_event_datetime("2026-10-10T15:42:08").isoformat(),
            "2026-10-10T15:42:08",
        )
        self.assertEqual(parse_quantity("- 12 unidades"), 12)
        self.assertIsNone(parse_event_datetime("data indisponível"))

    def test_classifies_sales_and_stock_entries(self):
        self.assertEqual(classify_movement("Saída"), "sale")
        self.assertEqual(classify_movement("Venda"), "sale")
        self.assertEqual(classify_movement("Entrada de estoque"), "stock_in")
        self.assertEqual(classify_movement("Ajuste manual"), "other")

    def test_repeated_daily_scan_does_not_duplicate_sales(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            repository = SalesRepository(Path(temp_dir) / "report.db")
            product = {
                "product_id": "123",
                "name": "Produto teste",
                "category": "Categoria teste",
                "url": "https://dash.wedrop.com.br/catalog/123",
                "stock_history": [
                    {
                        "type": "Saída",
                        "quantity": "- 2",
                        "date": "10/10/2026 15:42:08",
                    },
                    {
                        "type": "Entrada",
                        "quantity": "+ 5",
                        "date": "10/10/2026 15:43:08",
                    },
                ],
            }
            repository.save_product(product, "2026-10-10T16:00:00")
            repository.save_product(product, "2026-10-11T16:00:00")

            sales = repository.sales_for_day(date(2026, 10, 10))
            entries = repository.stock_entries_for_day(date(2026, 10, 10))
            self.assertEqual(len(sales), 1)
            self.assertEqual(sales[0]["units_sold"], 2)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0]["quantity"], 5)
            repository.close()


if __name__ == "__main__":
    unittest.main()
