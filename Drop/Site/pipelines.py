# Define your item pipelines here
#
# Don't forget to add your pipeline to the ITEM_PIPELINES setting
# See: https://docs.scrapy.org/en/latest/topics/item-pipeline.html


# useful for handling different item types with a single interface
from itemadapter import ItemAdapter


class SitePipeline:
    def process_item(self, item, spider):
        return item

import json
import os

class SplitStockPipeline:
    def __init__(self):
        self.instock_file = None
        self.outofstock_file = None

    def open_spider(self, spider):
        base_dir = os.path.dirname(os.path.dirname(__file__))
        instock_path = os.path.join(base_dir, 'data_instock.json')
        outofstock_path = os.path.join(base_dir, 'data_outofstock.json')
        # Usar JSON lines para escrita incremental
        self.instock_file = open(instock_path, 'w', encoding='utf-8')
        self.outofstock_file = open(outofstock_path, 'w', encoding='utf-8')

    def close_spider(self, spider):
        if self.instock_file:
            self.instock_file.close()
        if self.outofstock_file:
            self.outofstock_file.close()

    def process_item(self, item, spider):
        try:
            stock_str = str(item.get('stock', '0') or '0')
            stock_val = 0
            try:
                stock_val = int(stock_str)
            except Exception:
                stock_val = 0

            target = self.instock_file if stock_val > 0 else self.outofstock_file
            target.write(json.dumps(item, ensure_ascii=False) + "\n")
        except Exception:
            # Em caso de erro, apenas segue sem interromper o fluxo
            pass
        return item


import logging

class GoogleSheetsBatchPipeline:

    # Tamanho do lote. Enviaremos os dados ao Google a cada 50 itens.
    # Isso evita os limites da API do Google.
    BATCH_SIZE = 50

    def __init__(self, google_sheet_name, google_worksheet_name, google_creds_file):
        self.google_sheet_name = google_sheet_name
        self.google_worksheet_name = google_worksheet_name
        self.google_creds_file = google_creds_file
        self.batch = []
        self.sheet = None
        self.logger = logging.getLogger(__name__)

    @classmethod
    def from_crawler(cls, crawler):
        # Puxa as configurações do seu arquivo settings.py
        return cls(
            google_sheet_name=crawler.settings.get('GOOGLE_SHEET_NAME'),
            google_worksheet_name=crawler.settings.get('GOOGLE_WORKSHEET_NAME', 'Dados_Brutos'), # 'Dados_Brutos' é o padrão
            google_creds_file=crawler.settings.get('GOOGLE_CREDS_FILE')
        )

    def open_spider(self, spider):
        # Esta função é executada UMA VEZ quando o robô inicia
        try:
            # Importa dependências apenas quando necessário, evitando erro se não instaladas
            import gspread
            from oauth2client.service_account import ServiceAccountCredentials
            # Autenticação
            scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
            creds = ServiceAccountCredentials.from_json_keyfile_name(self.google_creds_file, scope)
            client = gspread.authorize(creds)

            # Abre a planilha e a aba (worksheet)
            self.sheet = client.open(self.google_sheet_name).worksheet(self.google_worksheet_name)
            
            # Limpa a aba e escreve os cabeçalhos
            self.sheet.clear()
            headers = ['title', 'price', 'stock', 'product_id', 'url', 'scrape_time']
            self.sheet.append_row(headers)
            self.logger.info(f"Conectado ao Google Sheet '{self.google_sheet_name}'. Aba '{self.google_worksheet_name}' limpa e cabeçalhos escritos.")

        except Exception as e:
            self.logger.error(f"Falha ao conectar/preparar o Google Sheets: {e}")
            self.sheet = None # Desativa o pipeline se a conexão falhar

    def close_spider(self, spider):
        # Esta função é executada UMA VEZ quando o robô termina
        # Envia qualquer item restante no lote
        if self.sheet and self.batch:
            self.send_batch_to_sheets(spider)

    def process_item(self, item, spider):
        # Esta função é executada PARA CADA ITEM raspado
        if not self.sheet:
            return item # Retorna o item se a conexão com o Sheets falhou

        # Adiciona o item ao nosso lote
        # IMPORTANTE: A ordem DEVE ser a mesma dos cabeçalhos!
        row = [
            item.get('title'),
            item.get('price'),
            item.get('stock'),
            item.get('product_id'),
            item.get('url'),
            item.get('scrape_time')
        ]
        self.batch.append(row)

        # Se o lote atingiu o tamanho máximo, envia para a planilha
        if len(self.batch) >= self.BATCH_SIZE:
            self.send_batch_to_sheets(spider)

        return item # Sempre retorne o item para que outros pipelines (como o do SQL) possam usá-lo

    def send_batch_to_sheets(self, spider):
        try:
            # append_rows é muito mais rápido que append_row
            self.sheet.append_rows(self.batch)
            spider.log(f'Enviado um lote de {len(self.batch)} itens para o Google Sheets.')
            self.batch.clear()
        except Exception as e:
            self.logger.error(f"Erro ao enviar lote para o Google Sheets: {e}")