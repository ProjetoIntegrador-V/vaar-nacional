"""
calculadora/formulas.py
Implementação das fórmulas legais de cálculo do ICMS Educacional e VAAR.

Referências legais:
  - Lei 24.431/2023 — Anexo II e III (IE, IQE)
  - Lei 14.113/2020 — Art. 14 (VAAR)
"""
from __future__ import annotations
from dataclasses import dataclass
from utils.config import PESOS_IQE


# ─────────────────────────────────────────────────────────────────────────────
# ICMS EDUCACIONAL — Lei 24.431/2023
# ─────────────────────────────────────────────────────────────────────────────

def calcular_iqe(irap: float, ire: float, iae: float, ige: float) -> float:
    """
    Calcula o Índice de Qualidade Educacional (IQE) de um município.

    Fórmula (Anexo II — Lei 24.431/2023):
        IQEi = (IRAPi × 0,50) + (IREi × 0,20) + (IAEi × 0,15) + (IGEi × 0,15)

    Args:
        irap: Índice de Desempenho Escolar        (peso 50%)
        ire:  Índice de Rendimento Escolar        (peso 20%)
        iae:  Índice de Atendimento Educacional   (peso 15%)
        ige:  Índice de Gestão Escolar            (peso 15%)

    Returns:
        IQE no intervalo [0, 1]
    """
    return (
        irap * PESOS_IQE["IRAP"]
        + ire  * PESOS_IQE["IRE"]
        + iae  * PESOS_IQE["IAE"]
        + ige  * PESOS_IQE["IGE"]
    )


def calcular_ie(iqe_municipio: float, soma_iqe_todos: float) -> float:
    """
    Calcula o Índice de Educação do Município (IE).

    Fórmula (Anexo II — Lei 24.431/2023):
        IE(i) = IQE(i) / Σ IQE(i)

    Args:
        iqe_municipio:  IQE do município i
        soma_iqe_todos: Σ IQE de todos os municípios do estado

    Returns:
        IE no intervalo [0, 1] — representa a participação percentual
        do município no rateio do ICMS Educação
    """
    if soma_iqe_todos == 0:
        return 0.0
    return iqe_municipio / soma_iqe_todos


def calcular_repasse_icms(ie: float, total_icms_educacao: float) -> float:
    """
    Calcula o valor de repasse do ICMS Educação para o município.

    Args:
        ie:                    IE do município (participação proporcional)
        total_icms_educacao:   Total do ICMS destinado à educação no estado (R$)

    Returns:
        Valor em R$ a ser repassado ao município
    """
    return ie * total_icms_educacao


# ─────────────────────────────────────────────────────────────────────────────
# FUNDEB / VAAR — Lei 14.113/2020
# ─────────────────────────────────────────────────────────────────────────────

def calcular_coef_vaar(
    delta_indicador_municipio: float,
    soma_delta_indicadores_estado: float
) -> float:
    """
    Calcula o coeficiente de distribuição VAAR do município.

    Fórmula (Lei 14.113/2020 — Art. 14 + Res. CIF 15/2025):
        CoefVAAR = ΔIndicador_mun / Σ ΔIndicador_rede

    Args:
        delta_indicador_municipio:      Melhoria do índice educacional do município
        soma_delta_indicadores_estado:  Soma das melhorias de todos os municípios
                                        habilitados do estado

    Returns:
        Coeficiente proporcional de participação no VAAR
    """
    if soma_delta_indicadores_estado == 0:
        return 0.0
    return delta_indicador_municipio / soma_delta_indicadores_estado


def calcular_repasse_vaar(coef_vaar: float, total_vaar_estado: float) -> float:
    """
    Calcula o valor de repasse VAAR para o município.

    Fórmula:
        ValorVAAR = CoefVAAR × Total_VAAR_UF

    Args:
        coef_vaar:          Coeficiente VAAR do município
        total_vaar_estado:  Total VAAR alocado ao estado (R$)

    Returns:
        Valor em R$ a ser repassado ao município via VAAR
    """
    return coef_vaar * total_vaar_estado


# ─────────────────────────────────────────────────────────────────────────────
# Dataclass para resultado consolidado de um município
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ResultadoMunicipio:
    """Resultado completo de cálculo para um município."""
    cod_ibge:           str
    municipio:          str
    ano:                int
    irap:               float
    ire:                float
    iae:                float
    ige:                float
    iqe:                float
    ie:                 float
    repasse_icms:       float
    coef_vaar:          float
    repasse_vaar:       float

    @property
    def repasse_total(self) -> float:
        return self.repasse_icms + self.repasse_vaar

    def resumo(self) -> dict:
        return {
            "Município":            self.municipio,
            "Ano":                  self.ano,
            "IRAP (50%)":           round(self.irap, 4),
            "IRE (20%)":            round(self.ire, 4),
            "IAE (15%)":            round(self.iae, 4),
            "IGE (15%)":            round(self.ige, 4),
            "IQE":                  round(self.iqe, 4),
            "IE (participação)":    f"{self.ie * 100:.4f}%",
            "Repasse ICMS (R$)":    round(self.repasse_icms, 2),
            "Coef. VAAR":           round(self.coef_vaar, 6),
            "Repasse VAAR (R$)":    round(self.repasse_vaar, 2),
            "Total Recebido (R$)":  round(self.repasse_total, 2),
        }
