# SCRIPT TEMPORÁRIO - SOMENTE SQLITE (sem Google Sheets)
# Use este script se houver problemas de conectividade

import pandas as pd
import json
import sqlite3
import os
from datetime import datetime
import sys

# --- CONFIGURAÇÕES ---
INPUT_JSON_FILE = '../data.json' 
DB_NAME = 'meudrop_data.db'
TABLE_NAME = 'produtos_raspados'

def load_new_data(file_path):
    """Carrega os dados raspados HOJE (data.json)"""
    script_dir = os.path.dirname(__file__)
    json_path = os.path.normpath(os.path.join(script_dir, file_path))

    if not os.path.exists(json_path):
        print(f"ERRO: Arquivo JSON não encontrado em: {json_path}")
        return None
    
    with open(json_path, 'r', encoding='utf-8') as file:
        data = json.load(file)
    
    if not data:
        print("AVISO: Arquivo JSON está vazio.")
        return None
    
    df = pd.DataFrame(data)
    
    # Mapear colunas do JSON para formato final
    column_mapping = {
        'title': 'Produto',
        'price': 'Preço', 
        'stock': 'Estoque',
        'status_liquidacao': 'Liquidação',
        'numero_vendas': 'Qtd. Vendida',
        'product_id': 'ID do Produto',
        'ncm': 'NCM',
        'altura': 'Altura',
        'largura': 'Largura',
        'comprimento': 'Comprimento',
        'profundidade': 'Profundidade',
        'peso': 'Peso',
        'url': 'URL'
    }
    
    df = df.rename(columns=column_mapping)
    
    # Adicionar coluna de data atual
    df['Data da Coleta'] = datetime.now()
    
    print(f"Sucesso: {len(df)} novos produtos carregados do data.json.")
    return df

def load_old_data_from_sqlite(db_name, table_name):
    """Carrega dados históricos do SQLite local"""
    try:
        if not os.path.exists(db_name):
            print(f"AVISO: Base de dados {db_name} não existe. Criando nova.")
            return pd.DataFrame()
        
        conn = sqlite3.connect(db_name)
        df_historical = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        
        if df_historical.empty:
            print("AVISO: Base de dados SQLite está vazia.")
            return pd.DataFrame()
        
        # Converter data de string para datetime se necessário
        df_historical['Data da Coleta'] = pd.to_datetime(df_historical['Data da Coleta'])
        
        print(f"Sucesso: {len(df_historical)} registros históricos carregados do SQLite.")
        return df_historical
        
    except Exception as e:
        print(f"AVISO: Erro ao carregar dados históricos do SQLite: {e}")
        return pd.DataFrame()

def export_to_sql(df, db_name, table_name):
    """Salva dados combinados no SQLite"""
    try:
        conn = sqlite3.connect(db_name)
        df.to_sql(table_name, conn, if_exists='replace', index=False) 
        conn.close()
        print(f"Sucesso: Banco de dados SQL atualizado ({db_name}, Tabela: {table_name}).")
        print(f"📊 Total de registros salvos: {len(df)}")
    except Exception as e:
        print(f"ERRO ao salvar no SQLite: {e}")

def calculate_sales(df):
    """Processa os dados combinados"""
    print("Iniciando processamento dos dados...")
    
    # 1. Garantir tipos de dados corretos
    df['Data da Coleta'] = pd.to_datetime(df['Data da Coleta'])
    df['Estoque'] = pd.to_numeric(df['Estoque'], errors='coerce').fillna(0).astype(int)
    df['ID do Produto'] = df['ID do Produto'].astype(str)
    
    # 2. Ordenar para cálculo
    df.sort_values(by=['ID do Produto', 'Data da Coleta'], inplace=True)
    
    # 3. Remover duplicatas (caso o robô rode duas vezes no mesmo dia)
    df['Data_Pura'] = df['Data da Coleta'].dt.date
    df.drop_duplicates(subset=['ID do Produto', 'Data_Pura'], keep='last', inplace=True)
    
    # 4. Limpar coluna auxiliar
    df = df.drop(columns=['Data_Pura'])
    
    # 5. Reordenar colunas (até 'Peso')
    colunas_finais = [
        'Número Item',
        'Data da Coleta',
        'Produto',
        'Preço',
        'Estoque',
        'Liquidação',
        'Qtd. Vendida',
        'ID do Produto',
        'URL',
        'NCM',
        'Altura',
        'Largura',
        'Comprimento',
        'Profundidade',
        'Peso'
    ]
    
    # Adicionar coluna Qtd. Vendida se não existir
    if 'Qtd. Vendida' not in df.columns:
        df['Qtd. Vendida'] = 0
    
    # Adicionar coluna Número Item se não existir
    if 'Número Item' not in df.columns:
        df['Número Item'] = pd.NA
    
    # Reordenar e filtrar colunas
    df = df.reindex(columns=colunas_finais, fill_value='')
    
    # 6. Ordenar por data (novos no topo) e numerar por dia
    print("Ordenando por data (novos no topo) e numerando por dia...")
    df['__Dia'] = df['Data da Coleta'].dt.date
    df.sort_values(by=['__Dia', 'Data da Coleta'], ascending=[False, False], inplace=True)
    df['Número Item'] = df.groupby('__Dia').cumcount() + 1
    df['Número Item'] = df['Número Item'].astype('Int64')
    df = df.drop(columns=['__Dia'])
    
    print("Cálculos concluídos.")
    return df

if __name__ == "__main__":
    # Mudar para o diretório do script
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    # 1. Carregar dados novos
    df_novos_produtos = load_new_data(INPUT_JSON_FILE)
    
    if df_novos_produtos is None:
        print("Nenhum dado novo encontrado. A exportação foi interrompida.")
        sys.exit(1)
    
    # 2. Carregar dados antigos do SQLite
    df_historico = load_old_data_from_sqlite(DB_NAME, TABLE_NAME)
    
    # 3. Combinar dados
    if df_historico.empty:
        df_total_combinado = df_novos_produtos
        print("Nenhum histórico encontrado. Usando apenas dados novos.")
    else:
        df_total_combinado = pd.concat([df_historico, df_novos_produtos], ignore_index=True)
        print(f"Dados combinados: {len(df_historico)} históricos + {len(df_novos_produtos)} novos = {len(df_total_combinado)} total")
    
    # 4. Processar dados
    df_final_calculado = calculate_sales(df_total_combinado)
    
    # 5. Salvar no SQLite
    export_to_sql(df_final_calculado, DB_NAME, TABLE_NAME)
    
    print("\n✅ EXPORTAÇÃO CONCLUÍDA COM SUCESSO!")
    print(f"📁 Arquivo: {DB_NAME}")
    print(f"📊 Total de produtos: {len(df_final_calculado)}")
    print(f"📅 Dados mais recentes: {df_final_calculado['Data da Coleta'].max()}")