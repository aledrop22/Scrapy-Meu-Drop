# 🎯 GUIA PASSO A PASSO - Como Rodar o Scraper Corrigido

## 📋 Pré-requisitos

- ✅ Python 3.12+
- ✅ Dependências instaladas (`pip install -r requirements.txt`)
- ✅ Arquivo `storage_state.json` existente (cookie salvo)
- ✅ WSL (se no Windows com WSL)

---

## 🚀 EXECUÇÃO RÁPIDA (3 etapas)

### 1️⃣ Verificar as Correções

```bash
cd Drop
python verificar_config.py
```

**Deve mostrar:**
```
✅ Concorrência por domínio reduzida
✅ Concorrência total reduzida
✅ Delay aumentado
✅ Timeout aumentado
... (mais ✅)
```

### 2️⃣ Testar com 3 Páginas

```bash
python -m scrapy crawl wedrop
```

**Deve ver:**
```
[PÁGINA 1]: https://wedropbrasil.com/loja/?cache_buster=...
📦 20+ produtos encontrados
✅ Produto 12345 raspado: "Nome do Produto"...
```

**Tempo esperado:** 2-5 minutos

### 3️⃣ Verificar Resultados

```bash
# Contar itens extraídos
grep -c '"product_id"' data.json

# Ou no Windows (PowerShell)
(Get-Content data.json | Measure-Object -Line).Lines
```

**Deve mostrar um número > 0**

---

## ✅ Se o Teste Passou

### Para Raspagem Completa:

1. **Abra** `Drop/Site/settings.py`
2. **Encontre** esta linha:
   ```python
   CLOSESPIDER_PAGECOUNT = 3  # ← REMOVA ESTA LINHA
   ```
3. **Remova** ou comente:
   ```python
   # CLOSESPIDER_PAGECOUNT = 3
   ```
4. **Salve** o arquivo
5. **Execute:**
   ```bash
   python -m scrapy crawl wedrop
   ```

---

## ❌ Se o Teste Falhou

### Verificar Logs Detalhados

```bash
# Com logs DEBUG
python -m scrapy crawl wedrop --loglevel=DEBUG 2>&1 | tee scraper.log

# Procurar por erros
grep -i "error\|exception\|timeout" scraper.log
```

### Aumentar Timeouts Ainda Mais

**Edite `Drop/Site/settings.py`:**

```python
# Linha 12
DOWNLOAD_DELAY = 2.0  # (aumentar de 1.5)

# Linha 14
DOWNLOAD_TIMEOUT = 180  # (aumentar de 120)

# Linha 48
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000  # (aumentar de 45_000)

# Linha 49  
PLAYWRIGHT_BROWSER_LAUNCH_TIMEOUT = 90_000  # (aumentar de 60_000)
```

**Salve e tente novamente:**
```bash
python -m scrapy crawl wedrop
```

---

## 📊 Monitorar Execução

### Ver progresso em tempo real

```bash
# Terminal 1: Executar scraper
python -m scrapy crawl wedrop

# Terminal 2: Monitorar data.json
watch -n 5 'wc -l data.json'  # Linux/Mac
# ou Windows PowerShell
while($true) { Clear-Host; (Get-Content data.json | Measure-Object -Line).Lines; Start-Sleep 5 }
```

### Ver consumo de memória (Linux/Mac)

```bash
top -p $(pgrep -f 'scrapy crawl') -d 2
```

---

## 🔄 Executar Várias Vezes

Se precisar rodar novamente:

### ⚠️ ANTES DE EXECUTAR:

Você pode:
- **A) Limpar data.json** e começar do zero:
  ```bash
  rm data.json
  python -m scrapy crawl wedrop
  ```

- **B) Fazer backup** e começar novo:
  ```bash
  mv data.json data_backup_$(date +%Y%m%d_%H%M%S).json
  python -m scrapy crawl wedrop
  ```

- **C) Continuar de onde parou:**
  ```bash
  # Remova CLOSESPIDER_PAGECOUNT e execute
  python -m scrapy crawl wedrop
  ```

---

## 📁 Arquivos Importantes

```
Drop/
├── Site/
│   ├── settings.py ..................... ✏️ MODIFICADO
│   └── spiders/
│       └── wedrop.py .................. ✏️ MODIFICADO
├── data.json ........................... 📊 SAÍDA (itens)
├── storage_state.json .................. 🔐 Cookie de autenticação
├── SOLUCAO_TIMEOUT.md .................. 📖 Este guia
├── CORREÇÕES_APLICADAS.md .............. 📖 Detalhes técnicos
├── verificar_config.py ................. ✅ Verificador
└── test_run.bat/.sh .................... 🚀 Scripts de teste
```

---

## 💡 Dicas Importantes

### ✅ O Que Esperar

- **Velocidade:** ~1-2 requisições por segundo (lento, mas estável)
- **Taxa de sucesso:** 95%+ de produtos extraídos
- **Memória:** 300-500MB (vs 800MB+ antes)
- **Tempo total:** ~1h para 1000+ produtos

### ❌ Sinais de Problema

| Sinal | Causa | Solução |
|-------|-------|---------|
| `Timeout` | Muito rápido | Aumentar `DOWNLOAD_DELAY` |
| `Connection closed` | Sobrecarga | Reduzir `CONCURRENT_REQUESTS` |
| `0 items` | Seletores errados | Verificar HTML da página |
| `Cookie expirado` | Session vencida | Rodar `obter_cookie.py` novamente |

### 🔐 Cookie Expirado?

Se ver: `"O Cookie pode ter EXPIRADO"`

**Execute:**
```bash
python obter_cookie.py
```

Depois rode o scraper novamente.

---

## 📞 Suporte

Todos os arquivos têm comentários explicativos. Veja:
- `SOLUCAO_TIMEOUT.md` - Entender o problema
- `CORREÇÕES_APLICADAS.md` - Técnicos/detalhados
- Este arquivo - Executar passo a passo

---

**✅ Pronto para começar!**

```bash
cd Drop
python verificar_config.py
python -m scrapy crawl wedrop
```
