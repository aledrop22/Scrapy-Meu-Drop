import scrapy
from scrapy_playwright.page import PageMethod
from parsel import Selector
import re
from scrapy.loader import ItemLoader
from itemloaders.processors import TakeFirst, MapCompose
import time
import os
import datetime
import logging
import asyncio  # Para controle de timeout

SITE_HOST = "meudropbrasil.com"
STORAGE_STATE_FILE = 'storage_state.json' # Para carregar o estado completo

# Função para limpar espaços em branco
def clean_text(text):
    if text:
        return text.strip()
    return None

class ProductItem(scrapy.Item):
    # Campos que o scraper irá coletar
    item_number = scrapy.Field(output_processor=TakeFirst())
    title = scrapy.Field(output_processor=TakeFirst())
    price = scrapy.Field(output_processor=TakeFirst())
    stock = scrapy.Field(output_processor=TakeFirst())
    url = scrapy.Field(output_processor=TakeFirst())
    product_id = scrapy.Field(output_processor=TakeFirst())
    scrape_time = scrapy.Field(output_processor=TakeFirst()) 
    status_liquidacao = scrapy.Field(output_processor=TakeFirst())
    numero_vendas = scrapy.Field(output_processor=TakeFirst())
    ncm = scrapy.Field(output_processor=TakeFirst())
    altura = scrapy.Field(output_processor=TakeFirst())
    largura = scrapy.Field(output_processor=TakeFirst())
    comprimento = scrapy.Field(output_processor=TakeFirst())
    profundidade = scrapy.Field(output_processor=TakeFirst())
    peso = scrapy.Field(output_processor=TakeFirst())
    altura_sem_embalagem = scrapy.Field(output_processor=TakeFirst())
    largura_sem_embalagem = scrapy.Field(output_processor=TakeFirst())
    comprimento_sem_embalagem = scrapy.Field(output_processor=TakeFirst())
    profundidade_sem_embalagem = scrapy.Field(output_processor=TakeFirst())
    peso_sem_embalagem = scrapy.Field(output_processor=TakeFirst())
    altura_com_embalagem = scrapy.Field(output_processor=TakeFirst())
    largura_com_embalagem = scrapy.Field(output_processor=TakeFirst())
    comprimento_com_embalagem = scrapy.Field(output_processor=TakeFirst())
    profundidade_com_embalagem = scrapy.Field(output_processor=TakeFirst())
    peso_com_embalagem = scrapy.Field(output_processor=TakeFirst())

class MeudropSpider(scrapy.Spider):
    name = "meudrop"
    allowed_domains = [SITE_HOST]
    start_urls = [f"https://{SITE_HOST}/loja/"]
    
    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super(MeudropSpider, cls).from_crawler(crawler, *args, **kwargs)

        # --- LÓGICA DO STORAGE STATE (ESTÁVEL) ---
        if not os.path.exists(STORAGE_STATE_FILE):
            raise ValueError(f"!!! ERRO: Ficheiro '{STORAGE_STATE_FILE}' não encontrado! Execute o 'obter_cookie.py' primeiro. !!!")
            
        spider.storage_state = STORAGE_STATE_FILE
        spider.log(f"Storage state carregado de '{STORAGE_STATE_FILE}'. Cookies e localStorage incluídos.")
        # --- FIM LÓGICA DO STORAGE STATE ---

        spider.page_count = 0
        return spider

    # --- FUNÇÃO 1 (START): USA PLAYWRIGHT E STORAGE STATE ---
    def start_requests(self):
        url = self.start_urls[0]
        timestamp = int(time.time() * 1000)
        cache_busted_url = f"{url}?cache_buster={timestamp}"
        self.log(f"Usando URL com Cache Buster: {cache_busted_url}")
        
        yield scrapy.Request(
            cache_busted_url, 
            callback=self.parse, 
            dont_filter=True,
            meta=dict(
                playwright=True,
                playwright_stealth=True,
                playwright_include_page=True,
                playwright_context_kwargs={'storage_state': self.storage_state}, # Injeta o login
                playwright_page_goto_kwargs=dict(
                    wait_until="domcontentloaded",
                    timeout=30000 
                ),
                playwright_page_methods=[
                    PageMethod("wait_for_selector", "ul.products", timeout=10000) 
                ]
            )
        )

    # --- FUNÇÃO 2 (PARSE): RASPAGEM E LÓGICA DE PARADA ---
    async def parse(self, response):
        self.page_count += 1
        self.log(f"Iniciando o parse da listagem [PÁGINA {self.page_count}]: {response.url}")

        page = response.meta["playwright_page"]
        
        try:
            await page.wait_for_selector("ul.products li.product", timeout=10000)
            
            try:
                self.log(f"Esperando por tags 'Mais Vendido' (JS)...")
                await page.wait_for_selector("div.tag-vendas-produto", timeout=800)  # Otimizado para 800ms
                self.log(f"Tags 'Mais Vendido' encontradas.")
            except Exception:
                self.log(f"AVISO: Nenhuma tag 'Mais Vendido' encontrada apos 800ms (Pagina {self.page_count}).")

            page_content = await page.content()
            selector = Selector(text=page_content)

        except Exception as e:
            self.log(f"ERRO: Nao foi possivel carregar a lista de produtos na Pagina {self.page_count}. {e}", level=logging.ERROR)
            await page.close()
            return

        products = selector.css('li.product')
        self.log(f"Produtos encontrados nesta pagina: {len(products)}")
        if not products:
            self.log("Nenhum link de produto encontrado nesta pagina.")

        storage_state = self.storage_state
        
        zero_stock_counter = 0
        
        for product_count, product in enumerate(products, 1):
            
            class_string = product.attrib.get('class', '')
            is_out_of_stock = 'outofstock' in class_string

            if is_out_of_stock:
                zero_stock_counter += 1
                self.log(f"Produto sem estoque encontrado (Strike {zero_stock_counter}/3): {product.css('h2.woocommerce-loop-product__title::text').get()}")
            else:
                zero_stock_counter = 0 
                
                product_url = product.css('a.woocommerce-LoopProduct-link::attr(href)').get()
                title = product.css('h2.woocommerce-loop-product__title::text').get()

                if product_url:
                    texto_vendas_nodes = product.css('div.tag-vendas-produto::text').getall()
                    numero_de_vendas = '0' 
                    if texto_vendas_nodes:
                        full_text = " ".join(texto_vendas_nodes)
                        match = re.search(r'\d+', full_text) 
                        if match:
                            numero_de_vendas = match.group(0)

                    meta_data = dict(
                        product_title=clean_text(title) if title else 'Sem Titulo',
                        numero_de_vendas=numero_de_vendas, 
                        playwright=True,
                        playwright_stealth=True, 
                        playwright_context_kwargs={'storage_state': storage_state}, # Injeta o login
                        playwright_page_goto_kwargs=dict(
                            wait_until="domcontentloaded",
                            timeout=20000 # Otimizado para 20s
                        ),
                        playwright_include_page=True,
                        product_index=product_count,
                        is_retry=False
                    )
                    
                    yield scrapy.Request(
                        product_url,
                        callback=self.parse_product,
                        errback=self.parse_product_error,
                        meta=meta_data,
                        priority=0 
                    )
                    
            if zero_stock_counter >= 3:
                self.log("="*50)
                self.log(f"3 PRODUTOS CONSECUTIVOS COM ESTOQUE ZERO ENCONTRADOS.")
                self.log(f"Continuando raspagem: regra de interrupcao desativada.")
                self.log("="*50)
                # Não interrompe mais; apenas registra e segue
        
        # --- LÓGICA DE PAGINAÇÃO (REATIVADA) ---
        self.log(f"Procurando pela proxima pagina (botao 'next')...")
        
        # Regra de interrupção por estoque zero removida

        seletor_proxima_pagina = 'a.next.page-numbers::attr(href)'
        next_page_url = selector.css(seletor_proxima_pagina).get()

        await page.close() # Fecha a pagina de listagem atual
        
        if next_page_url:
            self.log(f"Proxima pagina (Pagina {self.page_count + 1}) encontrada: {next_page_url}")
            # Chama a função 'parse' novamente com a próxima URL
            yield scrapy.Request(
                url=next_page_url,
                callback=self.parse,
                dont_filter=True,
                meta=dict(
                    playwright=True,
                    playwright_stealth=True,
                    playwright_include_page=True,
                    playwright_context_kwargs={'storage_state': self.storage_state}, # Injeta o login
                    playwright_page_goto_kwargs=dict(
                        wait_until="domcontentloaded",
                        timeout=20000 # Reduzido para 20s para evitar travamentos
                    ),
                    playwright_page_methods=[
                        PageMethod("wait_for_selector", "ul.products", timeout=10000)
                    ]
                )
            )
        else:
            self.log("=" * 50)
            self.log("PAGINAÇÃO CONCLUIDA. Botao 'Proxima' nao encontrado.")
            self.log(f"Total de {self.page_count} paginas de listagem foram lidas.")
            self.log("=" * 50)


    # --- FUNÇÃO 3 (PARSE_PRODUCT) ---
    async def parse_product(self, response):
        self.log(f"Extraindo dados do produto (via Cookie): {response.url}")
        page = response.meta["playwright_page"]
        
        try: # Tenta fechar o pop-up "Entendido"
            await page.evaluate("() => { const button = document.querySelector('button#webbex-arp-entendido'); if (button) { button.click(); } }")
            await page.wait_for_timeout(200)  # Reduzido de 500ms para 200ms
        except Exception: pass

        # --- ESPERA PELO PREÇO (PROVA DE LOGIN) ---
        try:
            await page.wait_for_selector(
                "p.price, button[name='add-to-cart']", 
                timeout=3000  # Reduzido de 5s para 3s
            ) 
        except Exception:
            self.log(f"ERRO CRITICO: Nao foi possivel encontrar 'p.price' ou 'add-to-cart' em {response.url}. O Cookie pode ter EXPIRADO.", level=logging.ERROR)
            await page.close()
            return # Pula este item

        # --- LÓGICA DE 'LIQUIDAÇÃO' ---
        tags_list = []
        try:
            tag_locators = page.locator('span.tagged_as span.detail-content a')
            await tag_locators.first.wait_for(timeout=1000)  # Reduzido para 1s
            
            for tag in await tag_locators.all():
                tag_text = await tag.text_content()
                if tag_text:
                    tags_list.append(tag_text.strip().lower()) 
                    
        except Exception:
            self.log(f"AVISO: Nenhuma tag encontrada (ou timeout) em {response.url}.")
            pass 

        # Proteger page.content() com timeout para evitar travamento
        try:
            page_content = await asyncio.wait_for(page.content(), timeout=3.0)  # Reduzido de 5.0 para 3.0
        except asyncio.TimeoutError:
            self.log(f"ERRO: Timeout ao obter conteúdo da página {response.url}. Usando fallback.")
            page_content = await page.evaluate("() => document.documentElement.outerHTML")
        except Exception as e:
            self.log(f"ERRO ao obter conteúdo da página {response.url}: {e}")
            page_content = await page.evaluate("() => document.documentElement.outerHTML")
        
        # Fechar página com proteção contra erros de shutdown
        try:
            await asyncio.wait_for(page.close(), timeout=1.5)  # Reduzido de 3.0 para 1.5
        except asyncio.TimeoutError:
            self.log(f"AVISO: Timeout ao fechar página {response.url}. Página 'zumbi'.", level=logging.WARNING)
        except Exception as e:
            self.log(f"AVISO: Não foi possível fechar a página 'zumbi'. {e}", level=logging.WARNING)

        selector = Selector(text=page_content)
        loader = ItemLoader(item=ProductItem(), selector=selector)
        
        # Campo para numeração (será preenchido no data_export.py)
        loader.add_value('item_number', None)
        
        now = datetime.datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        loader.add_value('scrape_time', timestamp_str)

        loader.add_value('title', response.meta.get('product_title'))
        if loader.get_output_value('title') in ['Sem Titulo', None] or 'produto' in loader.get_output_value('title').lower():
                loader.replace_css('title', 'h1.product_title::text', MapCompose(clean_text))
        loader.add_value('url', response.url)

        price_texts_raw = selector.css('p.price *::text, div.summary .price *::text, .amount::text').getall()
        price = None
        for text in price_texts_raw:
                match = re.search(r'(\d[\d\.,]*)', text)
                if match:
                        cleaned_price = match.group(0).replace('.', '').replace(',', '.')
                        if re.match(r'^\d+\.\d{2}$', cleaned_price) or re.match(r'^\d+$', cleaned_price.split('.')[0]):
                                price = cleaned_price
                                break
        # Formatar price: remover zeros desnecessários
        if price:
            price_float = float(price)
            if price_float == int(price_float):
                price = str(int(price_float))
            else:
                price = f"{price_float:.2f}".rstrip('0').rstrip('.')
        loader.add_value('price', price if price else '0')
        if not price: self.log(f"AVISO: Preço nao encontrado em {response.url}.") 

        stock_raw = selector.css('p.stock::text').get()
        stock = '0'
        if stock_raw:
            stock_match = re.search(r'\d+', stock_raw)
            if stock_match: stock = stock_match.group(0)
            elif 'em estoque' in stock_raw.lower() or 'in stock' in stock_raw.lower(): stock = '1'
        loader.add_value('stock', stock)

        # Extrair descrição PRIMEIRO (antes de usar em outras buscas)
        desc_nodes = selector.css('div.woocommerce-product-details__short-description, div#tab-description, div.woocommerce-Tabs-panel--description, div.product .entry-content').xpath('.//text()').getall()
        desc_text = " ".join([clean_text(t) for t in desc_nodes if clean_text(t)]) if desc_nodes else ""

        ncm_value = None
        ncm_nodes = selector.xpath("//li[p[strong[contains(translate(., 'ncm', 'NCM'), 'NCM')]]]/p//text()" ).getall()
        if not ncm_nodes:
            ncm_nodes = selector.xpath("//p[strong[contains(translate(., 'ncm', 'NCM'), 'NCM')]]//text()").getall()
        if ncm_nodes:
            ncm_text = " ".join([clean_text(t) for t in ncm_nodes if clean_text(t)])
            ncm_match = re.search(r'(\d[\d\.]*)', ncm_text)
            if ncm_match:
                ncm_value = re.sub(r'[^\d]', '', ncm_match.group(1))
        
        if not ncm_value:
            ncm_strong_nodes = selector.xpath("//p[contains(text(), 'NCM')]//strong//text()").getall()
            if ncm_strong_nodes:
                for strong_text in ncm_strong_nodes:
                    strong_clean = clean_text(strong_text)
                    if strong_clean and re.match(r'^\d', strong_clean):
                        ncm_value = re.sub(r'[^\d]', '', strong_clean)
                        break
        
        # Tentar extrair do texto da descrição curta com múltiplos padrões (com ou sem dois-pontos)
        if not ncm_value and desc_text:
            # Padrão 1: "NCM: 9506.99.00" ou "NCM: 950699.00" (com dois-pontos)
            ncm_desc_match = re.search(r'NCM\s*:\s*(\d[\d\.]*)', desc_text, flags=re.I)
            if ncm_desc_match:
                ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
            else:
                # Padrão 2: "NCM 9506.99.00" ou "NCM 950699.00" (sem dois-pontos, com espaço)
                ncm_desc_match = re.search(r'NCM\s+(\d[\d\.]*)', desc_text, flags=re.I)
                if ncm_desc_match:
                    ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
                else:
                    # Padrão 3: Qualquer número de 8+ dígitos que pareça um NCM
                    ncm_desc_match = re.search(r'\b(\d{4}\.?\d{2}\.?\d{2})\b', desc_text)
                    if ncm_desc_match:
                        ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
        
        # Se ainda não encontrou, tenta busca direta na aba de descrição (#tab-description)
        if not ncm_value:
            tab_desc_nodes = selector.css('div#tab-description').xpath('.//text()').getall()
            tab_desc_text = " ".join([clean_text(t) for t in tab_desc_nodes if clean_text(t)]) if tab_desc_nodes else ""
            
            if tab_desc_text:
                # Mesmo padrão de busca na descrição longa
                ncm_desc_match = re.search(r'NCM\s*:\s*(\d[\d\.]*)', tab_desc_text, flags=re.I)
                if ncm_desc_match:
                    ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
                else:
                    ncm_desc_match = re.search(r'NCM\s+(\d[\d\.]*)', tab_desc_text, flags=re.I)
                    if ncm_desc_match:
                        ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
                    else:
                        ncm_desc_match = re.search(r'\b(\d{4}\.?\d{2}\.?\d{2})\b', tab_desc_text)
                        if ncm_desc_match:
                            ncm_value = re.sub(r'[^\d]', '', ncm_desc_match.group(1))
        
        # Armazenar apenas números (sem pontos)
        loader.add_value('ncm', ncm_value or '')

        def convert_weight(raw, unit):
            unit_l = unit.lower()
            if unit_l == 'g':
                try:
                    return str(float(raw.replace(',', '.')) / 1000)
                except Exception:
                    return raw
            return raw

        def extract_measure(label_list):
            for label in label_list:
                xpath = f"//li[p[strong[contains(translate(., '{label.lower()}', '{label.upper()}'), '{label.upper()}')]]]/p//text()"
                nodes = selector.xpath(xpath).getall()
                if not nodes:
                    xpath = f"//p[strong[contains(translate(., '{label.lower()}', '{label.upper()}'), '{label.upper()}')]]//text()"
                    nodes = selector.xpath(xpath).getall()
                if nodes:
                    text_joined = " ".join([clean_text(t) for t in nodes if clean_text(t)])
                    cleaned = re.sub(rf"{label}\s*:\s*", "", text_joined, flags=re.I)
                    match = re.search(r"(\d+[\.,]?\d*)", cleaned)
                    if match:
                        return match.group(1)
                    return cleaned or None
            return None

        altura_val = extract_measure(['ALTURA'])
        largura_val = extract_measure(['LARGURA'])
        comprimento_val = extract_measure(['COMPRIMENTO'])
        profundidade_val = extract_measure(['PROFUNDIDADE'])
        peso_val = extract_measure(['PESO'])

        if not altura_val or not largura_val or not profundidade_val:
            dims_label_nodes = selector.xpath("//p[strong[contains(translate(., 'dimensões', 'DIMENSÕES'), 'DIMENSÕES')]]//text()").getall()
            if dims_label_nodes:
                dims_label_text = " ".join([clean_text(t) for t in dims_label_nodes if clean_text(t)])
                dims_label_match = re.search(r"(\d+[\.,]?\d*)\s*(cm|mm|m)?\s*[xX]\s*(\d+[\.,]?\d*)\s*(cm|mm|m)?\s*[xX]\s*(\d+[\.,]?\d*)\s*(cm|mm|m)?", dims_label_text)
                if dims_label_match:
                    altura_val = altura_val or dims_label_match.group(1)
                    largura_val = largura_val or dims_label_match.group(3)
                    profundidade_val = profundidade_val or dims_label_match.group(5)
                    if not comprimento_val:
                        comprimento_val = profundidade_val

        if not altura_val or not largura_val or not profundidade_val:
            dims_abrev_nodes = selector.xpath("//p[contains(translate(., 'dimensões', 'DIMENSÕES'), 'DIMENSÕES')]//text()").getall()
            if dims_abrev_nodes:
                dims_abrev_text = " ".join([clean_text(t) for t in dims_abrev_nodes if clean_text(t)])
                dims_abrev_matches = re.findall(r"(\d+[\.,]?\d*)\s*(cm|mm)?\s*\(([ALCP])\)", dims_abrev_text, flags=re.I)
                if dims_abrev_matches:
                    dims_dict = {}
                    for val, unit, label in dims_abrev_matches:
                        dims_dict[label.upper()] = val
                    altura_val = altura_val or dims_dict.get('A')
                    largura_val = largura_val or dims_dict.get('L')
                    comprimento_val = comprimento_val or dims_dict.get('C') or dims_dict.get('P')
                    profundidade_val = profundidade_val or dims_dict.get('P') or dims_dict.get('C')

        if (not altura_val or not largura_val or not profundidade_val) and desc_text:
            dims_match = re.search(r"(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*(mm|cm|m)?", desc_text)
            if dims_match:
                altura_val = altura_val or dims_match.group(1)
                largura_val = largura_val or dims_match.group(2)
                profundidade_val = profundidade_val or dims_match.group(3)
                if not comprimento_val:
                    comprimento_val = profundidade_val

        if not peso_val and desc_text:
            peso_match = re.search(r"peso[^\d]{0,20}(\d+[\.,]?\d*)\s*(kg|g)", desc_text, flags=re.I)
            if peso_match:
                peso_raw = peso_match.group(1)
                unit = peso_match.group(2)
                peso_val = convert_weight(peso_raw, unit)

        sem_emb_dims = re.search(r"sem embalagem[^\n]*?(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*(mm|cm|m)?", desc_text, flags=re.I)
        com_emb_dims = re.search(r"com embalagem[^\n]*?(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*[xX]\s*(\d+[\.,]?\d*)\s*(mm|cm|m)?", desc_text, flags=re.I)
        sem_emb_peso = re.search(r"peso[^\n]*?sem embalagem[^\d]*(\d+[\.,]?\d*)\s*(kg|g)", desc_text, flags=re.I)
        com_emb_peso = re.search(r"peso[^\n]*?com embalagem[^\d]*(\d+[\.,]?\d*)\s*(kg|g)", desc_text, flags=re.I)

        altura_sem = largura_sem = profundidade_sem = comprimento_sem = None
        altura_com = largura_com = profundidade_com = comprimento_com = None
        peso_sem = peso_com = None

        if sem_emb_dims:
            altura_sem, largura_sem, profundidade_sem = sem_emb_dims.group(1), sem_emb_dims.group(2), sem_emb_dims.group(3)
            comprimento_sem = profundidade_sem
        if com_emb_dims:
            altura_com, largura_com, profundidade_com = com_emb_dims.group(1), com_emb_dims.group(2), com_emb_dims.group(3)
            comprimento_com = profundidade_com
        if sem_emb_peso:
            peso_sem = convert_weight(sem_emb_peso.group(1), sem_emb_peso.group(2))
        if com_emb_peso:
            peso_com = convert_weight(com_emb_peso.group(1), com_emb_peso.group(2))

        if altura_sem and not altura_val: altura_val = altura_sem
        if largura_sem and not largura_val: largura_val = largura_sem
        if profundidade_sem and not profundidade_val: profundidade_val = profundidade_sem
        if comprimento_sem and not comprimento_val: comprimento_val = comprimento_sem
        if peso_sem and not peso_val: peso_val = peso_sem

        loader.add_value('altura', altura_val)
        loader.add_value('largura', largura_val)
        loader.add_value('comprimento', comprimento_val)
        loader.add_value('profundidade', profundidade_val)
        loader.add_value('peso', peso_val)
        loader.add_value('altura_sem_embalagem', altura_sem)
        loader.add_value('largura_sem_embalagem', largura_sem)
        loader.add_value('comprimento_sem_embalagem', comprimento_sem)
        loader.add_value('profundidade_sem_embalagem', profundidade_sem)
        loader.add_value('peso_sem_embalagem', peso_sem)
        loader.add_value('altura_com_embalagem', altura_com)
        loader.add_value('largura_com_embalagem', largura_com)
        loader.add_value('comprimento_com_embalagem', comprimento_com)
        loader.add_value('profundidade_com_embalagem', profundidade_com)
        loader.add_value('peso_com_embalagem', peso_com)

        product_id_value = selector.css('button[name="add-to-cart"]::attr(value)').get()
        if product_id_value: loader.add_value('product_id', product_id_value)
        else:
            self.log(f"AVISO: Product ID nao encontrado em {response.url}")
            loader.add_css('product_id', 'a.single_add_to_cart_button::attr(data-product_id)')

        # --- SALVANDO OS NOVOS DADOS ---
        
        if 'liquidacao' in tags_list:
            loader.add_value('status_liquidacao', 'Sim')
        else:
            loader.add_value('status_liquidacao', 'Não')
        
        numero_vendas = response.meta.get('numero_de_vendas', '0')
        loader.add_value('numero_vendas', numero_vendas)
        
        yield loader.load_item()

    # --- FUNÇÃO 4 (ERRBACK): LÓGICA DE RETENTATIVA (COM CORREÇÃO) ---
    async def parse_product_error(self, failure):
        request = failure.request
        meta = request.meta
        url = request.url

        # --- CORREÇÃO: FECHA A PÁGINA QUE FALHOU ---
        page = failure.request.meta.get("playwright_page")
        if page:
            try:
                await asyncio.wait_for(page.close(), timeout=3.0)
                self.log(f"Página 'zumbi' (Timeout?) em {url} foi fechada.", level=logging.INFO)
            except asyncio.TimeoutError:
                self.log(f"Timeout ao fechar página 'zumbi' em {url}.", level=logging.WARNING)
            except Exception as e:
                self.log(f"Não foi possível fechar a página 'zumbi'. {e}", level=logging.WARNING)
        # --- FIM DA CORREÇÃO ---

        if meta.get('is_retry', False):
            self.log(f"ERRO FINAL (Passo 2): Falha ao raspar {url} mesmo na retentativa. DESISTINDO DESTE ITEM.", level=logging.ERROR)
            return

        else:
            self.log(f"AVISO (Passo 1): Falha ao baixar {url} (Timeout?). Re-agendando para o Passo 2 (prioridade baixa).", level=logging.WARNING)
            
            meta['is_retry'] = True
            
            yield scrapy.Request(
                url=url,
                callback=self.parse_product,
                errback=self.parse_product_error,
                meta=meta,
                dont_filter=True, 
                priority=-10 
            )