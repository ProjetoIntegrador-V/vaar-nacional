"""
utils/validators.py
Validações de entrada para a calculadora e formulários.
"""
from __future__ import annotations


def validar_indice(valor: float, nome: str) -> tuple[bool, str]:
    """Valida que um índice está no intervalo [0, 1]."""
    if valor is None:
        return False, f"{nome}: valor obrigatório."
    if not (0.0 <= valor <= 1.0):
        return False, f"{nome}: deve estar entre 0,0000 e 1,0000 (recebido: {valor})."
    return True, ""


def validar_iqe(irap, ire, iae, ige) -> tuple[bool, list[str]]:
    """Valida todos os componentes do IQE."""
    erros = []
    for valor, nome in [(irap, "IRAP"), (ire, "IRE"), (iae, "IAE"), (ige, "IGE")]:
        ok, msg = validar_indice(valor, nome)
        if not ok:
            erros.append(msg)
    return len(erros) == 0, erros


def validar_repasse(total_icms: float, total_vaar: float) -> tuple[bool, list[str]]:
    """Valida valores de repasse."""
    erros = []
    if total_icms is not None and total_icms <= 0:
        erros.append("Total ICMS Educação deve ser maior que zero.")
    if total_vaar is not None and total_vaar <= 0:
        erros.append("Total VAAR do estado deve ser maior que zero.")
    return len(erros) == 0, erros


def validar_cod_ibge(cod: str | int) -> bool:
    """Valida código IBGE de município mineiro (7 dígitos iniciando com 31)."""
    cod_str = str(cod).strip()
    return (
        cod_str.isdigit()
        and len(cod_str) == 7
        and cod_str.startswith("31")
    )
