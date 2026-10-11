#!/usr/bin/env python
"""
Entrypoint para Scrapy com workaround de event loop no Windows.
Este arquivo força ProactorEventLoop ANTES de qualquer coisa ser importada.
"""
import sys
import asyncio

# WORKAROUND CRÍTICO: Forçar ProactorEventLoop ANTES de importar Twisted/Scrapy
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        # Instala reactor asyncio usando um loop Proactor (necessário para subprocessos do Playwright)
        from twisted.internet import asyncioreactor
        asyncioreactor.install(asyncio.ProactorEventLoop())
    except Exception as e:
        print(f"Aviso: Não foi possível definir ProactorEventLoopPolicy ou instalar o reactor: {e}", file=sys.stderr)

# Agora sim importa Scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings

if __name__ == "__main__":
    settings = get_project_settings()
    process = CrawlerProcess(settings)
    process.crawl("wedrop")
    process.start()
