"""
Test script to verify the daily sales calculation logic.
This test creates sample data and verifies that:
1. Daily sales are calculated correctly (previous stock - current stock)
2. Product order is preserved
3. The new column appears in the correct position
"""

import pandas as pd
from datetime import datetime, timedelta
import sys
import os

# Add parent directory to path to import data_export functions
sys.path.insert(0, os.path.dirname(__file__))

def create_test_data():
    """Create sample data to test daily sales calculation"""
    
    # Create data for 3 products over 3 days
    # Product A: Stock goes from 100 -> 95 -> 90 (5 sales each day)
    # Product B: Stock goes from 50 -> 48 -> 48 (2 sales first day, 0 second day)
    # Product C: Stock goes from 30 -> 35 -> 32 (entry of stock, then 3 sales)
    
    today = datetime.now()
    yesterday = today - timedelta(days=1)
    two_days_ago = today - timedelta(days=2)
    
    data = [
        # Day 1 (two days ago)
        {'ID do Produto': '101', 'Produto': 'Product A', 'Estoque': 100, 'Preço': '10.00', 
         'Data da Coleta': two_days_ago, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/a'},
        {'ID do Produto': '102', 'Produto': 'Product B', 'Estoque': 50, 'Preço': '20.00',
         'Data da Coleta': two_days_ago, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/b'},
        {'ID do Produto': '103', 'Produto': 'Product C', 'Estoque': 30, 'Preço': '15.00',
         'Data da Coleta': two_days_ago, 'Liquidação': 'Sim', 'Qtd. Vendida': 0, 'URL': 'http://test.com/c'},
        
        # Day 2 (yesterday)
        {'ID do Produto': '101', 'Produto': 'Product A', 'Estoque': 95, 'Preço': '10.00',
         'Data da Coleta': yesterday, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/a'},
        {'ID do Produto': '102', 'Produto': 'Product B', 'Estoque': 48, 'Preço': '20.00',
         'Data da Coleta': yesterday, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/b'},
        {'ID do Produto': '103', 'Produto': 'Product C', 'Estoque': 35, 'Preço': '15.00',
         'Data da Coleta': yesterday, 'Liquidação': 'Sim', 'Qtd. Vendida': 0, 'URL': 'http://test.com/c'},
        
        # Day 3 (today)
        {'ID do Produto': '101', 'Produto': 'Product A', 'Estoque': 90, 'Preço': '10.00',
         'Data da Coleta': today, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/a'},
        {'ID do Produto': '102', 'Produto': 'Product B', 'Estoque': 48, 'Preço': '20.00',
         'Data da Coleta': today, 'Liquidação': 'Não', 'Qtd. Vendida': 0, 'URL': 'http://test.com/b'},
        {'ID do Produto': '103', 'Produto': 'Product C', 'Estoque': 32, 'Preço': '15.00',
         'Data da Coleta': today, 'Liquidação': 'Sim', 'Qtd. Vendida': 0, 'URL': 'http://test.com/c'},
    ]
    
    return pd.DataFrame(data)

def test_daily_sales_calculation():
    """Test the daily sales calculation"""
    
    print("="*80)
    print("TESTE: Cálculo de Vendas Diárias")
    print("="*80)
    
    # Import the calculate_sales function
    from data_export import calculate_sales
    
    # Create test data
    df = create_test_data()
    
    print("\n📊 Dados de Teste (antes do processamento):")
    print(df[['ID do Produto', 'Produto', 'Data da Coleta', 'Estoque']].to_string())
    
    # Process the data
    df_processed = calculate_sales(df)
    
    print("\n📊 Dados Processados (depois do processamento):")
    print(df_processed[['Número Item', 'Data da Coleta', 'Produto', 'Estoque', 'Vendas Dia']].to_string())
    
    # Verify the results
    print("\n" + "="*80)
    print("VERIFICAÇÕES:")
    print("="*80)
    
    # Check that Vendas Dia column exists
    assert 'Vendas Dia' in df_processed.columns, "❌ ERRO: Coluna 'Vendas Dia' não encontrada!"
    print("✅ Coluna 'Vendas Dia' existe")
    
    # Check column order
    expected_columns = ['Número Item', 'Data da Coleta', 'Produto', 'Preço', 'Estoque', 
                       'Vendas Dia', 'Liquidação', 'Qtd. Vendida', 'ID do Produto', 'URL']
    assert list(df_processed.columns) == expected_columns, f"❌ ERRO: Ordem das colunas incorreta! Esperado: {expected_columns}, Obtido: {list(df_processed.columns)}"
    print("✅ Ordem das colunas está correta")
    
    # Check that products are ordered by date (newest first)
    dates = df_processed['Data da Coleta'].dt.date.unique()
    assert list(dates) == sorted(dates, reverse=True), "❌ ERRO: Produtos não estão ordenados por data (mais novos primeiro)"
    print("✅ Produtos ordenados por data (mais novos primeiro)")
    
    # Verify daily sales calculations for specific products
    # For Product A on today: should have 5 sales (95 - 90)
    product_a_today = df_processed[
        (df_processed['ID do Produto'] == '101') & 
        (df_processed['Data da Coleta'].dt.date == datetime.now().date())
    ]
    if not product_a_today.empty:
        vendas_a = product_a_today['Vendas Dia'].iloc[0]
        assert vendas_a == 5, f"❌ ERRO: Product A vendas dia deveria ser 5, obtido: {vendas_a}"
        print(f"✅ Product A: Vendas Dia = {vendas_a} (correto: 95 - 90 = 5)")
    
    # For Product B on today: should have 0 sales (48 - 48)
    product_b_today = df_processed[
        (df_processed['ID do Produto'] == '102') & 
        (df_processed['Data da Coleta'].dt.date == datetime.now().date())
    ]
    if not product_b_today.empty:
        vendas_b = product_b_today['Vendas Dia'].iloc[0]
        assert vendas_b == 0, f"❌ ERRO: Product B vendas dia deveria ser 0, obtido: {vendas_b}"
        print(f"✅ Product B: Vendas Dia = {vendas_b} (correto: 48 - 48 = 0)")
    
    # For Product C on today: should have 3 sales (35 - 32)
    product_c_today = df_processed[
        (df_processed['ID do Produto'] == '103') & 
        (df_processed['Data da Coleta'].dt.date == datetime.now().date())
    ]
    if not product_c_today.empty:
        vendas_c = product_c_today['Vendas Dia'].iloc[0]
        assert vendas_c == 3, f"❌ ERRO: Product C vendas dia deveria ser 3, obtido: {vendas_c}"
        print(f"✅ Product C: Vendas Dia = {vendas_c} (correto: 35 - 32 = 3)")
    
    # For Product C on yesterday: should have 0 sales (negative value means stock entry)
    # 30 - 35 = -5, but we set negative values to 0
    product_c_yesterday = df_processed[
        (df_processed['ID do Produto'] == '103') & 
        (df_processed['Data da Coleta'].dt.date == (datetime.now() - timedelta(days=1)).date())
    ]
    if not product_c_yesterday.empty:
        vendas_c_yesterday = product_c_yesterday['Vendas Dia'].iloc[0]
        assert vendas_c_yesterday == 0, f"❌ ERRO: Product C vendas dia (ontem) deveria ser 0 (entrada de estoque), obtido: {vendas_c_yesterday}"
        print(f"✅ Product C (ontem): Vendas Dia = {vendas_c_yesterday} (correto: entrada de estoque = 0)")
    
    print("\n" + "="*80)
    print("✅ TODOS OS TESTES PASSARAM COM SUCESSO!")
    print("="*80)
    
    return df_processed

if __name__ == "__main__":
    # Change to script directory
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    
    try:
        result = test_daily_sales_calculation()
        print("\n✅ Teste concluído com sucesso!")
        sys.exit(0)
    except AssertionError as e:
        print(f"\n❌ ERRO NO TESTE: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERRO INESPERADO: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
