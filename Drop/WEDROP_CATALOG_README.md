# Monitoramento do catálogo WeDrop

O fluxo principal está concentrado em `wedrop_monitor_sistema.py`: ele lê a configuração local, valida a sessão, autentica automaticamente quando necessário, mapeia todas as categorias e produtos e grava catálogo e histórico no SQLite e no Supabase. Não é preciso obter cookies antes nem executar um segundo scraper.

## Configuração inicial

1. Copie `.env.example` para `.env` dentro de `Drop`.
2. Preencha `WEDROP_EMAIL`, `WEDROP_PASSWORD`, `SUPABASE_URL` e `SUPABASE_SERVICE_ROLE_KEY`.
3. No SQL Editor do projeto Supabase, execute uma vez o conteúdo de `supabase_schema.sql`.
4. Instale as dependências: `python -m pip install -r requirements.txt`.
5. Execute o mapeamento integrado: `python wedrop_monitor_sistema.py`.

O arquivo `.env` e os cookies locais não devem ser enviados ao Git. A chave de serviço Supabase fica somente no processo local do scraper; não a coloque em JavaScript ou código do navegador.

O programa verifica a sessão do catálogo a cada execução. Se ela tiver expirado, usa as credenciais configuradas, valida o login, salva `storage_state.json` e continua a coleta na mesma execução. Em terminal interativo, e-mail e senha também podem ser solicitados sem gravar a senha; no painel, podem ser informados no formulário. O processo falha explicitamente se o login, a configuração do Supabase ou uma gravação remota falhar.

## Dados mantidos

- Categorias, contagem informada pelo site e quantidade de produtos encontrados.
- Identificador, título, categoria e URL do produto.
- SKU, EAN, preço, disponibilidade/estoque, saldo, situação, fornecedor, CNPJ, estado de origem, NCM, dimensões, peso, descrição e contador de vendas quando exibidos na página.
- Registros do histórico de estoque, com tipo de movimento, quantidade, data/hora original, data interpretada e chave da nota fiscal.

As tabelas `wedrop_categories`, `wedrop_products` e `wedrop_stock_events` recebem upserts idempotentes. Eventos repetidos em uma coleta diária não são contabilizados duas vezes. SQLite é mantido como cópia operacional local.

## Painel e rotina diária

Inicie o painel com `streamlit run app_monitoramento_vendas.py` ou `start_streamlit.bat`. Use **Atualizar catálogo e históricos** para executar a mesma coleta e renovar a sessão quando necessário. O painel mostra o ranking dos 20 produtos com mais saídas/vendas no dia, gráfico de vendas, entradas de estoque e cobertura por categoria.

Para manter a série diária, execute o scraper uma vez por dia pelo Agendador de Tarefas do Windows. O comando é `python wedrop_monitor_sistema.py`; ele faz autenticação, mapeamento e sincronização numa única execução.

## Troubleshooting

- **Supabase não configurado:** verifique as variáveis no `.env` e reinicie o terminal ou painel.
- **Tabela inexistente/permissão negada:** execute `supabase_schema.sql` no SQL Editor e mantenha a chave de serviço apenas no processo local.
- **Login recusado:** confira as credenciais; cookies só são salvos depois de confirmar a navegação autenticada.
- **Categoria com cobertura incompleta:** o painel compara o total reportado com os links de produtos encontrados; confira se o site carrega paginação/lazy-loading ou se mudou sua interface.
- **Histórico sem totais no gráfico:** eventos com data ilegível são preservados no banco, porém não podem ser agrupados por dia.

O spider Scrapy antigo continua no repositório por compatibilidade, mas não é usado pelos lançadores principais. Use o fluxo unificado acima.
