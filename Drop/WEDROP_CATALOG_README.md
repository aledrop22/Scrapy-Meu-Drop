# WeDrop Catalog Spider

Este spider foi criado para extrair dados do catálogo da WeDrop (https://dash.wedrop.com.br/catalog).

## Funcionalidades

1. **Mapeamento de Categorias**: Identifica todas as categorias disponíveis no catálogo com suas contagens de itens
2. **Detecção de Itens Ativos/Inativos**: Verifica quais itens estão ativos e quais estão desativados
3. **Histórico de Estoque**: Extrai o histórico de movimentação de estoque de cada item
4. **Saldo Real**: Calcula o saldo real de cada item (excluindo itens desativados do total)

## Arquivos

- `Site/spiders/wedrop_catalog.py` - Spider principal
- `Site/items.py` - Definição dos itens (WedropCatalogItem e WedropCategoryItem)
- `Site/pipelines.py` - Pipeline para separar categorias e produtos
- `obter_cookie_novo_site.py` - Script para obter autenticação
- `run_wedrop_catalog.bat` - Script para executar o spider

## Como Usar

### 1. Obter Autenticação

Primeiro, você precisa fazer login no site para obter o estado da sessão:

```bash
cd Drop
python obter_cookie_novo_site.py
```

Este script irá:
- Abrir o navegador
- Navegar para https://dash.wedrop.com.br/catalog
- Solicitar que você faça login manualmente (se necessário)
- Salvar o estado da sessão em `storage_state.json`

**IMPORTANTE**: Edite o arquivo `obter_cookie_novo_site.py` e configure suas credenciais:
```python
LOGIN_EMAIL = "seu_email@exemplo.com"
SENHA_LOGIN = "sua_senha"
```

### 2. Executar o Spider

Após obter a autenticação, execute o spider:

```bash
cd Drop
run_wedrop_catalog.bat
```

Ou manualmente:

```bash
cd Drop
scrapy crawl wedrop_catalog -o data_wedrop_catalog.json
```

### 3. Resultados

O spider irá gerar três arquivos:

- `wedrop_categories.json` - Lista de todas as categorias encontradas
- `wedrop_products.json` - Lista de todos os produtos com seus detalhes
- `data_wedrop_catalog.json` - Arquivo combinado (opcional)

## Estrutura dos Dados

### WedropCategoryItem

- `category_name` - Nome da categoria
- `category_count` - Quantidade de itens na categoria
- `category_url` - URL da categoria
- `scrape_time` - Timestamp da extração

### WedropCatalogItem

- `product_id` - ID do produto
- `title` - Título do produto
- `url` - URL do produto
- `category` - Categoria do produto
- `is_active` - "Sim" se ativo, "Não" se desativado
- `total_stock_count` - Contagem total de estoque (incluindo desativados)
- `real_balance` - Saldo real (excluindo desativados)
- `stock_history` - Histórico de movimentação de estoque
- `scrape_time` - Timestamp da extração
- `cnnpj` - CNPJ do fornecedor
- `estado_origem` - Estado de origem
- `numero_vendas` - Número de vendas

## Configurações

### Limitar Extração (para testes)

Edite `Site/settings.py` e descomente:

```python
CLOSESPIDER_PAGECOUNT = 3  # Parar após 3 páginas
# CLOSESPIDER_ITEMCOUNT = 100  # Parar após 100 itens
```

### Ajustar Concorrência

Se estiver tendo problemas de estabilidade, ajuste em `Site/settings.py`:

```python
CONCURRENT_REQUESTS_PER_DOMAIN = 1
CONCURRENT_REQUESTS = 2
DOWNLOAD_DELAY = 1.5
```

## Solução de Problemas

### Erro: storage_state.json não encontrado

Execute o script de autenticação:
```bash
python obter_cookie_novo_site.py
```

### Timeout ao navegar

Aumente o timeout em `Site/settings.py`:
```python
DOWNLOAD_TIMEOUT = 180
PLAYWRIGHT_DEFAULT_NAVIGATION_TIMEOUT = 60_000
```

### Cookies expirados

Se o spider falhar com erros de autenticação, execute novamente:
```bash
python obter_cookie_novo_site.py
```

## Notas Importantes

- O spider usa Playwright para renderização JavaScript
- O site pode ter proteções anti-bot, então use delays adequados
- Itens desativados são identificados automaticamente
- O saldo real é calculado subtraindo itens desativados do total
