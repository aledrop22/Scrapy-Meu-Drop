Projeto Scrapy para coletar dados do site Meu Drop Brasil.

## Ambiente (Windows)
- Instale Python 3.12 (marque "Add Python to PATH").
- Opcional, porém recomendado: crie um ambiente virtual
	- `py -m venv .venv`
	- `.\.venv\Scripts\activate`
- Instale dependências a partir da pasta `Drop`:
	- `py -m pip install --upgrade pip`
	- `py -m pip install -r requirements.txt`
- Instale o navegador do Playwright:
	- `py -m playwright install chromium`

## Execução resumida
1) Dentro de `Drop`, obtenha o cookie/login (gera `storage_state.json`):
	 - `py obter_cookie.py`
2) Rode o fluxo completo:
	 - `run_auto.bat`

## Notas
- As credenciais do login estão em `Drop/obter_cookie.py`.
- O scraper e o Playwright estão otimizados para Python 3.12.
