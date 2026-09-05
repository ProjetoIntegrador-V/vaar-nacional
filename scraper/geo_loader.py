"""
scraper/geo_loader.py
Carrega a malha municipal (GeoJSON) de uma UF via geodata-br / IBGE
e enriquece com nomes, meso/microrregião e população.

Uso:
    python -m scraper.geo_loader           # MG (padrão)
    python -m scraper.geo_loader SP
    python -m scraper.geo_loader SP --forcar
"""
from __future__ import annotations
import json
import sys
import requests
import pandas as pd
import geopandas as gpd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import (
    URLS, TIMEOUT_S, DATA_GEO, UF_PADRAO, ESTADOS,
    meta_estado, nome_geojson_uf,
)
from utils.cache import salvar_geojson

HEADERS = {"Accept": "application/json", "User-Agent": "fundeb-icms-mg/1.0"}


def _url_municipios(cod: str) -> str:
    return URLS["ibge_municipios"].format(cod=cod)


def _url_malha(cod: str) -> str:
    return URLS["geodata_br_mun"].format(cod=cod)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def baixar_lista_municipios(uf: str = UF_PADRAO) -> pd.DataFrame:
    """
    Baixa a lista de municípios da UF com código IBGE e nome.

    Returns:
        DataFrame com [cod_ibge, municipio, mesorregiao, microrregiao]
    """
    meta = meta_estado(uf)
    logger.info(f"Baixando lista de municípios de {uf.upper()} (IBGE)...")
    resp = requests.get(_url_municipios(meta["cod"]), headers=HEADERS, timeout=TIMEOUT_S)
    resp.raise_for_status()

    dados = resp.json()
    municipios = [
        {
            "cod_ibge": str(m["id"]),
            "municipio": m["nome"],
            "uf": uf.strip().upper(),
            "mesorregiao": m.get("microrregiao", {}).get("mesorregiao", {}).get("nome", ""),
            "microrregiao": m.get("microrregiao", {}).get("nome", ""),
        }
        for m in dados
    ]

    df = pd.DataFrame(municipios)
    logger.success(f"Lista de municípios: {len(df)} municípios de {uf.upper()}.")
    return df


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def baixar_geojson(uf: str = UF_PADRAO) -> dict:
    """
    Baixa o GeoJSON dos municípios da UF (tbrugz/geodata-br).
    """
    meta = meta_estado(uf)
    logger.info(f"Baixando malha territorial de {uf.upper()} (geodata-br)...")
    url = _url_malha(meta["cod"])

    resp = requests.get(url, headers=HEADERS, timeout=120)
    resp.raise_for_status()

    geojson = resp.json()
    n_features = len(geojson.get("features", []))
    logger.success(f"GeoJSON baixado: {n_features} polígonos municipais.")
    return geojson


def baixar_geojson_mg() -> dict:
    """Compatibilidade: malha de MG."""
    return baixar_geojson("MG")


def enriquecer_geojson(geojson: dict, df_muns: pd.DataFrame) -> dict:
    """
    Padroniza as propriedades do GeoJSON para o esquema do projeto.
    O GeoJSON do tbrugz/geodata-br já vem com id e name por município.
    """
    idx = df_muns.set_index("cod_ibge").to_dict("index")

    for feature in geojson.get("features", []):
        props = feature.get("properties", {})

        cod = str(props.get("id", props.get("codarea", ""))).strip()

        props["cod_ibge"] = cod
        if not props.get("municipio"):
            props["municipio"] = props.get("name", "")

        if cod in idx:
            props.update(idx[cod])

        feature["properties"] = props

    return geojson


def geojson_para_geodataframe(geojson: dict) -> gpd.GeoDataFrame:
    """
    Converte GeoJSON para GeoDataFrame GeoPandas com CRS SIRGAS 2000.
    """
    gdf = gpd.GeoDataFrame.from_features(
        geojson["features"],
        crs="EPSG:4674",
    )
    logger.info(f"GeoDataFrame: {len(gdf)} municípios | CRS: {gdf.crs}")
    return gdf


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def baixar_populacao(uf: str = UF_PADRAO) -> pd.DataFrame:
    """
    Baixa a população estimada dos municípios da UF (IBGE Censo 2022).
    """
    meta = meta_estado(uf)
    logger.info(f"Baixando dados populacionais de {uf.upper()} (IBGE Censo 2022)...")

    url = (
        "https://servicodados.ibge.gov.br/api/v3/agregados/6579"
        "/periodos/2022/variaveis/9324"
        f"?localidades=N6[in~{meta['cod']}]"
    )

    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    dados = resp.json()

    registros = []
    for variavel in dados:
        for resultado in variavel.get("resultados", []):
            for serie in resultado.get("series", []):
                cod = str(serie["localidade"]["id"])
                valor = serie["serie"].get("2022", None)
                if cod and valor:
                    registros.append({
                        "cod_ibge": cod,
                        "populacao": int(valor) if valor != "-" else None,
                    })

    df = pd.DataFrame(registros)
    logger.success(f"Populações: {len(df)} municípios carregados.")
    return df


def baixar_populacao_mg() -> pd.DataFrame:
    """Compatibilidade: população de MG."""
    return baixar_populacao("MG")


def caminho_geojson_uf(uf: str = UF_PADRAO):
    return DATA_GEO / f"{nome_geojson_uf(uf)}.geojson"


def carregar_geodados(
    uf: str = UF_PADRAO,
    forcar: bool = False,
) -> tuple[dict, gpd.GeoDataFrame]:
    """
    Baixa (se necessário) e consolida a malha municipal da UF.

    Returns:
        Tupla (geojson_dict, GeoDataFrame)
    """
    uf = uf.strip().upper()
    if uf not in ESTADOS:
        raise ValueError(f"UF inválida: {uf}")

    nome = nome_geojson_uf(uf)
    caminho_geojson = caminho_geojson_uf(uf)

    if caminho_geojson.exists() and not forcar:
        logger.info(f"GeoJSON em disco — {caminho_geojson.name}")
        with open(caminho_geojson, encoding="utf-8") as f:
            geojson = json.load(f)
        gdf = gpd.read_file(caminho_geojson)
        return geojson, gdf

    DATA_GEO.mkdir(parents=True, exist_ok=True)

    df_muns = baixar_lista_municipios(uf)
    geojson = baixar_geojson(uf)
    geojson = enriquecer_geojson(geojson, df_muns)

    try:
        df_pop = baixar_populacao(uf)
        pop_idx = df_pop.set_index("cod_ibge")["populacao"].to_dict()
        for feat in geojson["features"]:
            cod = feat["properties"].get("cod_ibge", "")
            feat["properties"]["populacao"] = pop_idx.get(cod, None)
    except Exception as e:
        logger.warning(f"Dados populacionais não carregados: {e}")

    salvar_geojson(geojson, nome)
    gdf = geodataframe_para_arquivo(geojson, uf)

    logger.success(
        f"Geodados de {uf} prontos: {len(geojson['features'])} municípios."
    )
    return geojson, gdf


def geodataframe_para_arquivo(
    geojson: dict,
    uf: str = UF_PADRAO,
) -> gpd.GeoDataFrame:
    """Cria e salva o GeoDataFrame final."""
    gdf = geojson_para_geodataframe(geojson)
    destino = caminho_geojson_uf(uf)
    gdf.to_file(destino, driver="GeoJSON")
    logger.info(f"GeoDataFrame salvo: {destino}")
    return gdf


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--forcar"]
    forcar = "--forcar" in sys.argv[1:]
    uf_cli = args[0].upper() if args else UF_PADRAO
    geojson, gdf = carregar_geodados(uf_cli, forcar=forcar)
    print(gdf.columns.tolist())
    print(gdf.head(3))
    print(f"\nTotal: {len(gdf)} municípios | UF: {uf_cli} | CRS: {gdf.crs}")
