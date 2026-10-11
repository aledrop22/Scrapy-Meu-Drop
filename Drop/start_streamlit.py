#!/usr/bin/env python3
"""
🚀 Inicializador do App Streamlit
Executa validações antes de iniciar
"""

import os
import sys
import subprocess
from pathlib import Path


def verificar_dependencias():
    """Verifica se as dependências essenciais estão instaladas"""
    try:
        import streamlit
        import playwright
        import pandas
        return True
    except ImportError as e:
        print("❌ ERRO: Dependências não instaladas!")
        print(f"   {e}")
        print("\nExecute:")
        print("  pip install -r requirements.txt")
        return False


def verificar_autenticacao():
    """Verifica se o arquivo de autenticação existe"""
    if not os.path.exists('storage_state.json'):
        print("⚠️  AVISO: Arquivo 'storage_state.json' não encontrado!")
        print("\nVocê ainda pode usar o app, mas precisará fazer login.")
        print("Para fazer login automático, execute:")
        print("  python obter_cookie_novo_site.py")
        return False
    return True


def main():
    """Função principal"""
    print("=" * 60)
    print("🎯 Inicializador - Seu Armazém Drop - App Streamlit")
    print("=" * 60)
    print()

    # Verificar dependências
    print("📦 Verificando dependências...")
    if not verificar_dependencias():
        sys.exit(1)
    print("✅ Dependências OK\n")

    # Verificar autenticação
    print("🔐 Verificando autenticação...")
    verificar_autenticacao()
    print()

    # Iniciar Streamlit
    print("🚀 Iniciando Streamlit...")
    print("   Abrindo em: http://localhost:8501")
    print("\n   Pressione Ctrl+C para parar\n")

    try:
        subprocess.run(
            [sys.executable, "-m", "streamlit", "run", "app_streamlit.py"],
            check=False
        )
    except KeyboardInterrupt:
        print("\n\n👋 Encerrando...")
        sys.exit(0)
    except Exception as e:
        print(f"❌ ERRO: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
