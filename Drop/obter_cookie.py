import asyncio
import sys 
from playwright.async_api import async_playwright
import time
import os 

# (O bloco de correção do asyncio foi REMOVIDO daqui)

# --- Seus dados de login ---
LOGIN_EMAIL = "renidreshop@gmail.com"
MINHA_SENHA_DE_LOGIN = "&kT%cR9NFi1dkv"
# --------------------------

URL_LOGIN = 'https://wedrop.com.br/minha-conta/'
COOKIE_FILE = 'cookie.txt'
STORAGE_STATE_FILE = 'storage_state.json' 

async def get_and_save_cookie():
    print("Iniciando o navegador para obter o cookie...")
    async with async_playwright() as p:
        try:
            browser = await p.chromium.launch(headless=True) 
            context = await browser.new_context()
            page = await context.new_page()
        except Exception as e:
            print(f"ERRO: Falha ao iniciar o Playwright/Chromium. {e}")
            return False
        
        try:
            print(f"Navegando para: {URL_LOGIN}")
            await page.goto(URL_LOGIN)
            
            print("Preenchendo credenciais...")
            await page.fill('input[name="username"]', LOGIN_EMAIL)
            await page.fill('input[name="password"]', MINHA_SENHA_DE_LOGIN)
            
            print("Clicando em Login...")
            await page.click('button[name="login"]')
            
            print("Esperando confirmação de login (URL e seletor 'Sair')...")
            await page.wait_for_selector("a:text-is('Sair')", timeout=10000)
            print("Login confirmado!")

        except Exception as e:
            print(f"ERRO: Login falhou. Nao foi possivel encontrar o botao 'Sair' ou a pagina expirou. {e}")
            await browser.close()
            return False

        # Salva o Storage State (a forma moderna de salvar o login)
        await context.storage_state(path=STORAGE_STATE_FILE)
        print(f"SUCESSO: Storage state salvo em '{STORAGE_STATE_FILE}'")

        # Salva o cookie.txt (para compatibilidade com o Scrapy)
        all_cookies = await context.cookies()
        
        cookie_parts = []
        for cookie in all_cookies:
            if 'wedrop.com.br' in cookie['domain']:
                cookie_parts.append(f"{cookie['name']}={cookie['value']}")
        
        cookie_string = "; ".join(cookie_parts)
        
        if cookie_string:
            with open(COOKIE_FILE, 'w', encoding='utf-8') as f:
                f.write(cookie_string)
            print(f"SUCESSO: Cookie string salvo em '{COOKIE_FILE}' (compatibilidade)")
            await browser.close()
            return True
        else:
            print("ERRO: Nenhum cookie foi capturado apos o login.")
            await browser.close()
            return False

if __name__ == "__main__":
    
    if not asyncio.run(get_and_save_cookie()):
        sys.exit(1)