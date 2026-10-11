@echo off
REM 🚀 Script para iniciar o Streamlit rapidamente

echo.
echo ============================================================
echo   🎯 Iniciando App Streamlit - Seu Armazem Drop
echo ============================================================
echo.

REM Verificar se dependencies estao instaladas
python -m pip list | find "streamlit" >nul
if errorlevel 1 (
    echo ❌ ERRO: Streamlit nao instalado!
    echo.
    echo Execute primeiro:
    echo   pip install streamlit
    echo.
    pause
    exit /b 1
)

REM Verificar se storage_state.json existe
if not exist storage_state.json (
    echo ⚠️  AVISO: arquivo 'storage_state.json' nao encontrado!
    echo.
    echo Execute primeiro:
    echo   python obter_cookie_novo_site.py
    echo.
    echo Continuando mesmo assim...
    echo.
)

echo ✅ Pronto!
echo.
echo 📌 Abrindo Streamlit em http://localhost:8501
echo.
echo Pressione Ctrl+C para parar
echo.

timeout /t 2

python -m streamlit run app_streamlit.py

pause
