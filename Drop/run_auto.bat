@echo OFF
echo Iniciando automacao completa do Scraper Wedrop...

REM --- PASSO 1: Garantir que estamos na pasta correta ---
cd /D "%~dp0"
echo Estamos a executar a partir de: %CD%

REM --- PASSO 2: Executar o script de obtenção de cookie ---
echo (1/3) Atualizando o cookie de login...
py obter_cookie.py

IF %ERRORLEVEL% NEQ 0 (
    echo ERRO FATAL: O script 'obter_cookie.py' FALHOU.
    exit /b
)
echo Cookie atualizado com sucesso!

REM --- PASSO 3: Limpar dados antigos (JSON e DB) ---
IF EXIST transformacao\wedrop_data.db (
    echo Limpando wedrop_data.db antigo...
    del transformacao\wedrop_data.db
)

REM --- PASSO 4: Executar o Scraper (Scrapy) ---
echo (2/3) Executando o Scraper (wedrop)...
echo (Salvando progresso em data.json em tempo real...)

REM --- CORREÇÃO CONTRA CRASH/CONGELAMENTO (Funciona no Python 3.12) ---
set ASYNCIO_EVENT_LOOP=asyncio.SelectorEventLoop
REM Usamos -O (maiúsculo) para sobrescrever completamente e garantir output completo
py -m scrapy crawl wedrop -O data.json

REM (Pequena pausa para garantir que o Windows libere o arquivo)
timeout /t 2 /nobreak > NUL

IF NOT EXIST data.json (
    echo AVISO: O ficheiro data.json nao foi criado. O Scrapy falhou ou nao encontrou itens.
    goto :fim
)
echo Scraper finalizado.

REM --- PASSO 5: Executar a exportação para o Dashboard ---
echo (3/3) Exportando dados para SQLite (modo teste - sem Google Sheets)...
cd transformacao

REM --- MODO TESTE: Usa data_export_sqlite_only.py (sem Google Sheets) ---
py data_export_sqlite_only.py

REM --- MODO NORMAL (comentado): Descomente a linha abaixo para enviar ao Google Sheets ---
REM
cmd /c "py data_export.py"
cd ..

:fim
echo Automacao concluida!