# Coluna "Vendas Dia" (Daily Sales)

## O que é?

A coluna "Vendas Dia" foi adicionada à planilha para rastrear as vendas diárias de cada produto, calculadas automaticamente pela diferença de estoque entre dias consecutivos.

## Como funciona?

Para cada produto (identificado pelo ID do Produto), o sistema:

1. Compara o estoque do dia atual com o estoque do dia anterior
2. Calcula: **Vendas Dia = Estoque Anterior - Estoque Atual**
3. Se o valor for negativo (entrada de estoque), mostra 0
4. No primeiro dia de cada produto, mostra 0 (sem dados anteriores)

## Exemplo:

### Produto A:
| Data | Estoque | Vendas Dia | Explicação |
|------|---------|------------|------------|
| 15/11 | 100 | 0 | Primeiro dia, sem dados anteriores |
| 16/11 | 95 | 5 | 100 - 95 = 5 vendas |
| 17/11 | 90 | 5 | 95 - 90 = 5 vendas |

### Produto B:
| Data | Estoque | Vendas Dia | Explicação |
|------|---------|------------|------------|
| 15/11 | 50 | 0 | Primeiro dia |
| 16/11 | 48 | 2 | 50 - 48 = 2 vendas |
| 17/11 | 48 | 0 | 48 - 48 = 0 vendas |

### Produto C (com entrada de estoque):
| Data | Estoque | Vendas Dia | Explicação |
|------|---------|------------|------------|
| 15/11 | 30 | 0 | Primeiro dia |
| 16/11 | 35 | 0 | 30 - 35 = -5 (entrada de estoque), mostra 0 |
| 17/11 | 32 | 3 | 35 - 32 = 3 vendas |

## Posição na Planilha

A coluna "Vendas Dia" aparece logo após a coluna "Estoque":

```
Número Item | Data da Coleta | Produto | Preço | Estoque | Vendas Dia | Liquidação | Qtd. Vendida | ID do Produto | URL
```

## Comportamento Importante

1. **Preserva a ordem**: A ordem dos produtos na planilha não é alterada
2. **Por produto**: Cada produto tem seu próprio histórico de vendas
3. **Entrada de estoque**: Quando o estoque aumenta, "Vendas Dia" mostra 0
4. **Dados históricos**: O cálculo funciona automaticamente com dados históricos existentes

## Teste

Para testar a funcionalidade, execute:

```bash
cd Drop/transformacao
python test_vendas_dia.py
```

Este teste verifica:
- ✅ Cálculo correto das vendas diárias
- ✅ Preservação da ordem dos produtos
- ✅ Posicionamento correto da coluna
- ✅ Tratamento de entrada de estoque (valores negativos)
