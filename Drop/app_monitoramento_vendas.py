"""Daily sales and stock-entry dashboard for the WeDrop catalog."""

from __future__ import annotations

import asyncio
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

from sales_reporting import SalesRepository, load_local_environment
from wedrop_monitor_sistema import DB_FILE, WedropMonitor

load_local_environment()

st.set_page_config(
    page_title="Monitoramento WeDrop",
    page_icon="📊",
    layout="wide",
)


def main() -> None:
    st.title("Monitoramento diário WeDrop")
    st.caption("Vendas e entradas de estoque extraídas do histórico dos produtos.")

    with st.sidebar:
        selected_day = st.date_input("Data do relatório", value=date.today())
        with st.form("catalog_sync"):
            login_email = st.text_input(
                "E-mail WeDrop",
                value=os.environ.get("WEDROP_EMAIL", ""),
            )
            login_password = st.text_input(
                "Senha WeDrop",
                value=os.environ.get("WEDROP_PASSWORD", ""),
                type="password",
            )
            start_mapping = st.form_submit_button(
                "Atualizar catálogo e históricos", type="primary"
            )
        if start_mapping:
            monitor = WedropMonitor()
            try:
                with st.spinner("Mapeando categorias e históricos de produtos..."):
                    asyncio.run(
                        monitor.run_full_mapping(
                            email=login_email,
                            password=login_password,
                            prompt_for_credentials=False,
                        )
                    )
                st.success("Mapeamento concluído.")
            except Exception as exc:
                st.error(f"Falha na coleta: {exc}")
            finally:
                monitor.close()

    if not Path(DB_FILE).exists():
        st.info("Ainda não há coleta salva. Atualize o catálogo para iniciar o histórico.")
        return

    repository = SalesRepository(DB_FILE)
    try:
        categories = repository.categories()
        sales = repository.sales_for_day(selected_day)
        entries = repository.stock_entries_for_day(selected_day)
        daily_sales = repository.daily_sales(selected_day)

        col1, col2, col3 = st.columns(3)
        col1.metric("Categorias mapeadas", len(categories))
        col2.metric("Produtos com venda no dia", len(sales))
        col3.metric("Unidades vendidas no dia", sum(row["units_sold"] for row in sales))

        st.subheader(f"20 produtos mais vendidos — {selected_day:%d/%m/%Y}")
        if sales:
            sales_df = pd.DataFrame([dict(row) for row in sales])
            st.bar_chart(sales_df.set_index("name")["units_sold"], height=420)
            st.dataframe(
                sales_df.rename(
                    columns={
                        "product_id": "ID",
                        "name": "Produto",
                        "category": "Categoria",
                        "sku": "SKU",
                        "units_sold": "Unidades vendidas",
                        "sale_events": "Registros de venda",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Nenhuma saída/venda com data legível foi registrada para esse dia.")

        st.subheader("Vendas por dia — últimos 14 dias")
        if daily_sales:
            daily_df = pd.DataFrame([dict(row) for row in daily_sales])
            daily_df["day"] = pd.to_datetime(daily_df["day"])
            st.line_chart(daily_df.set_index("day")["units_sold"], height=300)
        else:
            st.info("O gráfico aparecerá depois que houver registros de venda.")

        st.subheader(f"Entradas no estoque — {selected_day:%d/%m/%Y}")
        if entries:
            entries_df = pd.DataFrame([dict(row) for row in entries]).rename(
                columns={
                    "name": "Produto",
                    "category": "Categoria",
                    "quantity": "Unidades recebidas",
                    "event_at": "Data e hora",
                    "movement_type": "Movimentação",
                }
            )
            st.dataframe(entries_df, hide_index=True, use_container_width=True)
        else:
            st.info("Nenhuma entrada de estoque foi registrada para esse dia.")

        st.subheader("Cobertura do mapeamento por categoria")
        if categories:
            categories_df = pd.DataFrame([dict(row) for row in categories])
            categories_df["cobertura"] = categories_df.apply(
                lambda row: (
                    "OK"
                    if row["expected_products"] is None
                    or row["mapped_products"] >= row["expected_products"]
                    else "Incompleta"
                ),
                axis=1,
            )
            st.dataframe(
                categories_df.rename(
                    columns={
                        "name": "Categoria",
                        "expected_products": "Produtos informados",
                        "mapped_products": "Produtos mapeados",
                        "updated_at": "Última coleta",
                        "cobertura": "Cobertura",
                    }
                ),
                hide_index=True,
                use_container_width=True,
            )
        else:
            st.info("Nenhuma categoria foi mapeada ainda.")
    finally:
        repository.close()


if __name__ == "__main__":
    main()
