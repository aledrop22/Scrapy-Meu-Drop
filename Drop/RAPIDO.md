
# ⚡ EXECUÇÃO RÁPIDA - SEM BUROCRACIA

Copie e cole no terminal (dentro da pasta `Drop`):

## Windows (PowerShell/CMD)

```powershell
# Teste em 3 passos
python checklist.py
python -m scrapy crawl wedrop
findstr /c:"product_id" data.json | find /c "" > nul && echo ✅ Items extraídos! || echo ❌ Nenhum item
```

## Linux / Mac

```bash
# Teste em 3 passos
python checklist.py
python -m scrapy crawl wedrop
grep -c '"product_id"' data.json && echo "✅ Items extraídos!" || echo "❌ Nenhum item"
```

---

## Para Execução Completa (depois de validar):

### 1. Editar settings.py
```bash
# Windows
notepad Site\settings.py

# Linux/Mac
nano Site/settings.py
```

### 2. Encontrar e remover esta linha (linha ~13)
```python
CLOSESPIDER_PAGECOUNT = 3  # ← DELETE ESTA LINHA
```

### 3. Salvar e executar
```bash
python -m scrapy crawl wedrop
```

---

## Ver progresso em tempo real

**Windows (PowerShell):**
```powershell
while($true) { Clear-Host; (Get-Content data.json | Measure-Object -Line).Lines; Start-Sleep 5 }
```

**Linux/Mac:**
```bash
watch -n 5 'wc -l data.json'
```

---

## Se der erro

```bash
# Ver logs detalhados
python -m scrapy crawl wedrop --loglevel=DEBUG 2>&1 | tee scraper.log

# Procurar erros
grep -i "error\|exception\|timeout" scraper.log
```

---

**Pronto! Execute o primeiro comando acima** ⬆️
