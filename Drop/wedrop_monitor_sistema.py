"""Map the authenticated WeDrop catalog and persist daily stock-history events."""

from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from sales_reporting import SalesRepository


BASE_URL = "https://dash.wedrop.com.br"
PROJECT_DIR = Path(__file__).resolve().parent
STORAGE_STATE_FILE = PROJECT_DIR / "storage_state.json"
DB_FILE = PROJECT_DIR / "wedrop_monitoramento.db"
CATEGORY_SELECTOR = 'a[draggable="false"][data-group=""]'
PRODUCT_PATH = re.compile(r"/catalog/(?:[^/?#]+/)*(\d+)(?:[/?#]|$)", re.IGNORECASE)


def product_id_from_url(url: str) -> str:
    match = PRODUCT_PATH.search(urlparse(url).path)
    return match.group(1) if match else ""


class WedropMonitor:
    def __init__(self, database_path: Path = DB_FILE):
        self.repository = SalesRepository(database_path)

    async def get_categories(self, page) -> list[dict]:
        await page.goto(f"{BASE_URL}/catalog", wait_until="domcontentloaded")
        await page.wait_for_timeout(1500)
        if await page.locator('input[type="password"]').count():
            raise RuntimeError(
                "A sessão WeDrop expirou ou não está autenticada. "
                "Atualize storage_state.json executando obter_cookie_novo_site.py."
            )

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
            count_text = (await count_node.inner_text()).strip() if await count_node.count() else ""
            if not count_text:
                title = await link.get_attribute("title") or ""
                count_text = title.split("—", 1)[1] if "—" in title else ""
            count_match = re.search(r"\d+", count_text)
            categories.append(
                {
                    "name": name,
                    "url": urljoin(BASE_URL, href),
                    "count": int(count_match.group()) if count_match else None,
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
            # Include lazy-loaded products before following pagination.
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
            await page.wait_for_timeout(800)
            products.update(await self._product_links_on_page(page))
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
                "A sessão WeDrop expirou durante a coleta. "
                "Atualize storage_state.json e execute novamente."
            )

        title_node = page.locator("h1, h2").first
        name = (await title_node.inner_text()).strip() if await title_node.count() else ""
        if not name:
            name = (await page.title()).strip()

        sku = ""
        sku_node = page.locator('p[class*="nk7nkj"]').first
        if await sku_node.count():
            sku_text = (await sku_node.inner_text()).strip()
            sku_match = re.search(r"SKU:\s*([^|]+)", sku_text, re.IGNORECASE)
            sku = sku_match.group(1).strip() if sku_match else ""

        price_node = page.locator('p[class*="1enygfq"], p[class*="1hulv5q"]').first
        price = (await price_node.inner_text()).strip() if await price_node.count() else ""
        stock_node = page.locator('span[class*="1dvt0g7"]').first
        stock = (await stock_node.inner_text()).strip() if await stock_node.count() else ""

        history_tab = page.get_by_role("tab", name=re.compile("Histórico de Estoque", re.I))
        if await history_tab.count():
            await history_tab.first.click()
            await page.wait_for_timeout(400)

        history = []
        for row in await page.locator("div.css-2p27im").all():
            type_node = row.locator('span[class*="1kghjv8"]').first
            quantity_node = row.locator('p[class*="1yd6l9q"]').first
            date_node = row.locator('p[class*="1dv5bo2"]').first
            movement_type = (await type_node.inner_text()).strip() if await type_node.count() else ""
            quantity = (await quantity_node.inner_text()).strip() if await quantity_node.count() else ""
            event_date = (await date_node.inner_text()).strip() if await date_node.count() else ""
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

        return {
            "product_id": product_id,
            "name": name,
            "category": category_name,
            "url": product_url,
            "sku": sku,
            "price": price,
            "stock": stock,
            "stock_history": history,
        }

    async def run_full_mapping(self) -> None:
        if not STORAGE_STATE_FILE.is_file():
            raise FileNotFoundError(
                f"Sessão não encontrada em {STORAGE_STATE_FILE}. "
                "Execute obter_cookie_novo_site.py para autenticar."
            )
        captured_at = datetime.now().isoformat(timespec="seconds")
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                context = await browser.new_context(storage_state=str(STORAGE_STATE_FILE))
                page = await context.new_page()
                categories = await self.get_categories(page)
                print(f"Categorias mapeadas: {len(categories)}")

                total_products = 0
                for index, category in enumerate(categories, 1):
                    print(f"[{index}/{len(categories)}] {category['name']}")
                    product_links = await self.get_products_from_category(page, category)
                    if category["count"] and len(product_links) < category["count"]:
                        print(
                            f"  AVISO: catálogo informa {category['count']} produtos; "
                            f"foram encontrados {len(product_links)} links."
                        )
                    self.repository.save_category(category, len(product_links), captured_at)
                    for product_id, product_url in product_links.items():
                        product = await self.get_product_details_and_history(
                            page, product_id, product_url, category["name"]
                        )
                        self.repository.save_product(product, captured_at)
                        total_products += 1
                    print(f"  Produtos mapeados: {len(product_links)}")

                print(
                    f"Mapeamento concluído: {len(categories)} categorias e "
                    f"{total_products} produtos processados."
                )
                print(f"Banco de dados: {DB_FILE}")
                print(
                    "Abra o painel diário com: "
                    "streamlit run app_monitoramento_vendas.py"
                )
                await context.close()
            finally:
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
