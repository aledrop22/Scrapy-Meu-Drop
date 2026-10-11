@echo off
cd /d "%~dp0"
echo ========================================
echo WeDrop Catalog Spider
echo ========================================
echo.
echo Verificando storage_state.json...
if not exist storage_state.json (
    echo ERRO: storage_state.json nao encontrado!
    echo Execute primeiro: python obter_cookie_novo_site.py
    pause
    exit /b 1
)
echo.
echo Iniciando spider...
scrapy crawl wedrop_catalog -o data_wedrop_catalog.json
echo.
echo Concluido! Dados salvos em data_wedrop_catalog.json
pause
