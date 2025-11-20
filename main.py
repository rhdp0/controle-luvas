import json
import math
from collections import Counter
from datetime import date
from io import BytesIO

import pandas as pd
import plotly.express as px
import pygsheets
import streamlit as st
from fpdf import FPDF


def carregar_dados() -> pd.DataFrame:
    service_account_info = dict(st.secrets["gcp_service_account"])
    service_account_json = json.dumps(service_account_info)
    credenciais = pygsheets.authorize(service_account_json=service_account_json)

    file_path = "https://docs.google.com/spreadsheets/d/1dP5615dw8FXX6QDHOYZr6hYTw6qmU90GwJAnpeOGU_I/"
    file = credenciais.open_by_url(file_path)
    sheet = file.worksheet_by_title("2025")
    data = sheet.get_all_values()

    header = data[0]
    rows = data[1:]

    counter = Counter()
    new_header = []

    for name in header:
        name = name.strip()
        if name == "":
            name = "Coluna_vazia"
        counter[name] += 1
        if counter[name] > 1:
            name = f"{name}_{counter[name]}"
        new_header.append(name)

    df_loaded = pd.DataFrame(rows, columns=new_header)
    df_loaded = df_loaded.loc[:, (df_loaded != "").any(axis=0)]
    return df_loaded


def preparar_dados(df_raw: pd.DataFrame) -> pd.DataFrame:
    colunas = {
        "Data": "Data",
        "Dia da Semana": "Dia da Semana",
        "Profissional": "Profissional",
        "Pacotes em Estoque (inicial)": "Pacotes em Estoque (inicial)",
        "Tamanhos/tipo luvas": "Tamanhos/tipo luvas",
        "Luvas por Atendimento": "Luvas por Atendimento",
        "Luvas Extras": "Luvas Extras",
        "Total Usado no Dia": "Total Usado no Dia",
        "Saldo Final": "Saldo Final",
        "Observações": "Observações",
    }

    df = df_raw.rename(columns=colunas).copy()
    df["Data"] = pd.to_datetime(df.get("Data"), format="%d/%m/%Y", errors="coerce")

    numericas = [
        "Pacotes em Estoque (inicial)",
        "Luvas por Atendimento",
        "Luvas Extras",
        "Total Usado no Dia",
        "Saldo Final",
    ]
    for coluna in numericas:
        df[coluna] = pd.to_numeric(df.get(coluna), errors="coerce")

    df.sort_values("Data", inplace=True)
    df.reset_index(drop=True, inplace=True)
    return df


def indicadores(df: pd.DataFrame) -> dict:
    total_usado = df["Total Usado no Dia"].sum()
    media_diaria = df.groupby(df["Data"].dt.date)["Total Usado no Dia"].sum().mean()
    extras_total = df["Luvas Extras"].sum()
    saldo_atual = df["Saldo Final"].dropna().iloc[-1] if not df["Saldo Final"].dropna().empty else float("nan")
    aproveitamento_extras = (extras_total / total_usado * 100) if total_usado else 0

    return {
        "total_usado": total_usado,
        "media_diaria": media_diaria,
        "extras_total": extras_total,
        "aproveitamento_extras": aproveitamento_extras,
        "saldo_atual": saldo_atual,
    }


def criar_graficos(df: pd.DataFrame) -> dict:
    serie_diaria = df.groupby("Data", as_index=False)["Total Usado no Dia"].sum()
    uso_por_profissional = df.groupby("Profissional", as_index=False)["Total Usado no Dia"].sum()
    uso_por_tipo = df.groupby(["Data", "Tamanhos/tipo luvas"], as_index=False)["Total Usado no Dia"].sum()
    saldo_diario = df.groupby("Data", as_index=False)["Saldo Final"].mean()

    grafico_serie = px.line(
        serie_diaria,
        x="Data",
        y="Total Usado no Dia",
        markers=True,
        title="Consumo diário de luvas",
    )

    grafico_profissional = px.bar(
        uso_por_profissional,
        x="Profissional",
        y="Total Usado no Dia",
        title="Consumo por profissional",
        text_auto=True,
    )

    grafico_tipo = px.area(
        uso_por_tipo,
        x="Data",
        y="Total Usado no Dia",
        color="Tamanhos/tipo luvas",
        groupnorm="fraction",
        title="Distribuição do uso por tamanho/tipo",
    )

    grafico_saldo = px.line(
        saldo_diario,
        x="Data",
        y="Saldo Final",
        markers=True,
        title="Saldo final diário",
    )

    for chart in [grafico_serie, grafico_profissional, grafico_tipo, grafico_saldo]:
        chart.update_layout(hovermode="x unified")

    return {
        "grafico_serie": grafico_serie,
        "grafico_profissional": grafico_profissional,
        "grafico_tipo": grafico_tipo,
        "grafico_saldo": grafico_saldo,
    }


def figuras_pdf(df: pd.DataFrame) -> list[tuple[str, BytesIO]]:
    from matplotlib import pyplot as plt

    figuras = []

    serie_diaria = df.groupby("Data", as_index=False)["Total Usado no Dia"].sum()
    fig1, ax1 = plt.subplots(figsize=(6, 3.5))
    ax1.plot(serie_diaria["Data"], serie_diaria["Total Usado no Dia"], marker="o", color="#4C6EF5")
    ax1.set_title("Consumo diário")
    ax1.set_ylabel("Total de luvas")
    ax1.tick_params(axis="x", rotation=45, ha="right")
    ax1.grid(True, axis="both", alpha=0.3)
    buf1 = BytesIO()
    fig1.savefig(buf1, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig1)
    buf1.seek(0)
    figuras.append(("Consumo diário", buf1))

    consumo_prof = df.groupby("Profissional", as_index=False)["Total Usado no Dia"].sum()
    fig2, ax2 = plt.subplots(figsize=(6, 3.5))
    ax2.bar(consumo_prof["Profissional"], consumo_prof["Total Usado no Dia"], color="#4C6EF5")
    ax2.set_title("Consumo por profissional")
    ax2.set_ylabel("Total de luvas")
    ax2.tick_params(axis="x", rotation=45, ha="right")
    buf2 = BytesIO()
    fig2.savefig(buf2, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig2)
    buf2.seek(0)
    figuras.append(("Consumo por profissional", buf2))

    saldo_diario = df.groupby("Data", as_index=False)["Saldo Final"].mean()
    fig3, ax3 = plt.subplots(figsize=(6, 3.5))
    ax3.plot(saldo_diario["Data"], saldo_diario["Saldo Final"], marker="o", color="#12B886")
    ax3.set_title("Evolução do saldo final")
    ax3.set_ylabel("Saldo final")
    ax3.tick_params(axis="x", rotation=45, ha="right")
    ax3.grid(True, axis="both", alpha=0.3)
    buf3 = BytesIO()
    fig3.savefig(buf3, format="png", dpi=300, bbox_inches="tight")
    plt.close(fig3)
    buf3.seek(0)
    figuras.append(("Evolução do saldo final", buf3))

    return figuras


def gerar_pdf(df: pd.DataFrame, kpis: dict) -> BytesIO:
    def sanitize_value(value, use_dash: bool = False):
        if pd.notna(value) and isinstance(value, (int, float)) and math.isfinite(value):
            return value
        return "-" if use_dash else 0

    def format_metric(value, fmt: str, use_dash: bool = False):
        sanitized = sanitize_value(value, use_dash)
        if isinstance(sanitized, str):
            return sanitized
        return fmt.format(sanitized)

    total_usado = format_metric(kpis.get("total_usado"), "{:.0f}")
    media_diaria = format_metric(kpis.get("media_diaria"), "{:.1f}")
    extras_total = format_metric(kpis.get("extras_total"), "{:.0f}")
    aproveitamento_extras = format_metric(kpis.get("aproveitamento_extras"), "{:.1f}")
    saldo_atual = format_metric(kpis.get("saldo_atual"), "{:.0f}", use_dash=True)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "Relatório de Uso de Luvas", ln=True, align="C")

    pdf.set_font("Arial", size=11)
    pdf.cell(0, 8, f"Data de geração: {date.today().strftime('%d/%m/%Y')}", ln=True)
    pdf.ln(2)

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "Indicadores-chave", ln=True)
    pdf.set_font("Arial", size=11)
    pdf.multi_cell(0, 7, f"Total usado: {total_usado} luvas")
    pdf.multi_cell(0, 7, f"Média diária: {media_diaria} luvas/dia")
    pdf.multi_cell(0, 7, f"Extras utilizados: {extras_total} ({aproveitamento_extras}% do total)")
    pdf.multi_cell(0, 7, f"Saldo final mais recente: {saldo_atual} luvas")

    for titulo, buffer_imagem in figuras_pdf(df):
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(0, 10, titulo, ln=True)
        pdf.image(buffer_imagem, x=10, w=190, type="png")

    output = BytesIO()
    pdf.output(output)
    output.seek(0)
    return output


def aplicar_filtros(df: pd.DataFrame) -> pd.DataFrame:
    st.sidebar.header("Filtros")

    datas_validas = df["Data"].dropna()
    min_data = datas_validas.min().date() if not datas_validas.empty else date.today()
    max_data = datas_validas.max().date() if not datas_validas.empty else date.today()

    intervalo = st.sidebar.date_input(
        "Período",
        value=(min_data, max_data),
        min_value=min_data,
        max_value=max_data,
    )

    profissionais = st.sidebar.multiselect(
        "Profissional",
        options=sorted(df["Profissional"].dropna().unique()),
        default=sorted(df["Profissional"].dropna().unique()),
    )

    tipos = st.sidebar.multiselect(
        "Tamanho/Tipo de luva",
        options=sorted(df["Tamanhos/tipo luvas"].dropna().unique()),
        default=sorted(df["Tamanhos/tipo luvas"].dropna().unique()),
    )

    df_filtrado = df.copy()

    if intervalo:
        inicio, fim = intervalo if isinstance(intervalo, (list, tuple)) else (intervalo, intervalo)
        df_filtrado = df_filtrado[(df_filtrado["Data"] >= pd.to_datetime(inicio)) & (df_filtrado["Data"] <= pd.to_datetime(fim))]

    if profissionais:
        df_filtrado = df_filtrado[df_filtrado["Profissional"].isin(profissionais)]

    if tipos:
        df_filtrado = df_filtrado[df_filtrado["Tamanhos/tipo luvas"].isin(tipos)]

    st.sidebar.markdown("---")
    return df_filtrado


def layout_dashboard(df: pd.DataFrame, charts: dict, kpis: dict) -> None:
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total usado", f"{kpis['total_usado']:.0f}", help="Soma do total usado no período filtrado")
    col2.metric("Média diária", f"{kpis['media_diaria']:.1f}")
    col3.metric("Luvas extras", f"{kpis['extras_total']:.0f}", f"{kpis['aproveitamento_extras']:.1f}%")
    col4.metric("Saldo atual", f"{kpis['saldo_atual']:.0f}" if pd.notna(kpis['saldo_atual']) else "-", help="Saldo final mais recente")

    st.subheader("Tendências e comparativos")
    st.plotly_chart(charts["grafico_serie"], use_container_width=True)

    col_a, col_b = st.columns(2)
    with col_a:
        st.plotly_chart(charts["grafico_profissional"], use_container_width=True)
    with col_b:
        st.plotly_chart(charts["grafico_tipo"], use_container_width=True)

    st.plotly_chart(charts["grafico_saldo"], use_container_width=True)

    st.subheader("Tabela detalhada")
    st.dataframe(df)

    st.info(
        "Dica: acompanhe a relação entre saldo final e uso diário para ajustar compras e evitar rupturas. "
        "Profissionais e tamanhos com consumo acima da média merecem atenção para reposição antecipada."
    )


def main():
    st.set_page_config(page_title="Controle de Luvas", layout="wide")
    st.title("Controle de Luvas")
    st.caption("Monitoramento diário de consumo e estoque de luvas")

    df_bruto = carregar_dados()
    df_preparado = preparar_dados(df_bruto)
    df_filtrado = aplicar_filtros(df_preparado)

    kpis = indicadores(df_filtrado)
    charts = criar_graficos(df_filtrado)

    gerar_relatorio = st.sidebar.button("📄 Gerar relatório em PDF", use_container_width=True)

    layout_dashboard(df_filtrado, charts, kpis)

    if gerar_relatorio:
        if df_filtrado.empty:
            st.sidebar.warning("Não há dados para gerar o relatório com os filtros atuais.")
        else:
            pdf_buffer = gerar_pdf(df_filtrado, kpis)
            st.sidebar.download_button(
                label="Baixar relatório",
                data=pdf_buffer,
                file_name="relatorio_luvas.pdf",
                mime="application/pdf",
                use_container_width=True,
            )


if __name__ == "__main__":
    main()
