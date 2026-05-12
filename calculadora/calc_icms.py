"""
calculadora/calc_icms.py
Cálculo do ICMS Educacional para todos os municípios de MG.
Recebe DataFrame com os índices brutos e devolve com IE e repasse calculados.
"""
from __future__ import annotations
import pandas as pd
from loguru import logger
from calculadora.formulas import calcular_iqe, calcular_ie, calcular_repasse_icms


def calcular_icms_municipios(
    df: pd.DataFrame,
    total_icms_educacao: float,
    ano: int
) -> pd.DataFrame:
    """
    Calcula IE e repasse ICMS Educação para todos os municípios.

    Args:
        df: DataFrame com colunas [cod_ibge, municipio, IRAP, IRE, IAE, IGE]
        total_icms_educacao: Total em R$ destinado à educação no estado
        ano: Ano de referência

    Returns:
        DataFrame com colunas adicionais: IQE, IE, repasse_icms_educacao
    """
    df = df.copy()
    df["ano"] = ano

    # Calcula IQE para cada município
    df["IQE"] = df.apply(
        lambda r: calcular_iqe(r["IRAP"], r["IRE"], r["IAE"], r["IGE"]),
        axis=1
    )

    # Soma total dos IQEs (denominador da fórmula)
    soma_iqe = df["IQE"].sum()
    logger.info(f"Ano {ano} — Soma IQE = {soma_iqe:.6f} | {len(df)} municípios")

    # Calcula IE proporcional de cada município
    df["IE"] = df["IQE"].apply(lambda iqe: calcular_ie(iqe, soma_iqe))

    # Calcula repasse em R$
    df["repasse_icms_educacao"] = df["IE"].apply(
        lambda ie: calcular_repasse_icms(ie, total_icms_educacao)
    )

    # Validação: soma dos IE deve ser ~1.0
    soma_ie = df["IE"].sum()
    if not (0.9999 <= soma_ie <= 1.0001):
        logger.warning(f"Soma dos IE = {soma_ie:.6f} (esperado ~1.0)")

    return df


def ranking_icms(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """Retorna os top N e bottom N municípios por IE."""
    ordenado = df.sort_values("IE", ascending=False).reset_index(drop=True)
    ordenado.index += 1
    return ordenado
