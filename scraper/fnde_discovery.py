"""
scraper/fnde_discovery.py
Módulo de descoberta automática de links do FNDE.

Acessa as páginas índice do FNDE por ano, identifica os arquivos
mais recentes de receitas e inabilitados, e retorna as URLs para download.

Suporta 2024, 2025 e anos futuros (2026+) sem alteração de código —
basta adicionar a URL da página índice do novo ano em config.py.
"""
from __future__ import annotations
import re
import requests
from bs4 import BeautifulSoup
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import (
    FNDE_PAGINAS_INDICE,
    FNDE_PDF_RECEITAS_FALLBACK,
    FNDE_PDF_INABILITADOS_FALLBACK,
    FNDE_KEYWORDS_RECEITAS,
    FNDE_KEYWORDS_INABILITADOS,
    FNDE_FORMATOS_PREFERIDOS,
    TIMEOUT_S,
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

BASE_FNDE = "https://www.gov.br"


def _normalizar_url(href: str) -> str:
    """Garante que a URL seja absoluta."""
    href = href.strip()
    if href.startswith("http"):
        return href
    if href.startswith("/"):
        return BASE_FNDE + href
    return BASE_FNDE + "/" + href


def _score_link(href: str, texto: str, keywords: list[str]) -> int:
    """
    Pontua um link pela relevância para as palavras-chave.
    Quanto maior o score, mais relevante o link.
    """
    alvo = (href + " " + texto).lower()
    score = 0
    for kw in keywords:
        if kw.lower() in alvo:
            score += 1
    # Bônus por formato preferido
    for i, fmt in enumerate(FNDE_FORMATOS_PREFERIDOS):
        if href.lower().endswith(fmt):
            score += (len(FNDE_FORMATOS_PREFERIDOS) - i) * 2
            break
    return score


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def _buscar_links_pagina(url: str, keywords: list[str]) -> list[tuple[int, str, str]]:
    """
    Acessa uma página do FNDE e retorna lista de (score, url, texto)
    ordenada por relevância decrescente.
    """
    logger.debug(f"Buscando links em: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S)
        resp.raise_for_status()
    except requests.RequestException as e:
        logger.warning(f"Não foi possível acessar {url}: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    resultados = []

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        texto = tag.get_text(strip=True)

        # Filtrar apenas links que parecem ser arquivos ou subpáginas relevantes
        ext = href.lower().split("?")[0].split("#")[0]
        eh_arquivo = any(ext.endswith(f) for f in [".pdf", ".csv", ".xlsx", ".xls"])
        eh_subpagina = "fundeb" in href.lower() or any(k in href.lower() for k in keywords)

        if not (eh_arquivo or eh_subpagina):
            continue

        score = _score_link(href, texto, keywords)
        if score > 0:
            resultados.append((score, _normalizar_url(href), texto))

    resultados.sort(key=lambda x: x[0], reverse=True)
    return resultados


def _buscar_recursivo(
    url_inicial: str,
    keywords: list[str],
    profundidade: int = 2
) -> str | None:
    """
    Busca recursivamente nas subpáginas do FNDE pelo arquivo mais relevante.
    Profundidade 1 = apenas a página inicial.
    Profundidade 2 = página inicial + subpáginas encontradas.
    """
    visitados = set()
    melhor = (0, None)  # (score, url)

    def _visitar(url: str, nivel: int):
        nonlocal melhor
        if url in visitados or nivel > profundidade:
            return
        visitados.add(url)

        links = _buscar_links_pagina(url, keywords)
        for score, href, texto in links:
            ext = href.lower().split("?")[0]
            eh_arquivo = any(ext.endswith(f) for f in [".pdf", ".csv", ".xlsx", ".xls"])

            if eh_arquivo and score > melhor[0]:
                melhor = (score, href)
                logger.debug(f"Novo melhor link (score={score}): {href}")
            elif not eh_arquivo and nivel < profundidade:
                # É uma subpágina — visitar recursivamente
                _visitar(href, nivel + 1)

    _visitar(url_inicial, 1)
    return melhor[1]


def descobrir_url_receitas(ano: int) -> str | None:
    """
    Descobre automaticamente a URL do arquivo de receitas FUNDEB
    para o ano informado.

    Estratégia:
      1. Acessa a página índice do FNDE para o ano
      2. Busca recursivamente pelos links de receitas
      3. Usa fallback hardcoded se disponível
      4. Retorna None se não encontrar

    Args:
        ano: Ano de referência (ex: 2025, 2026)

    Returns:
        URL do arquivo mais recente, ou None
    """
    logger.info(f"Descobrindo URL de receitas FNDE para {ano}...")

    # Tentar página índice
    pagina = FNDE_PAGINAS_INDICE.get(ano)
    if pagina:
        url = _buscar_recursivo(pagina, FNDE_KEYWORDS_RECEITAS, profundidade=2)
        if url:
            logger.success(f"URL receitas {ano} descoberta: {url}")
            return url

    # Fallback hardcoded
    url_fallback = FNDE_PDF_RECEITAS_FALLBACK.get(ano)
    if url_fallback:
        logger.warning(f"Usando URL fallback para receitas {ano}: {url_fallback}")
        return url_fallback

    logger.error(f"Não foi possível descobrir URL de receitas para {ano}.")
    return None


def descobrir_url_inabilitados(ano: int) -> str | None:
    """
    Descobre automaticamente a URL do arquivo de redes inabilitadas VAAR
    para o ano informado.

    Args:
        ano: Ano de referência

    Returns:
        URL do arquivo mais recente, ou None
    """
    logger.info(f"Descobrindo URL de inabilitados VAAR para {ano}...")

    pagina = FNDE_PAGINAS_INDICE.get(ano)
    if pagina:
        url = _buscar_recursivo(pagina, FNDE_KEYWORDS_INABILITADOS, profundidade=2)
        if url:
            logger.success(f"URL inabilitados {ano} descoberta: {url}")
            return url

    url_fallback = FNDE_PDF_INABILITADOS_FALLBACK.get(ano)
    if url_fallback:
        logger.warning(f"Usando URL fallback para inabilitados {ano}: {url_fallback}")
        return url_fallback

    logger.error(f"Não foi possível descobrir URL de inabilitados para {ano}.")
    return None


def descobrir_todas_urls(anos: list[int]) -> dict[int, dict[str, str | None]]:
    """
    Descobre todas as URLs necessárias para os anos informados.

    Returns:
        Dict no formato:
        {
            2025: {"receitas": "https://...", "inabilitados": "https://..."},
            2026: {"receitas": "https://...", "inabilitados": None},
        }
    """
    resultado = {}
    for ano in anos:
        resultado[ano] = {
            "receitas":     descobrir_url_receitas(ano),
            "inabilitados": descobrir_url_inabilitados(ano),
        }
        logger.info(
            f"Ano {ano} — receitas: {'✅' if resultado[ano]['receitas'] else '❌'} | "
            f"inabilitados: {'✅' if resultado[ano]['inabilitados'] else '❌'}"
        )
    return resultado


if __name__ == "__main__":
    from utils.config import ANOS_COLETA
    urls = descobrir_todas_urls(ANOS_COLETA)
    for ano, links in urls.items():
        print(f"\n{ano}:")
        for tipo, url in links.items():
            print(f"  {tipo}: {url}")
