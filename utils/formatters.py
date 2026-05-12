"""
utils/formatters.py
Funções de formatação para exibição na interface Streamlit.
"""
from __future__ import annotations
import locale
locale.setlocale(locale.LC_ALL, "pt_BR.UTF-8") if "pt_BR" in locale.locale_alias else None


def fmt_moeda(valor: float) -> str:
    """R$ 1.234.567,89"""
    if valor is None or valor != valor:  # NaN check
        return "—"
    return f"R$ {valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_numero(valor: float, casas: int = 4) -> str:
    """0,1234"""
    if valor is None or valor != valor:
        return "—"
    return f"{valor:.{casas}f}".replace(".", ",")


def fmt_percentual(valor: float, casas: int = 2) -> str:
    """12,34%"""
    if valor is None or valor != valor:
        return "—"
    return f"{valor * 100:.{casas}f}%".replace(".", ",")


def fmt_municipio(nome: str) -> str:
    """Capitaliza corretamente o nome do município."""
    preposicoes = {"de", "do", "da", "dos", "das", "e", "em", "no", "na"}
    partes = nome.lower().split()
    return " ".join(
        p if p in preposicoes else p.capitalize()
        for p in partes
    )


def indicador_cor(valor: float, maximo: float = 1.0) -> str:
    """Retorna cor hex baseada no valor relativo (verde → amarelo → vermelho)."""
    if valor is None or valor != valor:
        return "#AAAAAA"
    ratio = max(0.0, min(1.0, valor / maximo))
    if ratio >= 0.7:
        return "#047857"   # verde
    elif ratio >= 0.4:
        return "#D97706"   # âmbar
    else:
        return "#DC2626"   # vermelho


def truncar(texto: str, max_chars: int = 40) -> str:
    """Trunca texto longo com reticências."""
    if len(texto) <= max_chars:
        return texto
    return texto[:max_chars - 3] + "..."
