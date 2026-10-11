"""Authenticate, map the full WeDrop catalog, and persist daily stock history."""

from __future__ import annotations

import asyncio
import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import TimeoutError as PlaywrightTimeoutError
from playwright.async_api import async_playwright

from sales_reporting import (
    SalesRepository,
    SupabaseRepository,
    load_local_environment,
)


BASE_URL = "https://dash.wedrop.com.br"
PROJECT_DIR = Path(__file__).resolve().parent
STORAGE_STATE_FILE = PROJECT_DIR / "storage_state.json"
DB_FILE = PROJECT_DIR / "wedrop_monitoramento.db"
CATEGORY_SELECTOR = 'a[draggable="false"][data-group=""]'
PRODUCT_PATH = re.compile(
    r"/catalog/(?:[^/?#]+/)*(?:"
    r"(\d+)|([0-9a-f]{8}-[0-9a-f-]{27,})"
    r")(?:/[^/?#]+)?/?$",
    re.IGNORECASE,
)
PRODUCT_FIELDS = (
    "sku",
    "ean",
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
    "total_stock_count",
    "real_balance",
)


def product_id_from_url(url: str) -> str:
    match = PRODUCT_PATH.search(urlparse(url).path)
    return next((group for group in match.groups() if group), "") if match else ""


def value_for_label(text: str, labels: tuple[str, ...]) -> str:
    alternatives = "|".join(re.escape(label) for label in labels)
    match = re.search(
        rf"^\s*(?:{alternatives})\s*:?\s*(.+?)\s*$", text, re.IGNORECASE | re.MULTILINE
    )
    return match.group(1).strip() if match else ""


async def extract_technical_specs(page) -> dict[str, str]:
    specs = {}
    label_fields = {
        "ncm": "ncm",
        "peso": "weight",
        "altura": "height",
        "largura": "width",
        "comprimento": "length",
        "descrição": "description",
    }
    rows = page.locator("div.css-tuph3t")
    for row in await rows.all():
        label_node = row.locator("p.css-1wld651").first
        value_node = row.locator("p.css-nidmuk").first
        if not await label_node.count() or not await value_node.count():
            continue
        label = (await label_node.inner_text()).strip().casefold().rstrip(":")
        field = label_fields.get(label)
        if field:
            specs[field] = (await value_node.inner_text()).strip()
    return specs


def _as_int(value: str) -> int | None:
    match = re.search(r"\d[\d.,]*", value)
    if not match:
        return None
    return int(re.sub(r"\D", "", match.group()))


def _credential_values(
    email: str | None,
    password: str | None,
    prompt_for_credentials: bool,
) -> tuple[str, str]:
    email = (email or os.environ.get("WEDROP_EMAIL", "")).strip()
    password = password or os.environ.get("WEDROP_PASSWORD", "")
    if email and password:
        return email, password
    if not prompt_for_credentials or not sys.stdin.isatty():
        raise RuntimeError(
            "É necessário autenticar no WeDrop. Configure WEDROP_EMAIL e "
            "WEDROP_PASSWORD ou informe as credenciais no formulário do painel."
        )
    if not email:
        email = input("E-mail do WeDrop: ").strip()
    if not password:
        password = getpass.getpass("Senha do WeDrop: ")
    if not email or not password:
        raise RuntimeError("E-mail e senha são obrigatórios para autenticar no WeDrop.")
    return email, password


class WedropMonitor:
    def __init__(self, database_path: Path = DB_FILE):
        self.repository = SalesRepository(database_path)

    async def ensure_authenticated(
        self,
        page,
        context,
        email: str | None = None,
        password: str | None = None,
        prompt_for_credentials: bool = True,
    ) -> None:
        await page.goto(f"{BASE_URL}/catalog", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        login_form = page.locator('input[type="password"]')
        if "/login" not in page.url and not await login_form.count():
            return

        login_email, login_password = _credential_values(
            email, password, prompt_for_credentials
        )
        await page.goto(f"{BASE_URL}/login", wait_until="domcontentloaded")
        await page.locator('input[type="email"], input[name="email"]').first.fill(
            login_email
        )
        await page.locator('input[type="password"], input[name="password"]').first.fill(
            login_password
        )
        await page.locator('button[type="submit"]').click()
        try:
            await page.wait_for_function(
                "() => !location.pathname.includes('/login') && "
                "!document.querySelector('input[type=password]')",
                timeout=30_000,
            )
        except PlaywrightTimeoutError as exc:
            feedback = await page.locator('[role="alert"], [data-status="error"]').all_inner_texts()
            detail = " ".join(feedback).strip()
            raise RuntimeError(
                "O WeDrop não confirmou o login. Confira e-mail e senha"
                + (f": {detail}" if detail else ".")
            ) from exc

        await page.goto(f"{BASE_URL}/catalog", wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        if await page.locator('input[type="password"]').count():
            raise RuntimeError("Login não autorizado pelo WeDrop; sessão não foi salva.")
        await context.storage_state(path=str(STORAGE_STATE_FILE))
        print(f"Sessão autenticada salva em {STORAGE_STATE_FILE.name}.")

    async def get_categories(self, page) -> list[dict]:
        categories = []
        seen_urls = set()
        for link in await page.locator(CATEGORY_SELECTOR).all():
            href = await link.get_attribute("href")
            name_node = link.locator('p[class*="uniu7j"]').first
            name = (await name_node.inner_text()).strip() if await name_node.count() else ""
            if not name:
                name = (await link.inner_text()).strip()
            if not href or not name or href in seen_urls:
                continue

            count_node = link.locator('p[class*="1lser6l"]').first
            count_text = (
                (await count_node.inner_text()).strip()
                if await count_node.count()
                else ""
            )
            if not count_text:
                title = await link.get_attribute("title") or ""
                count_text = title.split("—", 1)[1] if "—" in title else ""
            count_match = re.search(r"\d[\d.,]*", count_text)
            categories.append(
                {
                    "name": name,
                    "url": urljoin(BASE_URL, href),
                    "count": _as_int(count_match.group()) if count_match else None,
                }
            )
            seen_urls.add(href)

        if not categories:
            raise RuntimeError(
                "Nenhuma categoria foi encontrada no catálogo autenticado. "
                "A coleta foi interrompida para não registrar um mapeamento vazio."
            )
        return categories

    async def _product_links_on_page(self, page) -> dict[str, str]:
        hrefs = await page.locator('a[href*="/catalog/"]').evaluate_all(
            "(anchors) => anchors.map((anchor) => anchor.href)"
        )
        links = {}
        for href in hrefs:
            product_id = product_id_from_url(href)
            if product_id:
                links.setdefault(product_id, href)
        return links

    async def _next_page(self, page):
        selectors = (
            'a[rel="next"]',
            'button[aria-label*="next" i]',
            'a[aria-label*="next" i]',
            'button[aria-label*="próxima" i]',
            'a[aria-label*="próxima" i]',
            'button:has-text("Próxima")',
            'button:has-text("Próximo")',
            'a:has-text("Próxima")',
            'a:has-text("Próximo")',
        )
        for selector in selectors:
            candidate = page.locator(selector).last
            if await candidate.count() and await candidate.is_visible():
                if await candidate.get_attribute("disabled") is None:
                    return candidate
        return None

    async def get_products_from_category(self, page, category: dict) -> dict[str, str]:
        await page.goto(category["url"], wait_until="domcontentloaded")
        await page.wait_for_timeout(1000)
        products: dict[str, str] = {}
        seen_pages: set[tuple[str, tuple[str, ...]]] = set()

        for _ in range(500):
            unchanged_rounds = 0
            previous_count = -1
            for _ in range(30):
                page_links = await self._product_links_on_page(page)
                products.update(page_links)
                if len(page_links) == previous_count:
                    unchanged_rounds += 1
                    if unchanged_rounds >= 2:
                        break
                else:
                    unchanged_rounds = 0
                    previous_count = len(page_links)
                await page.mouse.wheel(0, 1200)
                await page.wait_for_timeout(250)

            if category["count"] is not None and len(products) >= category["count"]:
                break

            signature = (page.url, tuple(sorted(products)))
            if signature in seen_pages:
                break
            seen_pages.add(signature)
            next_button = await self._next_page(page)
            if next_button is None:
                break
            before = len(products)
            await next_button.click()
            await page.wait_for_timeout(1000)
            page_links = await self._product_links_on_page(page)
            products.update(page_links)
            if len(products) == before:
                break
        return products

    async def get_product_details_and_history(
        self, page, product_id: str, product_url: str, category_name: str
    ) -> dict:
        await page.goto(product_url, wait_until="domcontentloaded")
        await page.wait_for_timeout(500)
        if await page.locator('input[type="password"]').count():
            raise RuntimeError(
                "A sessão WeDrop expirou durante a coleta. Execute novamente para "
                "autenticar e retomar o mapeamento."
            )

        name_node = page.locator("h1, h2").first
        name = (await name_node.inner_text()).strip() if await name_node.count() else ""
        if not name:
            name = (await page.title()).strip()
        page_text = await page.locator("body").inner_text()

        sku_ean_node = page.locator('p[class*="nk7nkj"]').first
        sku_ean_text = (
            (await sku_ean_node.inner_text()).strip()
            if await sku_ean_node.count()
            else page_text
        )
        sku_match = re.search(r"SKU:\s*([^|]+)", sku_ean_text, re.IGNORECASE)
        ean_match = re.search(r"EAN:\s*([^|]+)", sku_ean_text, re.IGNORECASE)
        price_node = page.locator('p[class*="1enygfq"], p[class*="1hulv5q"]').first
        price = (await price_node.inner_text()).strip() if await price_node.count() else ""
        availability_node = page.locator('span[class*="1dvt0g7"]').first
        availability = (
            (await availability_node.inner_text()).strip()
            if await availability_node.count()
            else ""
        )

        history_tab = page.get_by_role("tab", name=re.compile("Histórico de Estoque", re.I))
        if await history_tab.count():
            await history_tab.first.click()
            await page.wait_for_timeout(400)

        history = []
        history_rows = page.locator(
            "div.css-2p27im, [data-testid*='history-row'], [class*='historyRow']"
        )
        for row in await history_rows.all():
            type_node = row.locator('span[class*="1kghjv8"]').first
            quantity_node = row.locator('p[class*="1yd6l9q"]').first
            date_node = row.locator('p[class*="1dv5bo2"]').first
            movement_type = (
                (await type_node.inner_text()).strip() if await type_node.count() else ""
            )
            quantity = (
                (await quantity_node.inner_text()).strip()
                if await quantity_node.count()
                else ""
            )
            event_date = (
                (await date_node.inner_text()).strip() if await date_node.count() else ""
            )
            row_text = (await row.inner_text()).strip()
            nf_match = re.search(r"Chave da NF:\s*(.+)", row_text, re.IGNORECASE)
            if movement_type and quantity:
                history.append(
                    {
                        "type": movement_type,
                        "quantity": quantity,
                        "date": event_date,
                        "nf_key": nf_match.group(1).strip() if nf_match else "",
                    }
                )

        details = await extract_technical_specs(page)
        cnpj = value_for_label(page_text, ("CNPJ", "CNPJ do fornecedor"))
        origin = value_for_label(page_text, ("Estado de origem", "Origem"))
        stock = value_for_label(
            page_text,
            ("Estoque", "Disponibilidade", "Saldo disponível", "Estoque disponível"),
        ) or availability
        real_balance = value_for_label(page_text, ("Saldo real", "Saldo"))
        total_stock = value_for_label(page_text, ("Estoque total", "Total em estoque"))
        sales = value_for_label(page_text, ("Vendas", "Número de vendas", "Vendido"))
        status = value_for_label(page_text, ("Status", "Situação"))
        if not status and re.search(r"\b(desativado|inativo)\b", page_text, re.I):
            status = "Inativo"
        elif not status and re.search(r"\b(ativo|ativado)\b", page_text, re.I):
            status = "Ativo"

        return {
            "product_id": product_id,
            "name": name,
            "category": category_name,
            "url": product_url,
            "sku": sku_match.group(1).strip() if sku_match else details["sku"],
            "ean": ean_match.group(1).strip() if ean_match else details["ean"],
            "price": price or value_for_label(page_text, ("Preço",)),
            "availability": availability,
            "stock": stock,
            "total_stock_count": total_stock or details["total_stock_count"],
            "real_balance": real_balance or details["real_balance"],
            "is_active": status,
            "supplier": value_for_label(page_text, ("Fornecedor",)) or details["supplier"],
            "cnpj": cnpj or details["cnpj"],
            "origin_state": origin or details["origin_state"],
            "ncm": details["ncm"],
            "weight": details["weight"],
            "height": details["height"],
            "width": details["width"],
            "length": details["length"],
            "description": details["description"],
            "number_sales": sales or details["number_sales"],
            "stock_history": history,
        }

    async def run_full_mapping(
        self,
        email: str | None = None,
        password: str | None = None,
        prompt_for_credentials: bool = True,
    ) -> None:
        load_local_environment()
        supabase = SupabaseRepository.from_environment()
        captured_at = datetime.now().astimezone().isoformat(timespec="seconds")
        supabase.validate()
        print("Conexão e tabelas Supabase validadas.")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                if STORAGE_STATE_FILE.is_file():
                    context = await browser.new_context(
                        storage_state=str(STORAGE_STATE_FILE)
                    )
                else:
                    context = await browser.new_context()
                try:
                    page = await context.new_page()
                    await self.ensure_authenticated(
                        page, context, email, password, prompt_for_credentials
                    )
                    categories = await self.get_categories(page)
                    print(f"Categorias encontradas: {len(categories)}")
                    total_products = 0

                    for category_index, category in enumerate(categories, 1):
                        print(
                            f"[{category_index}/{len(categories)}] "
                            f"Mapeando {category['name']}..."
                        )
                        product_links = await self.get_products_from_category(
                            page, category
                        )
                        self.repository.save_category(
                            category, len(product_links), captured_at
                        )
                        supabase.save_category(
                            category, len(product_links), captured_at
                        )
                        products = []
                        for product_id, product_url in product_links.items():
                            product = await self.get_product_details_and_history(
                                page, product_id, product_url, category["name"]
                            )
                            products.append(product)
                            if len(products) == 50:
                                self.repository.save_products(products, captured_at)
                                supabase.save_products(products, captured_at)
                                total_products += len(products)
                                products = []
                        if products:
                            self.repository.save_products(products, captured_at)
                            supabase.save_products(products, captured_at)
                            total_products += len(products)
                        if (
                            category["count"] is not None
                            and len(product_links) < category["count"]
                        ):
                            print(
                                f"  AVISO: site informa {category['count']} itens; "
                                f"foram encontrados {len(product_links)} links."
                            )
                        print(f"  Produtos salvos: {len(product_links)}")

                    print(
                        f"Mapeamento concluído e sincronizado: "
                        f"{len(categories)} categorias, {total_products} produtos."
                    )
                    print("Destino local:", DB_FILE)
                    print("Destino remoto: Supabase (categorias, produtos e eventos)")
                finally:
                    await context.close()
            finally:
                supabase.close()
                await browser.close()

    def close(self) -> None:
        self.repository.close()


async def main() -> None:
    monitor = WedropMonitor()
    try:
        await monitor.run_full_mapping()
    finally:
        monitor.close()


if __name__ == "__main__":
    asyncio.run(main())
