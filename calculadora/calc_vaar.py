"""
calculadora/calc_vaar.py
Cálculo da complementação VAAR por município.
"""
from __future__ import annotations
import pandas as pd
from loguru import logger
from calculadora.formulas import calcular_coef_vaar, calcular_repasse_vaar


def calcular_vaar_municipios(
    df: pd.DataFrame,
    total_vaar_estado: float,
    col_delta: str = "delta_indicador"
) -> pd.DataFrame:
    """
    Calcula CoefVAAR e repasse VAAR para municípios habilitados.

    Args:
        df: DataFrame com col_delta (variação do indicador educacional)
            e coluna 'habilitado_vaar' (bool)
        total_vaar_estado: Total VAAR alocado ao estado (R$)
        col_delta: Nome da coluna com a variação do indicador

    Returns:
        DataFrame com colunas adicionais: coef_vaar, repasse_vaar
    """
    df = df.copy()

    # Apenas municípios habilitados participam do rateio VAAR
    mask_hab = df.get("habilitado_vaar", pd.Series([True] * len(df)))
    soma_delta = df.loc[mask_hab, col_delta].sum()

    logger.info(
        f"VAAR — {mask_hab.sum()} municípios habilitados | "
        f"Σ delta = {soma_delta:.6f} | Total estado = R$ {total_vaar_estado:,.2f}"
    )

    # Coef. VAAR: só habilitados recebem
    df["coef_vaar"] = df.apply(
        lambda r: calcular_coef_vaar(r[col_delta], soma_delta)
        if mask_hab.iloc[r.name] else 0.0,
        axis=1
    )

    # Repasse em R$
    df["repasse_vaar"] = df["coef_vaar"].apply(
        lambda c: calcular_repasse_vaar(c, total_vaar_estado)
    )

    return df


def verificar_condicionalidades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Marca municípios como habilitados/inabilitados no VAAR com base
    nas 5 condicionalidades da Lei 14.113/2020.

    Espera colunas booleanas:
        cond_1_gestor, cond_2_saeb, cond_3_desigualdade,
        cond_4_lei_estadual, cond_5_bncc
    """
    conds = [
        "cond_1_gestor",
        "cond_2_saeb",
        "cond_3_desigualdade",
        "cond_4_lei_estadual",
        "cond_5_bncc",
    ]
    conds_presentes = [c for c in conds if c in df.columns]

    if not conds_presentes:
        logger.warning("Nenhuma coluna de condicionalidade encontrada.")
        df["habilitado_vaar"] = True  # assume todos habilitados se sem dados
        return df

    # Todas as condicionalidades devem ser True (cumulativo)
    df["habilitado_vaar"] = df[conds_presentes].all(axis=1)

    inabilitados = (~df["habilitado_vaar"]).sum()
    logger.info(f"Condicionalidades: {inabilitados} municípios inabilitados")

    return df
