# Scrapy settings for Site project
BOT_NAME = "Site"

SPIDER_MODULES = ["Site.spiders"]
NEWSPIDER_MODULE = "Site.spiders"

ADDONS = {}

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"

# Obey robots.txt rules
ROBOTSTXT_OBEY = False

# Concorrência (OTIMIZADO PARA VELOCIDADE)
CONCURRENT_REQUESTS_PER_DOMAIN = 2  # Aumentado de 1 para 2
CONCURRENT_REQUESTS = 4  # Aumentado de 2 para 4
DOWNLOAD_DELAY = 0.5  # Reduzido de 1.0 para 0.5

# Timeouts (REDUZIDOS PARA VELOCIDADE)
DOWNLOAD_TIMEOUT = 60  # Reduzido de 90 para 60
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 15000  # Reduzido de 20000 para 15000
PLAYWRIGHT_BROWSER_LAUNCH_TIMEOUT = 25000  # Reduzido de 30000 para 25000

# LIMITE PARA TESTES (desativado)
# CLOSESPIDER_ITEMCOUNT = 20

# Pipelines
ITEM_PIPELINES = {
    'Site.pipelines.SplitStockPipeline': 200,
}

FEED_EXPORT_ENCODING = "utf-8"

# --- ATIVAÇÃO DO PLAYWRIGHT (COM A CORREÇÃO DO 'https') ---
DOWNLOAD_HANDLERS = {
    "http": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler",
    "https": "scrapy_playwright.handler.ScrapyPlaywrightDownloadHandler", # <-- Corrigido (sem o '_')
}
# Esta linha é OBRIGATÓRIA para o Playwright funcionar
TWISTED_REACTOR = "twisted.internet.asyncioreactor.AsyncioSelectorReactor" 

# --- OPÇÕES DO NAVEGADOR (VERSÃO ESTÁVEL) ---
PLAYWRIGHT_LAUNCH_OPTIONS = {
    "headless": True,
    "args": [
        "--disable-dev-shm-usage",
        "--no-sandbox",
        "--disable-setuid-sandbox",
        "--disable-gpu",
        "--disable-software-rasterizer",
        "--disable-extensions",
    ],
    "timeout": 30000,
}

# Limita concorrência para evitar sobrecarga (ESTÁVEL)
PLAYWRIGHT_MAX_CONTEXTS = 1  # Estável: 1 contexto simultâneo
PLAYWRIGHT_MAX_PAGES_PER_CONTEXT = 1  # Estável: 1 página por contexto

# Configurações adicionais para estabilidade e performance
PLAYWRIGHT_ABORT_REQUEST = lambda req: req.resource_type in ["image", "media", "font", "stylesheet"] or (
    req.resource_type == "script" and any(x in req.url for x in ["analytics", "google-analytics", "facebook", "doubleclick", "ads"])
)