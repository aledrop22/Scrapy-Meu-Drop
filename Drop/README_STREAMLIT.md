# Painel WeDrop

O painel atualmente recomendado é `app_monitoramento_vendas.py`. Ele mostra vendas diárias, entradas de estoque, os 20 produtos mais vendidos e a cobertura das categorias mapeadas.

## Executar

Configure `.env` conforme `.env.example`, execute uma vez `supabase_schema.sql` no Supabase e instale as dependências de `requirements.txt`. Depois inicie:

```powershell
streamlit run app_monitoramento_vendas.py
```

No painel, informe e-mail e senha WeDrop no formulário de atualização quando solicitado. Se a sessão salva estiver válida, o login é reutilizado; se estiver vencida, a coleta autentica novamente, salva os cookies e continua sem etapa separada.

O scraper grava no banco SQLite local e nas tabelas `wedrop_categories`, `wedrop_products` e `wedrop_stock_events` do Supabase. Falhas de configuração ou gravação remota são mostradas como erro.

Veja [WEDROP_CATALOG_README.md](./WEDROP_CATALOG_README.md) para configuração, campos mapeados e solução de problemas.
