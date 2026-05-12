"""
scraper/geo_loader.py
Carrega o shapefile (GeoJSON) dos 853 municípios de Minas Gerais
via API oficial do IBGE e enriquece com dados populacionais.

Uso:
    python -m scraper.geo_loader
"""
from __future__ import annotations
import json
import requests
import pandas as pd
import geopandas as gpd
from shapely.geometry import shape
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import URLS, COD_ESTADO_MG, TIMEOUT_S, DATA_GEO, DATA_PROCESSED
from utils.cache import salvar_geojson, cache_valido

HEADERS = {"Accept": "application/json", "User-Agent": "fundeb-icms-mg/1.0"}

# URLs da API IBGE
#URL_MALHA    = f"https://servicodados.ibge.gov.br/api/v3/malhas/estados/{COD_ESTADO_MG}/municipios"
#URL_MALHA     = "https://servicodados.ibge.gov.br/api/v3/malhas/estados/31?resolucao=5&formato=application/vnd.geo+json"
URL_MALHA     = "https://servicodados.ibge.gov.br/api/v3/malhas/paises/BR?resolucao=5&divisao=municipio&formato=application/vnd.geo+json"
URL_MUNS      = f"https://servicodados.ibge.gov.br/api/v1/localidades/estados/{COD_ESTADO_MG}/municipios"
URL_POPULACAO = "https://servicodados.ibge.gov.br/api/v3/agregados/6579/periodos/2022/variaveis/9324?localidades=N6[3100102,3100201]"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def baixar_lista_municipios() -> pd.DataFrame:
    """
    Baixa a lista completa dos 853 municípios de MG com código IBGE e nome.

    Returns:
        DataFrame com [cod_ibge, municipio]
    """
    logger.info("Baixando lista de municípios de MG (IBGE)...")
    resp = requests.get(URL_MUNS, headers=HEADERS, timeout=TIMEOUT_S)
    resp.raise_for_status()

    dados = resp.json()
    municipios = [
        {
            "cod_ibge": str(m["id"]),
            "municipio": m["nome"],
            "mesorregiao": m.get("microrregiao", {}).get("mesorregiao", {}).get("nome", ""),
            "microrregiao": m.get("microrregiao", {}).get("nome", ""),
        }
        for m in dados
    ]

    df = pd.DataFrame(municipios)
    logger.success(f"Lista de municípios: {len(df)} municípios de MG.")
    return df


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def baixar_geojson_mg() -> dict:
    """
    Baixa o GeoJSON dos municípios de MG.
    Usa o repositório de malhas do IBGE no GitHub como fonte confiável.
    """
    logger.info("Baixando malha territorial de MG (IBGE via GitHub)...")

    # Fonte: repositório oficial de malhas do IBGE
    # Contém todos os 853 municípios de MG com polígonos individuais
    url = (
        "https://raw.githubusercontent.com/tbrugz/geodata-br/"
        "master/geojson/geojs-31-mun.json"
    )

    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()

    geojson = resp.json()
    n_features = len(geojson.get("features", []))
    logger.success(f"GeoJSON baixado: {n_features} polígonos municipais.")
    return geojson



def enriquecer_geojson(geojson: dict, df_muns: pd.DataFrame) -> dict:
    """
    Padroniza as propriedades do GeoJSON para o esquema do projeto.
    O GeoJSON do tbrugz/geodata-br já vem com id e name por município.
    """
    idx = df_muns.set_index("cod_ibge").to_dict("index")

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})

        # Este GeoJSON usa 'id' como código IBGE de 7 dígitos
        cod = str(props.get("id", props.get("codarea", ""))).strip()

        props["cod_ibge"] = cod
        if not props.get("municipio"):
            props["municipio"] = props.get("name", "")

        # Enriquecer com dados adicionais da lista IBGE
        if cod in idx:
            props.update(idx[cod])

        feature["properties"] = props

    return geojson


def geojson_para_geodataframe(geojson: dict) -> gpd.GeoDataFrame:
    """
    Converte GeoJSON para GeoDataFrame GeoPandas com CRS SIRGAS 2000.

    Returns:
        GeoDataFrame pronto para uso no Folium/Plotly
    """
    gdf = gpd.GeoDataFrame.from_features(
        geojson["features"],
        crs="EPSG:4674"   # SIRGAS 2000 — sistema oficial do Brasil
    )
    gdf = gdf.rename(columns={"geometry": "geometry"})
    logger.info(f"GeoDataFrame: {len(gdf)} municípios | CRS: {gdf.crs}")
    return gdf


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def baixar_populacao_mg() -> pd.DataFrame:
    """
    Baixa a população estimada dos municípios de MG via API IBGE (Censo 2022).

    Returns:
        DataFrame com [cod_ibge, populacao]
    """
    logger.info("Baixando dados populacionais de MG (IBGE Censo 2022)...")

    # API IBGE Agregados — tabela 6579, variável 9324 (pop. residente)
    # Localidade N6 = municípios, [cod_estado=31] = MG
    url = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
        f"/periodos/2022/variaveis/9324"
        f"?localidades=N6[in~{COD_ESTADO_MG}]"
    )

    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    dados = resp.json()

    registros = []
    for variavel in dados:
        for resultado in variavel.get("resultados", []):
            for localidade in resultado.get("classificacoes", []):
                pass
            series = resultado.get("series", [])
            for serie in series:
                cod = str(serie["localidade"]["id"])
                valor = serie["serie"].get("2022", None)
                if cod and valor:
                    registros.append({
                        "cod_ibge": cod,
                        "populacao": int(valor) if valor != "-" else None
                    })

    df = pd.DataFrame(registros)
    logger.success(f"Populações: {len(df)} municípios carregados.")
    return df


# ── Execução principal ───────────────────────────────────────────────────────

def carregar_geodados() -> tuple[dict, gpd.GeoDataFrame]:
    """
    Função principal: baixa e consolida todos os dados geoespaciais.

    Returns:
        Tupla (geojson_dict, GeoDataFrame)
    """
    caminho_geojson = DATA_GEO / "municipios_mg.geojson"
    caminho_gdf     = DATA_PROCESSED / "geodados_mg.parquet"

    # Verificar cache
    if cache_valido(caminho_geojson, ttl_horas=168):  # 7 dias
        logger.info("Cache GeoJSON válido — carregando do disco.")
        with open(caminho_geojson, encoding="utf-8") as f:
            geojson = json.load(f)
        gdf = gpd.read_file(caminho_geojson)
        return geojson, gdf

    DATA_GEO.mkdir(parents=True, exist_ok=True)

    # 1. Lista de municípios
    df_muns = baixar_lista_municipios()

    # 2. GeoJSON da malha territorial
    geojson = baixar_geojson_mg()

    # 3. Enriquecer GeoJSON com nomes e regiões
    geojson = enriquecer_geojson(geojson, df_muns)

    # 4. Dados populacionais (melhor esforço — não bloqueia se falhar)
    try:
        df_pop = baixar_populacao_mg()
        # Integrar população no GeoJSON
        pop_idx = df_pop.set_index("cod_ibge")["populacao"].to_dict()
        for f in geojson["features"]:
            cod = f["properties"].get("cod_ibge", "")
            f["properties"]["populacao"] = pop_idx.get(cod, None)
    except Exception as e:
        logger.warning(f"Dados populacionais não carregados: {e}")

    # 5. Salvar GeoJSON
    salvar_geojson(geojson, "municipios_mg")

    # 6. Converter para GeoDataFrame
    gdf = geodataframe_para_arquivo(geojson)

    logger.success(f"Geodados de MG prontos: {len(geojson['features'])} municípios.")
    return geojson, gdf


def geodataframe_para_arquivo(geojson: dict) -> gpd.GeoDataFrame:
    """Cria e salva o GeoDataFrame final."""
    gdf = geojson_para_geodataframe(geojson)
    # Salvar como GeoJSON (Streamlit Folium lê direto)
    gdf.to_file(DATA_GEO / "municipios_mg.geojson", driver="GeoJSON")
    logger.info(f"GeoDataFrame salvo: {DATA_GEO / 'municipios_mg.geojson'}")
    return gdf


if __name__ == "__main__":
    geojson, gdf = carregar_geodados()
    #print(gdf[["cod_ibge", "municipio", "populacao"]].head(10))
    #print(f"\nTotal: {len(gdf)} municípios | CRS: {gdf.crs}")
    print(gdf.columns.tolist())
    print(gdf.head(3))
    print(f"\nTotal: {len(gdf)} municípios | CRS: {gdf.crs}")