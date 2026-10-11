#!/usr/bin/env python3
"""
🔐 Script para obter autenticação - WeDrop Catalog
Faz login no novo site e salva o estado da sessão
"""

import asyncio
import getpass
import sys
import os
from playwright.async_api import async_playwright

# ==================== CONFIGURAÇÕES ====================
URL_LOGIN = "https://dash.wedrop.com.br/login"
STORAGE_STATE_FILE = "storage_state.json"

# Workaround para Windows
if sys.platform == "win32":
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    except Exception as e:
        print(f"⚠️ Aviso: {e}")


async def obter_autenticacao(login_email, senha_login):
    """
    Faz login e salva o estado da sessão
    """
    print("🔐 Iniciando processo de autenticação...")
    print("📧 Usando credenciais informadas localmente.")

    async with async_playwright() as p:
        try:
            # Iniciar navegador
            browser = await p.chromium.launch(headless=False)  # headless=False para ver o navegador
            context = await browser.new_context()
            page = await context.new_page()

            # Navegar até o site
            print(f"🌐 Acessando: {URL_LOGIN}")
            await page.goto(URL_LOGIN, wait_until="domcontentloaded")

            # Aguardar um momento para ver se há página de login
            await page.wait_for_timeout(3000)

            # Verificar se estamos na página de login ou se já estamos logados
            current_url = page.url
            print(f"📍 URL atual: {current_url}")

            # Se já estivermos no catálogo, provavelmente já logado (via cookies anteriores)
            if 'catalog' in current_url and 'login' not in current_url:
                print("✅ Já parece estar no catálogo. Salvando estado atual...")
                await context.storage_state(path=STORAGE_STATE_FILE)
                print("✅ Estado salvo com sucesso!")
                await context.close()
                await browser.close()
                return True

            # Se estamos na página de login, fazer login
            print("📝 Página de login detectada. Preenchendo credenciais...")

            # Tentar diferentes seletores de email
            email_seletores = [
                'input[type="email"]',
                'input[name="email"]',
                'input[name="username"]',
                'input[id="email"]',
                'input[placeholder*="email"]',
                'input[placeholder*="Email"]',
            ]

            email_preenchido = False
            for seletor in email_seletores:
                try:
                    await page.fill(seletor, login_email)
                    email_preenchido = True
                    print(f"✅ Email preenchido com seletor: {seletor}")
                    break
                except:
                    continue

            if not email_preenchido:
                print("❌ Não foi possível preencher o email!")
                await browser.close()
                return False

            # Tentar diferentes seletores de senha
            senha_seletores = [
                'input[type="password"]',
                'input[name="password"]',
                'input[name="senha"]',
                'input[id="password"]',
            ]

            senha_preenchida = False
            for seletor in senha_seletores:
                try:
                    await page.fill(seletor, senha_login)
                    senha_preenchida = True
                    print(f"✅ Senha preenchida com seletor: {seletor}")
                    break
                except:
                    continue

            if not senha_preenchida:
                print("❌ Não foi possível preencher a senha!")
                await browser.close()
                return False

            # Clicar em Login
            print("🔑 Clicando em Login...")
            botao_seletores = [
                'button[type="submit"]',
                'button:has-text("Login")',
                'button:has-text("Entrar")',
                'input[type="submit"]',
                'a[href*="login"]',
            ]

            botao_clicado = False
            for seletor in botao_seletores:
                try:
                    await page.click(seletor)
                    botao_clicado = True
                    print(f"✅ Botão clicado com seletor: {seletor}")
                    break
                except:
                    continue

            if not botao_clicado:
                print("⚠️ Tentando enviar formulário com Enter...")
                await page.press('input[type="password"]', 'Enter')

            # Aguardar redirecionamento
            print("⏳ Aguardando confirmação de login...")
            try:
                await page.wait_for_url(
                    lambda url: "/catalog" in url and "/login" not in url,
                    timeout=15000,
                )
                print("✅ Login bem-sucedido! Catálogo carregado.")
            except:
                print("⚠️ Timeout ao aguardar catálogo. Verifique as credenciais.")
                await page.screenshot(path="login_screenshot.png")
                print("📸 Screenshot salvo em: login_screenshot.png")
                await context.close()
                await browser.close()
                return False

            # Aguardar alguns segundos para garantir o carregamento
            await page.wait_for_timeout(2000)

            # Salvar estado da sessão
            print(f"💾 Salvando estado em: {STORAGE_STATE_FILE}")
            await context.storage_state(path=STORAGE_STATE_FILE)
            print("✅ Estado salvo com sucesso!")

            await context.close()
            await browser.close()

            return True

        except Exception as e:
            print(f"❌ Erro: {e}")
            return False


def main():
    """Função principal"""
    print("=" * 70)
    print("🔐 AUTENTICADOR - WeDrop Catalog")
    print("=" * 70)

    # Verificar se já existe arquivo
    if os.path.exists(STORAGE_STATE_FILE):
        print(f"⚠️ Arquivo '{STORAGE_STATE_FILE}' já existe.")
        resposta = input("Deseja fazer login novamente? (s/n): ").lower()
        if resposta != 's':
            print("ℹ️ Usando arquivo existente.")
            return

    login_email = os.environ.get("WEDROP_EMAIL") or input("E-mail: ").strip()
    senha_login = os.environ.get("WEDROP_PASSWORD") or getpass.getpass("Senha: ")

    # Executar autenticação
    sucesso = asyncio.run(obter_autenticacao(login_email, senha_login))

    if sucesso:
        print("\n" + "=" * 70)
        print("✅ PRONTO! Você pode agora usar o spider wedrop_catalog")
        print("=" * 70)
        print("\nPara executar o scraper, use:")
        print("  python wedrop_monitor_sistema.py")
    else:
        print("\n" + "=" * 70)
        print("❌ Falha na autenticação")
        print("=" * 70)


if __name__ == "__main__":
    main()
