from __future__ import annotations
import json
import streamlit as st
import pandas as pd
import plotly.express as px
from scraper.scheduler import carregar_consolidado
from scraper.geo_loader import carregar_geodados, caminho_geojson_uf
from utils.config import ESTADOS, UF_PADRAO, meta_estado
from utils.formatters import fmt_numero, fmt_moeda

st.set_page_config(
    page_title="Mapa — FUNDEB/VAAR",
    page_icon="🗺️", layout="wide"
)
st.title("🗺️ Mapa de Indicadores")
st.caption("Choropleth municipal por UF — malha IBGE/geodata-br")

UFS_ORDENADAS = [UF_PADRAO] + sorted(uf for uf in ESTADOS if uf != UF_PADRAO)
ROTULOS_UF = {uf: f"{uf} — {ESTADOS[uf]['nome']}" for uf in UFS_ORDENADAS}

INDICADORES_MG = {
    "IE — Índice de Educação":        "IE",
    "IRAP — Desempenho Escolar":      "IRAP",
    "IRE — Rendimento Escolar":       "IRE",
    "IAE — Atendimento Educacional":  "IAE",
    "IGE — Gestão Escolar":           "IGE",
    "Repasse ICMS Educação (R$)":     "repasse_icms_educacao",
    "Repasse VAAR (R$)":              "repasse_vaar",
}
INDICADORES_OUTROS = {
    "Repasse VAAR (R$)": "repasse_vaar",
}


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_tabela():
    return carregar_consolidado()


@st.cache_data(ttl=3600, show_spinner=False)
def carregar_geojson(uf: str) -> dict:
    caminho = caminho_geojson_uf(uf)
    if caminho.exists():
        with open(caminho, encoding="utf-8") as f:
            return json.load(f)
    geojson, _ = carregar_geodados(uf)
    return geojson


def dataframe_da_malha(geojson: dict) -> pd.DataFrame:
    linhas = []
    for feat in geojson.get("features", []):
        props = feat.get("properties", {})
        cod = str(props.get("id", props.get("cod_ibge", ""))).strip()
        linhas.append({
            "cod_ibge": cod,
            "municipio": props.get("municipio") or props.get("name") or "",
        })
    return pd.DataFrame(linhas)


with st.spinner("Carregando dados..."):
    df = carregar_tabela()

if df.empty:
    st.error("Dados consolidados não disponíveis.")
    st.stop()

# ── Controles ─────────────────────────────────────────────────────────────────
col0, col1, col2, col3 = st.columns(4)

with col0:
    uf_sel = st.selectbox(
        "Estado",
        UFS_ORDENADAS,
        index=0,
        format_func=lambda u: ROTULOS_UF[u],
    )

meta = meta_estado(uf_sel)

with col1:
    anos = sorted(df["ano"].unique(), reverse=True)
    ano_sel = st.selectbox("Ano", anos)

with col2:
    indicadores_disp = INDICADORES_MG if uf_sel == "MG" else INDICADORES_OUTROS
    indicador_nome = st.selectbox("Indicador", list(indicadores_disp.keys()))
    indicador_col = indicadores_disp[indicador_nome]

with col3:
    paletas = {
        "Amarelo → Vermelho": "YlOrRd",
        "Azul":               "Blues",
        "Verde":              "Greens",
        "Verde → Vermelho":   "RdYlGn",
        "Azul Púrpura":       "PuBu",
    }
    paleta_nome = st.selectbox("Paleta de cores", list(paletas.keys()))
    paleta = paletas[paleta_nome]

with st.spinner(f"Carregando malha de {ROTULOS_UF[uf_sel]}..."):
    try:
        geojson = carregar_geojson(uf_sel)
    except Exception as e:
        st.error(f"Não foi possível carregar a malha de {uf_sel}: {e}")
        st.stop()

n_poligonos = len(geojson.get("features", []))
if n_poligonos == 0:
    st.error(f"GeoJSON de {uf_sel} sem polígonos.")
    st.stop()

# ── Preparar dados (malha + indicadores) ──────────────────────────────────────
df_geo = dataframe_da_malha(geojson)

df_ano = df[df["ano"] == ano_sel].copy()
df_ano["cod_ibge"] = df_ano["cod_ibge"].astype(str).str.replace(r"\.0$", "", regex=True)
if indicador_col not in df_ano.columns:
    df_ano[indicador_col] = pd.NA

cols_merge = ["cod_ibge", indicador_col]
if "municipio" in df_ano.columns:
    cols_merge.append("municipio")
df_ind = df_ano[cols_merge].drop_duplicates("cod_ibge")

df_plot = df_geo.merge(df_ind, on="cod_ibge", how="left", suffixes=("", "_ind"))
if "municipio_ind" in df_plot.columns:
    df_plot["municipio"] = df_plot["municipio"].fillna(df_plot["municipio_ind"])
    df_plot = df_plot.drop(columns=["municipio_ind"])

n_com_valor = int(df_plot[indicador_col].notna().sum())

if uf_sel != "MG":
    st.info(
        f"Malha de **{meta['nome']}** ({n_poligonos} municípios). "
        "IE/ICMS são indicadores mineiros. VAAR nacional entra no mapa quando "
        "o consolidado deixar de filtrar só MG no FNDE. "
        f"Municípios com valor neste indicador: **{n_com_valor}**."
    )
elif n_com_valor == 0:
    st.warning("Nenhum município com valor para o indicador selecionado.")

df_plot["valor_fmt"] = df_plot[indicador_col].apply(
    lambda v: fmt_moeda(v) if "repasse" in indicador_col else fmt_numero(v, 4)
    if v == v else "—"
)

# ── Criar mapa Plotly (OpenStreetMap — sem token Mapbox) ──────────────────────
kwargs_mapa = dict(
    geojson=geojson,
    locations="cod_ibge",
    featureidkey="properties.id",
    color=indicador_col,
    color_continuous_scale=paleta,
    zoom=meta["zoom"],
    center={"lat": meta["lat"], "lon": meta["lon"]},
    opacity=0.75,
    hover_name="municipio",
    hover_data={
        "cod_ibge": False,
        indicador_col: False,
        "valor_fmt": True,
    },
    labels={"valor_fmt": indicador_nome},
    height=580,
)
# Plotly ≥ 5.24: choropleth_map (MapLibre). Antes: mapbox com OSM (também sem token).
if hasattr(px, "choropleth_map"):
    fig = px.choropleth_map(df_plot, map_style="open-street-map", **kwargs_mapa)
else:
    fig = px.choropleth_mapbox(
        df_plot, mapbox_style="open-street-map", **kwargs_mapa
    )

fig.update_layout(
    margin=dict(l=0, r=0, t=0, b=0),
    coloraxis_colorbar=dict(
        title=indicador_nome,
        thickness=15,
        len=0.6,
    ),
)

st.plotly_chart(fig, use_container_width=True)

# ── Estatísticas ──────────────────────────────────────────────────────────────
st.divider()
st.subheader(f"Estatísticas — {indicador_nome} ({ano_sel} · {uf_sel})")
col_a, col_b, col_c, col_d, col_e = st.columns(5)
serie = df_plot[indicador_col].dropna()
col_a.metric("Municípios na malha", f"{n_poligonos}")
col_b.metric("Com dado", f"{n_com_valor}")
col_c.metric("Média", fmt_numero(serie.mean()) if len(serie) else "—")
col_d.metric("Mínimo", fmt_numero(serie.min()) if len(serie) else "—")
col_e.metric("Máximo", fmt_numero(serie.max()) if len(serie) else "—")
