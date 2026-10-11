# 🎯 App Streamlit - Seu Armazém Drop

Aplicação interativa para fazer scraping do novo site **Seu Armazém Drop**: https://app.seuarmazemdrop.com.br/dashboard/catalog

## 📋 Requisitos

- Python 3.12+
- Dependências instaladas (veja seção Instalação)
- Navegador Chromium (Playwright)

## 🚀 Instalação Rápida

### 1️⃣ Criar ambiente virtual (opcional, mas recomendado)

```bash
# Windows
py -m venv .venv
.\.venv\Scripts\activate

# Mac/Linux
python3 -m venv .venv
source .venv/bin/activate
```

### 2️⃣ Instalar dependências

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3️⃣ Instalar navegador Playwright

```bash
python -m playwright install chromium
```

## 🔐 Autenticação

### Passo 1: Editar script de autenticação

Abra `obter_cookie_novo_site.py` e configure suas credenciais:

```python
LOGIN_EMAIL = "seu_email@exemplo.com"  # ← ALTERE
SENHA_LOGIN = "sua_senha"              # ← ALTERE
```

### Passo 2: Executar autenticação

```bash
python obter_cookie_novo_site.py
```

Este script:
- Abrirá o navegador (não é headless)
- Fará login automaticamente
- Salvará o estado em `storage_state.json`
- Gerará um screenshot se houver erro

**Resultado esperado:** Arquivo `storage_state.json` criado com sucesso ✅

## 🎯 Executar o Streamlit

```bash
streamlit run app_streamlit.py
```

A aplicação abrirá automaticamente no navegador em `http://localhost:8501`

## 📖 Como Usar

### Interface Principal

1. **Sidebar (esquerda):**
   - Ajuste o número máximo de páginas a coletar (1-50)
   - Visualize o status da autenticação

2. **Área Principal:**
   - Clique em **"Começar Coleta de Dados"** para iniciar o scraping
   - Acompanhe o progresso em tempo real
   - Visualize preview dos dados coletados

3. **Downloads:**
   - Baixe os dados em formato **CSV** ou **JSON**
   - Dados também são salvos automaticamente em `dados_catalogo.json`

### Dados Coletados

O app coleta as seguintes informações de cada produto:

| Campo | Descrição |
|-------|-----------|
| `id` | ID do produto |
| `nome` | Nome do produto |
| `preco` | Preço |
| `estoque` | Quantidade em estoque |
| `categoria` | Categoria do produto |
| `status` | Status (ativo, inativo, etc.) |
| `data_scrapy` | Data/hora da coleta |

## 📊 Saída de Dados

### Arquivo JSON (`dados_catalogo.json`)

```json
{
  "timestamp": "2024-01-15T10:30:00.000000",
  "total_produtos": 250,
  "produtos": [
    {
      "id": "12345",
      "nome": "Produto 1",
      "preco": "R$ 99.90",
      "estoque": "15",
      "categoria": "Eletrônicos",
      "status": "ativo",
      "data_scrapy": "2024-01-15T10:30:00Z"
    }
  ]
}
```

## ⚙️ Configurações Avançadas

### Alterar número de páginas

Na sidebar, use o slider para controlar quantas páginas deseja coletar.

### Aumentar timeout

Se o scraping está sendo interrompido, aumente o timeout no código em `app_streamlit.py`:

```python
await page.goto(url, wait_until="domcontentloaded", timeout=45000)  # ← aumentar de 30000
```

### Modo headless

Para desabilitar o navegador visual durante o scraping, altere em `app_streamlit.py`:

```python
browser = await p.chromium.launch(headless=True)  # já está True por padrão
```

## 🐛 Solução de Problemas

### ❌ "Arquivo storage_state.json não encontrado"

**Solução:** Execute `python obter_cookie_novo_site.py` primeiro

### ❌ "Erro ao iniciar o navegador"

**Solução:** Instale o Playwright:
```bash
python -m playwright install chromium
```

### ❌ "Timeout ao fazer login"

**Solução:** 
1. Verifique a URL de login em `obter_cookie_novo_site.py`
2. Confirme suas credenciais
3. Verifique se sua internet está estável

### ⚠️ "Nenhum produto encontrado"

**Solução:**
1. O site pode ter alterado sua estrutura HTML
2. Atualize os seletores CSS em `app_streamlit.py` (procure por `querySelector`)
3. Inspione a página com F12 e identifique os seletores corretos

## 📝 Estrutura de Arquivos

```
Drop/
├── app_streamlit.py                 # ← App Streamlit principal
├── obter_cookie_novo_site.py        # ← Script de autenticação
├── storage_state.json               # ← Gerado automaticamente
├── dados_catalogo.json              # ← Dados coletados
└── requirements.txt                 # ← Dependências
```

## 🔄 Comparação com Scrapy Original

| Aspecto | Scrapy Original | Streamlit Novo |
|--------|-----------------|----------------|
| Interface | Terminal/Logs | Interface Web |
| Visualização | JSON/CSV manual | Tabelas e gráficos |
| Interatividade | Linha de comando | Botões e sliders |
| Download | Manual | Botões one-click |
| Agendamento | Cron/Scheduler | Manual |

## 📞 Suporte

Se encontrar problemas:

1. Verifique o console (terminal) para mensagens de erro
2. Inspione a página com `F12` no navegador
3. Execute `python obter_cookie_novo_site.py` novamente se a sessão expirou
4. Aumente o `initial_wait` nos timeouts

## 🎓 Notas Técnicas

### Por que Streamlit?

- ✅ Interface web moderna sem precisar de HTML/CSS
- ✅ Atualização em tempo real
- ✅ Fácil de compartilhar (pode rodar em qualquer máquina)
- ✅ Integração com pandas, matplotlib, etc.

### Por que Playwright?

- ✅ Suporta JavaScript (site usa JS para carregar dados)
- ✅ Gerencia cookies e sessões automaticamente
- ✅ Detecta quando página está totalmente carregada
- ✅ Funciona com sites modernos (React, Vue, Angular)

### Segurança

- ⚠️ **Nunca** commit das credenciais em `obter_cookie_novo_site.py`
- ⚠️ Arquivo `storage_state.json` contém cookies - mantenha privado
- ⚠️ Use `.gitignore` para ignorar esses arquivos

## 🚀 Próximas Melhorias

- [ ] Agendamento automático (execução periódica)
- [ ] Gráficos de análise em tempo real
- [ ] Integração com banco de dados
- [ ] Histórico completo de coletas
- [ ] Notificações por email
- [ ] API para integração com outros sistemas

## 📄 Licença

Este projeto é fornecido como está para fins educacionais.

---

**Versão:** 1.0  
**Data:** 2024-01-15  
**Autor:** Seu Armazém Drop Automation
