"""Local and Supabase persistence for WeDrop catalog and stock history."""

from __future__ import annotations

import hashlib
import os
import re
import sqlite3
import unicodedata
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


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
            parsed = parser(text)
            return parsed.astimezone() if parsed.tzinfo is None else parsed
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


PRODUCT_FIELDS = (
    "product_id",
    "name",
    "category",
    "url",
    "sku",
    "ean",
    "price",
    "availability",
    "stock",
    "total_stock_count",
    "real_balance",
    "is_active",
    "supplier",
    "cnpj",
    "origin_state",
    "ncm",
    "weight",
    "height",
    "width",
    "length",
    "description",
    "number_sales",
    "updated_at",
)


def load_local_environment() -> None:
    """Load ignored local .env settings without overriding process-level values."""
    env_file = Path(__file__).resolve().parent / ".env"
    load_dotenv(env_file, override=False)


def make_event_records(
    product: dict[str, Any], captured_at: str
) -> list[dict[str, Any]]:
    records = []
    for event in product.get("stock_history", []):
        raw_date = str(event.get("date", "")).strip()
        parsed_date = parse_event_datetime(raw_date)
        records.append(
            {
                "event_id": event_fingerprint(product["product_id"], event),
                "product_id": product["product_id"],
                "movement_type": str(event.get("type", "")).strip(),
                "event_kind": classify_movement(str(event.get("type", ""))),
                "quantity": parse_quantity(str(event.get("quantity", ""))),
                "event_at": (
                    parsed_date.isoformat(timespec="seconds") if parsed_date else None
                ),
                "event_at_raw": raw_date,
                "nf_key": str(event.get("nf_key", "")).strip(),
                "recorded_at": captured_at,
            }
        )
    return records


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
                ean TEXT,
                price TEXT,
                availability TEXT,
                stock TEXT,
                total_stock_count TEXT,
                real_balance TEXT,
                is_active TEXT,
                supplier TEXT,
                cnpj TEXT,
                origin_state TEXT,
                ncm TEXT,
                weight TEXT,
                height TEXT,
                width TEXT,
                length TEXT,
                description TEXT,
                number_sales TEXT,
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
            CREATE INDEX IF NOT EXISTS stock_events_kind_date_idx
                ON stock_events (event_kind, event_at);
            CREATE INDEX IF NOT EXISTS stock_events_product_date_idx
                ON stock_events (product_id, event_at);
            """
        )
        existing_columns = {
            row["name"]
            for row in self.connection.execute("PRAGMA table_info(products)")
        }
        for column in PRODUCT_FIELDS[5:-1]:
            if column not in existing_columns:
                self.connection.execute(
                    f"ALTER TABLE products ADD COLUMN {column} TEXT"
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

    def save_products(
        self, products: list[dict[str, Any]], captured_at: str
    ) -> list[dict[str, Any]]:
        product_values = [
            tuple(product.get(field, "") for field in PRODUCT_FIELDS[:-1])
            + (captured_at,)
            for product in products
        ]
        update_columns = ", ".join(
            f"{field} = excluded.{field}" for field in PRODUCT_FIELDS[1:]
        )
        placeholders = ", ".join("?" for _ in PRODUCT_FIELDS)
        columns = ", ".join(PRODUCT_FIELDS)
        self.connection.executemany(
            f"""
            INSERT INTO products ({columns}) VALUES ({placeholders})
            ON CONFLICT(product_id) DO UPDATE SET {update_columns}
            """,
            product_values,
        )
        events = [
            event
            for product in products
            for event in make_event_records(product, captured_at)
        ]
        self.connection.executemany(
            """
            INSERT OR IGNORE INTO stock_events
                (event_id, product_id, movement_type, event_kind, quantity, event_at,
                 event_at_raw, nf_key, recorded_at)
            VALUES (:event_id, :product_id, :movement_type, :event_kind, :quantity,
                    :event_at, :event_at_raw, :nf_key, :recorded_at)
            """,
            events,
        )
        self.connection.commit()
        return events

    def save_product(self, product: dict[str, Any], captured_at: str) -> None:
        self.save_products([product], captured_at)

    def sales_for_day(self, selected_day: date) -> list[sqlite3.Row]:
        day_start = datetime.combine(
            selected_day, datetime.min.time()
        ).astimezone().isoformat()
        next_day = datetime.combine(
            selected_day + timedelta(days=1), datetime.min.time()
        ).astimezone().isoformat()
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
                    datetime.combine(first_day, datetime.min.time())
                    .astimezone()
                    .isoformat(),
                    datetime.combine(
                        through_day + timedelta(days=1), datetime.min.time()
                    )
                    .astimezone()
                    .isoformat(),
                ),
            )
        )

    def stock_entries_for_day(self, selected_day: date) -> list[sqlite3.Row]:
        day_start = datetime.combine(
            selected_day, datetime.min.time()
        ).astimezone().isoformat()
        next_day = datetime.combine(
            selected_day + timedelta(days=1), datetime.min.time()
        ).astimezone().isoformat()
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


class SupabaseRepository:
    """Persist catalog records through Supabase's PostgREST upsert endpoint."""

    def __init__(self, url: str, api_key: str, timeout: int = 30):
        self.base_url = f"{url.rstrip('/')}/rest/v1"
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update(
            {
                "apikey": api_key,
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Prefer": "resolution=merge-duplicates,return=minimal",
            }
        )

    @classmethod
    def from_environment(cls) -> "SupabaseRepository":
        load_local_environment()
        url = os.environ.get("SUPABASE_URL", "").strip()
        api_key = (
            os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "").strip()
            or os.environ.get("SUPABASE_KEY", "").strip()
        )
        missing = [
            name
            for name, value in (
                ("SUPABASE_URL", url),
                ("SUPABASE_SERVICE_ROLE_KEY ou SUPABASE_KEY", api_key),
            )
            if not value
        ]
        if missing:
            raise RuntimeError(
                "Supabase não configurado. Defina SUPABASE_URL e "
                "SUPABASE_SERVICE_ROLE_KEY (ou SUPABASE_KEY) no ambiente antes "
                "de iniciar a coleta."
            )
        return cls(url, api_key)

    def _upsert(self, table: str, rows: list[dict[str, Any]], conflict: str) -> None:
        for start in range(0, len(rows), 200):
            response = self.session.post(
                f"{self.base_url}/{table}",
                params={"on_conflict": conflict},
                json=rows[start : start + 200],
                timeout=self.timeout,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Supabase rejeitou gravação em {table} "
                    f"(HTTP {response.status_code}): {response.text[:500]}"
                )

    def validate(self) -> None:
        """Fail before a long scrape if the configured Supabase schema is unavailable."""
        table_keys = {
            "wedrop_categories": "category_url",
            "wedrop_products": "product_id",
            "wedrop_stock_events": "event_id",
        }
        for table, key in table_keys.items():
            response = self.session.get(
                f"{self.base_url}/{table}",
                params={"select": key, "limit": "0"},
                timeout=self.timeout,
            )
            if not response.ok:
                raise RuntimeError(
                    f"Supabase indisponível para a tabela {table} "
                    f"(HTTP {response.status_code}): {response.text[:500]}. "
                    "Confirme SUPABASE_URL/SUPABASE_SERVICE_ROLE_KEY e execute "
                    "supabase_schema.sql no SQL Editor do projeto."
                )

    def save_category(
        self, category: dict[str, Any], mapped_products: int, captured_at: str
    ) -> None:
        self._upsert(
            "wedrop_categories",
            [
                {
                    "category_url": category["url"],
                    "name": category["name"],
                    "expected_products": category.get("count"),
                    "mapped_products": mapped_products,
                    "updated_at": captured_at,
                }
            ],
            "category_url",
        )

    def save_products(
        self, products: list[dict[str, Any]], captured_at: str
    ) -> None:
        product_rows = [
            {field: product.get(field, "") for field in PRODUCT_FIELDS[:-1]}
            | {"updated_at": captured_at}
            for product in products
        ]
        events_by_id = {
            event["event_id"]: event
            for product in products
            for event in make_event_records(product, captured_at)
        }
        self._upsert("wedrop_products", product_rows, "product_id")
        self._upsert(
            "wedrop_stock_events", list(events_by_id.values()), "event_id"
        )

    def close(self) -> None:
        self.session.close()
