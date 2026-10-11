import asyncio
import sqlite3
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import requests

from sales_reporting import (
    SalesRepository,
    SupabaseRepository,
    classify_movement,
    parse_event_datetime,
    parse_quantity,
)
from wedrop_monitor_sistema import (
    WedropMonitor,
    product_id_from_url,
    value_for_label,
)


class SalesReportingTests(unittest.TestCase):
    def test_parses_date_formats_and_quantities(self):
        for value in ("10/10/2026 15:42:08", "2026-10-10T15:42:08"):
            parsed = parse_event_datetime(value)
            self.assertIsNotNone(parsed)
            if parsed is not None:
                self.assertEqual(parsed.strftime("%Y-%m-%dT%H:%M:%S"), "2026-10-10T15:42:08")
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
                "sku": "SKU-123",
                "stock": "15",
                "real_balance": "12",
                "description": "Descrição do produto",
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
            saved_product = repository.connection.execute(
                "SELECT sku, stock, real_balance, description FROM products"
            ).fetchone()
            self.assertEqual(tuple(saved_product), ("SKU-123", "15", "12", "Descrição do produto"))
            repository.close()

    def test_existing_product_database_is_upgraded_without_losing_data(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            database_path = Path(temp_dir) / "report.db"
            connection = sqlite3.connect(database_path)
            connection.execute(
                """
                CREATE TABLE products (
                    product_id TEXT PRIMARY KEY, name TEXT NOT NULL,
                    category TEXT NOT NULL, url TEXT NOT NULL, sku TEXT,
                    price TEXT, stock TEXT, updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "INSERT INTO products VALUES ('1', 'Existing', 'Cat', 'url', '', '', '', 'today')"
            )
            connection.commit()
            connection.close()

            repository = SalesRepository(database_path)
            columns = {
                row["name"]
                for row in repository.connection.execute("PRAGMA table_info(products)")
            }
            self.assertIn("real_balance", columns)
            self.assertEqual(
                repository.connection.execute(
                    "SELECT name FROM products WHERE product_id='1'"
                ).fetchone()["name"],
                "Existing",
            )
            repository.close()

    def test_supabase_requires_configuration_and_reports_upsert_errors(self):
        with patch("sales_reporting.load_local_environment"):
            with patch.dict("os.environ", {}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "Supabase não configurado"):
                    SupabaseRepository.from_environment()

        failed_response = Mock(spec=requests.Response)
        failed_response.ok = False
        failed_response.status_code = 401
        failed_response.text = "Unauthorized"
        repository = SupabaseRepository("https://example.supabase.co", "test-key")
        with patch.object(repository.session, "post", return_value=failed_response):
            with self.assertRaisesRegex(RuntimeError, "HTTP 401"):
                repository._upsert(
                    "wedrop_products", [{"product_id": "1"}], "product_id"
                )
        repository.close()

    def test_supabase_validates_all_required_tables_before_scraping(self):
        repository = SupabaseRepository("https://example.supabase.co", "test-key")
        successful_response = Mock(spec=requests.Response)
        successful_response.ok = True
        with patch.object(
            repository.session, "get", return_value=successful_response
        ) as get:
            repository.validate()
        self.assertEqual(get.call_count, 3)

        failed_response = Mock(spec=requests.Response)
        failed_response.ok = False
        failed_response.status_code = 404
        failed_response.text = "table missing"
        with patch.object(repository.session, "get", return_value=failed_response):
            with self.assertRaisesRegex(RuntimeError, "wedrop_categories"):
                repository.validate()
        repository.close()

    def test_supabase_upserts_full_product_and_deduplicated_history(self):
        repository = SupabaseRepository("https://example.supabase.co", "test-key")
        successful_response = Mock(spec=requests.Response)
        successful_response.ok = True
        product = {
            "product_id": "321",
            "name": "Produto",
            "category": "Casa",
            "url": "https://example.com/catalog/321",
            "stock": "4",
            "real_balance": "3",
            "stock_history": [
                {
                    "type": "Saída",
                    "quantity": "- 1",
                    "date": "10/10/2026 12:00:00",
                }
            ],
        }
        with patch.object(
            repository.session, "post", return_value=successful_response
        ) as post:
            repository.save_products([product, product], "2026-10-10T15:00:00-03:00")
        self.assertEqual(post.call_count, 2)
        product_payload = post.call_args_list[0].kwargs["json"]
        history_payload = post.call_args_list[1].kwargs["json"]
        self.assertEqual(len(product_payload), 2)
        self.assertEqual(product_payload[0]["real_balance"], "3")
        self.assertEqual(len(history_payload), 1)
        self.assertEqual(history_payload[0]["event_kind"], "sale")
        repository.close()

    def test_product_identifier_and_label_extraction(self):
        self.assertEqual(
            product_id_from_url("https://dash.wedrop.com.br/catalog/12345"),
            "12345",
        )
        self.assertEqual(
            product_id_from_url("https://dash.wedrop.com.br/catalog/categoria-casa"),
            "",
        )
        self.assertEqual(value_for_label("Saldo real:\n42 un.", ("Saldo real",)), "42 un.")

    def test_expired_session_authenticates_and_saves_cookies_in_same_run(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            monitor = WedropMonitor(Path(temp_dir) / "report.db")
            login_form = Mock()
            login_form.count = AsyncMock(return_value=1)
            email_input = Mock()
            email_input.first = Mock()
            email_input.first.fill = AsyncMock()
            password_input = Mock()
            password_input.first = Mock()
            password_input.first.fill = AsyncMock()
            post_login_form = Mock()
            post_login_form.count = AsyncMock(return_value=0)
            submit_button = Mock()
            submit_button.click = AsyncMock()
            page = Mock()
            page.url = "https://dash.wedrop.com.br/login"
            page.goto = AsyncMock()
            page.wait_for_timeout = AsyncMock()
            page.wait_for_function = AsyncMock()
            page.locator = Mock(
                side_effect=[
                    login_form,
                    email_input,
                    password_input,
                    submit_button,
                    post_login_form,
                ]
            )
            context = Mock()
            context.storage_state = AsyncMock()

            asyncio.run(
                monitor.ensure_authenticated(
                    page,
                    context,
                    email="person@example.com",
                    password="test-password",
                    prompt_for_credentials=False,
                )
            )

            email_input.first.fill.assert_awaited_once_with("person@example.com")
            password_input.first.fill.assert_awaited_once_with("test-password")
            context.storage_state.assert_awaited_once()
            monitor.close()


if __name__ == "__main__":
    unittest.main()
