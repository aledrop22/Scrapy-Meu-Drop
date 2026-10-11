# Monitoramento diário do catálogo WeDrop

O monitor percorre as categorias do catálogo autenticado, abre todos os produtos encontrados em cada categoria e grava os detalhes e as movimentações do histórico em `wedrop_monitoramento.db`. Eventos já registrados não são duplicados em coletas futuras.

## Preparar a sessão

No terminal, a partir de `Drop`:

```powershell
python obter_cookie_novo_site.py
```

O navegador solicitará o e-mail e a senha sem salvar a senha em arquivo. Também é possível fornecer `WEDROP_EMAIL` e `WEDROP_PASSWORD` como variáveis de ambiente. A sessão autenticada é salva em `storage_state.json`; não compartilhe esse arquivo.

## Mapear o catálogo e atualizar históricos

Execute a coleta completa com:

```powershell
python wedrop_monitor_sistema.py
```

O processo interrompe com erro explícito se a sessão expirou ou se nenhuma categoria for encontrada. Ao final, informa quantas categorias e produtos foram processados. No banco, cada categoria registra também a quantidade informada pelo site e a quantidade de links de produto encontrados.

Para acompanhamento diário, execute esse comando uma vez por dia. No Windows, ele pode ser configurado no Agendador de Tarefas. A nova coleta atualiza o catálogo e acrescenta os eventos ainda não vistos, preservando o histórico.

## Ver ranking e gráfico

Inicie o painel:

```powershell
streamlit run app_monitoramento_vendas.py
```

O painel permite selecionar a data e apresenta:

- Os 20 produtos com mais unidades vendidas no dia e um gráfico de barras.
- O total diário de vendas nos últimos 14 dias em um gráfico de linha.
- As entradas de estoque registradas na data selecionada.
- A cobertura do mapeamento por categoria, comparando a contagem do site com os produtos encontrados.

O ranking soma as quantidades de movimentações identificadas como `Saída` ou `Venda` no histórico. Movimentações `Entrada` e `Recebimento` aparecem separadamente como entradas no estoque. Datas que não puderem ser interpretadas são preservadas no banco, mas não entram nos totais por dia.

## Arquivos gerados

- `wedrop_monitoramento.db` — categorias, produtos e histórico incremental.
- `storage_state.json` — sessão autenticada privada.

Para renovar a sessão expirada, execute novamente `obter_cookie_novo_site.py` e repita a coleta.
