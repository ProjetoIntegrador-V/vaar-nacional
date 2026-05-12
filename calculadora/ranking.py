"""
calculadora/ranking.py
Geração de rankings e comparações entre municípios.
"""
from __future__ import annotations
import pandas as pd
from utils.config import NOMES_INDICADORES


def gerar_ranking(
    df: pd.DataFrame,
    coluna: str = "IE",
    top_n: int = 20,
    ascendente: bool = False
) -> pd.DataFrame:
    """
    Gera ranking de municípios por qualquer indicador.

    Args:
        df:         DataFrame consolidado
        coluna:     Indicador para ordenação (IE, IRAP, IRE, IAE, IGE, repasse_vaar…)
        top_n:      Número de municípios a retornar (None = todos)
        ascendente: False = maior primeiro (padrão), True = menor primeiro

    Returns:
        DataFrame ordenado com coluna de posição
    """
    df_rank = df.copy().sort_values(coluna, ascending=ascendente)
    df_rank = df_rank.reset_index(drop=True)
    df_rank.index += 1
    df_rank.index.name = "Posição"
    if top_n:
        df_rank = df_rank.head(top_n)
    return df_rank


def comparar_municipios(
    df: pd.DataFrame,
    municipios: list[str],
    colunas: list[str] | None = None
) -> pd.DataFrame:
    """
    Retorna tabela comparativa entre municípios selecionados.

    Args:
        df:         DataFrame consolidado
        municipios: Lista de nomes de municípios
        colunas:    Indicadores a comparar (None = todos)
    """
    if colunas is None:
        colunas = ["municipio", "ano", "IRAP", "IRE", "IAE", "IGE", "IQE", "IE",
                   "repasse_icms_educacao", "repasse_vaar"]

    mask = df["municipio"].str.upper().isin([m.upper() for m in municipios])
    return df.loc[mask, [c for c in colunas if c in df.columns]]


def evolucao_historica(
    df: pd.DataFrame,
    municipio: str,
    indicadores: list[str] | None = None
) -> pd.DataFrame:
    """
    Retorna a evolução anual dos indicadores de um município.
    """
    if indicadores is None:
        indicadores = ["IRAP", "IRE", "IAE", "IGE", "IQE", "IE"]

    mask = df["municipio"].str.upper() == municipio.upper()
    df_mun = df.loc[mask].sort_values("ano")

    colunas = ["ano"] + [c for c in indicadores if c in df_mun.columns]
    return df_mun[colunas].reset_index(drop=True)


def percentil_municipio(df: pd.DataFrame, municipio: str, coluna: str = "IE") -> float:
    """Retorna o percentil do município no indicador (0–100)."""
    mask = df["municipio"].str.upper() == municipio.upper()
    if not mask.any():
        return 0.0
    valor = df.loc[mask, coluna].values[0]
    return round((df[coluna] < valor).mean() * 100, 1)
