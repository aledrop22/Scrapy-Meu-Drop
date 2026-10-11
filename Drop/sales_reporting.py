"""Shared parsing and persistence for daily WeDrop stock-history reports."""

from __future__ import annotations

import hashlib
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any


def parse_event_datetime(value: str) -> datetime | None:
    """Parse the date formats commonly shown in the stock-history interface."""
    text = value.strip().replace("\u00a0", " ")
    text = re.sub(r"\s+às\s+", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"(?<=\d)h(?=\d)", ":", text, flags=re.IGNORECASE)
    for parser in (
        datetime.fromisoformat,
        lambda raw: datetime.strptime(raw, "%d/%m/%Y %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%d/%m/%Y %H:%M"),
        lambda raw: datetime.strptime(raw, "%d/%m/%Y"),
        lambda raw: datetime.strptime(raw, "%d-%m-%Y %H:%M:%S"),
        lambda raw: datetime.strptime(raw, "%d-%m-%Y %H:%M"),
        lambda raw: datetime.strptime(raw, "%d-%m-%Y"),
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def parse_quantity(value: str) -> int:
    """Return the absolute integer quantity from text such as '- 2 un.'."""
    digits = re.sub(r"\D", "", value)
    return int(digits) if digits else 0


def classify_movement(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value.casefold())
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    if "venda" in normalized or "saida" in normalized:
        return "sale"
    if "entrada" in normalized or "recebimento" in normalized:
        return "stock_in"
    return "other"


def event_fingerprint(product_id: str, event: dict[str, Any]) -> str:
    """Deduplicate the same history row when the daily catalog is rescanned."""
    fields = (
        product_id,
        str(event.get("type", "")).strip().casefold(),
        str(event.get("quantity", "")).strip(),
        str(event.get("date", "")).strip(),
        str(event.get("nf_key", "")).strip(),
    )
    return hashlib.sha256("\x1f".join(fields).encode("utf-8")).hexdigest()


class SalesRepository:
    def __init__(self, database_path: Path):
        self.connection = sqlite3.connect(database_path)
        self.connection.row_factory = sqlite3.Row
        self._initialize()

    def _initialize(self) -> None:
        self.connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS categories (
                category_url TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                expected_products INTEGER,
                mapped_products INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS products (
                product_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                url TEXT NOT NULL,
                sku TEXT,
                price TEXT,
                stock TEXT,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS stock_events (
                event_id TEXT PRIMARY KEY,
                product_id TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                event_kind TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                event_at TEXT,
                event_at_raw TEXT NOT NULL,
                nf_key TEXT,
                recorded_at TEXT NOT NULL,
                FOREIGN KEY (product_id) REFERENCES products(product_id)
            );
            """
        )
        self.connection.commit()

    def save_category(
        self, category: dict[str, Any], mapped_products: int, captured_at: str
    ) -> None:
        self.connection.execute(
            """
            INSERT INTO categories
                (category_url, name, expected_products, mapped_products, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(category_url) DO UPDATE SET
                name = excluded.name,
                expected_products = excluded.expected_products,
                mapped_products = excluded.mapped_products,
                updated_at = excluded.updated_at
            """,
            (
                category["url"],
                category["name"],
                category.get("count"),
                mapped_products,
                captured_at,
            ),
        )
        self.connection.commit()

    def save_product(self, product: dict[str, Any], captured_at: str) -> None:
        self.connection.execute(
            """
            INSERT INTO products
                (product_id, name, category, url, sku, price, stock, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(product_id) DO UPDATE SET
                name = excluded.name,
                category = excluded.category,
                url = excluded.url,
                sku = excluded.sku,
                price = excluded.price,
                stock = excluded.stock,
                updated_at = excluded.updated_at
            """,
            (
                product["product_id"],
                product["name"],
                product["category"],
                product["url"],
                product.get("sku", ""),
                product.get("price", ""),
                product.get("stock", ""),
                captured_at,
            ),
        )
        for event in product.get("stock_history", []):
            raw_date = str(event.get("date", "")).strip()
            parsed_date = parse_event_datetime(raw_date)
            self.connection.execute(
                """
                INSERT OR IGNORE INTO stock_events
                    (event_id, product_id, movement_type, event_kind, quantity,
                     event_at, event_at_raw, nf_key, recorded_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event_fingerprint(product["product_id"], event),
                    product["product_id"],
                    str(event.get("type", "")).strip(),
                    classify_movement(str(event.get("type", ""))),
                    parse_quantity(str(event.get("quantity", ""))),
                    parsed_date.isoformat(timespec="seconds") if parsed_date else None,
                    raw_date,
                    str(event.get("nf_key", "")).strip(),
                    captured_at,
                ),
            )
        self.connection.commit()

    def sales_for_day(self, selected_day: date) -> list[sqlite3.Row]:
        day_start = datetime.combine(selected_day, datetime.min.time()).isoformat()
        next_day = datetime.combine(
            selected_day + timedelta(days=1), datetime.min.time()
        ).isoformat()
        return list(
            self.connection.execute(
                """
                SELECT p.product_id, p.name, p.category, p.sku,
                       SUM(e.quantity) AS units_sold,
                       COUNT(e.event_id) AS sale_events
                FROM stock_events AS e
                JOIN products AS p ON p.product_id = e.product_id
                WHERE e.event_kind = 'sale'
                  AND e.event_at >= ?
                  AND e.event_at < ?
                GROUP BY p.product_id, p.name, p.category, p.sku
                ORDER BY units_sold DESC, p.name COLLATE NOCASE
                LIMIT 20
                """,
                (day_start, next_day),
            )
        )

    def daily_sales(self, through_day: date, days: int = 14) -> list[sqlite3.Row]:
        first_day = through_day - timedelta(days=days - 1)
        return list(
            self.connection.execute(
                """
                SELECT substr(event_at, 1, 10) AS day, SUM(quantity) AS units_sold
                FROM stock_events
                WHERE event_kind = 'sale'
                  AND event_at >= ?
                  AND event_at < ?
                GROUP BY substr(event_at, 1, 10)
                ORDER BY day
                """,
                (
                    datetime.combine(first_day, datetime.min.time()).isoformat(),
                    datetime.combine(
                        through_day + timedelta(days=1), datetime.min.time()
                    ).isoformat(),
                ),
            )
        )

    def stock_entries_for_day(self, selected_day: date) -> list[sqlite3.Row]:
        day_start = datetime.combine(selected_day, datetime.min.time()).isoformat()
        next_day = datetime.combine(
            selected_day + timedelta(days=1), datetime.min.time()
        ).isoformat()
        return list(
            self.connection.execute(
                """
                SELECT p.name, p.category, e.quantity, e.event_at, e.movement_type
                FROM stock_events AS e
                JOIN products AS p ON p.product_id = e.product_id
                WHERE e.event_kind = 'stock_in'
                  AND e.event_at >= ?
                  AND e.event_at < ?
                ORDER BY e.event_at DESC
                """,
                (day_start, next_day),
            )
        )

    def categories(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                """
                SELECT name, expected_products, mapped_products, updated_at
                FROM categories
                ORDER BY name COLLATE NOCASE
                """
            )
        )

    def close(self) -> None:
        self.connection.close()
