"""
app.py
Ponto de entrada da aplicação Streamlit.
Configura a página principal e o menu de navegação.

Executar:
    streamlit run app.py
"""
from __future__ import annotations
import streamlit as st

st.set_page_config(
    page_title="FUNDEB-VAAR & ICMS Educacional — MG",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={
        "Get Help": "https://www.fjp.mg.gov.br",
        "Report a bug": None,
        "About": (
            "**FUNDEB-VAAR & ICMS Educacional — Minas Gerais**\n\n"
            "Calculadora e mapa de indicadores educacionais municipais.\n\n"
            "Fontes: FJP | FNDE | INEP | IBGE\n\n"
            "Legislação: Lei 18.030/2009 | Lei 24.431/2023 | Lei 14.113/2020"
        ),
    }
)

# ── Sidebar ─────────────────────────────────────────────────────────────────
with st.sidebar:
    st.image("assets/logo.png", use_column_width=True) if __import__("os").path.exists("assets/logo.png") else None
    st.markdown("## 🎓 Indicadores Educacionais")
    st.markdown("**Estado de Minas Gerais**")
    st.divider()
    st.markdown(
        """
        **Navegação**
        - 🏠 Início — visão geral
        - 🧮 Calculadora — calcule IE e VAAR
        - 🗺️ Mapa — visualização por município
        - 🔍 Consulta — painel por município
        - 🏆 Ranking — comparação entre municípios
        """
    )
    st.divider()
    st.caption("Fontes: FJP · FNDE · INEP · IBGE")
    st.caption("Lei 24.431/2023 · Lei 14.113/2020")

# ── Página inicial ───────────────────────────────────────────────────────────
st.title("🎓 FUNDEB-VAAR & ICMS Educacional")
st.subheader("Indicadores Educacionais dos Municípios de Minas Gerais")
st.divider()

col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(label="Municípios de MG", value="853")
with col2:
    st.metric(label="ICMS Educação", value="10% do total")
with col3:
    st.metric(label="VAAR 2024", value="R$ 3,85 bi")
with col4:
    st.metric(label="Indicadores", value="IE, IQE, IRAP…")

st.divider()
st.info(
    "👈 Use o menu lateral para navegar entre as funcionalidades. "
    "Comece pela **Calculadora** para simular os repasses de um município, "
    "ou pelo **Mapa** para visualizar os indicadores em todo o estado."
)

with st.expander("ℹ️ Sobre este projeto"):
    st.markdown("""
    Esta aplicação calcula e visualiza os indicadores educacionais municipais
    utilizados nos repasses do **ICMS Educacional** (Lei 24.431/2023) e da
    **Complementação VAAR do FUNDEB** (Lei 14.113/2020).

    **Fórmulas implementadas:**
    - `IQE = IRAP×0,50 + IRE×0,20 + IAE×0,15 + IGE×0,15`
    - `IE(i) = IQE(i) / Σ IQE(i)`
    - `CoefVAAR = ΔIndicador_mun / Σ ΔIndicador_rede`
    - `ValorVAAR = CoefVAAR × Total_VAAR_UF`

    **Fontes de dados:** FJP · FNDE · INEP · IBGE
    """)
