"""
scraper/downloader_fnde.py
Baixa as planilhas de repasse VAAR do portal FNDE.

O FNDE disponibiliza arquivos XLS/XLSX com os coeficientes e valores
de repasse do FUNDEB (VAAF, VAAT, VAAR) por município e por mês.

Uso:
    python -m scraper.downloader_fnde
"""
from __future__ import annotations
import re
import io
import requests
import pandas as pd
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential
from bs4 import BeautifulSoup

from utils.config import URLS, ANOS_COLETA, TIMEOUT_S, DATA_RAW
from utils.cache import salvar_parquet, cache_valido, DATA_PROCESSED

# Cabeçalhos HTTP para simular navegador real
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "pt-BR,pt;q=0.9",
}

# URLs base dos extratos FNDE por ano
# Padrão real do FNDE para download de planilhas VAAR
URL_BASE_EXTRATOS = "https://www.fnde.gov.br/financiamento/fundeb/area-para-gestores/dados-estatisticos"


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def baixar_planilha_vaar(ano: int, session: requests.Session) -> pd.DataFrame | None:
    """
    Baixa e processa a planilha de repasse VAAR do FNDE para um ano.

    O FNDE publica planilhas XLS/XLSX com colunas como:
      - Código IBGE, Município, UF
      - Coeficiente VAAR, Valor Repassado, Mês/Ano

    Args:
        ano:     Ano de referência
        session: Sessão HTTP reutilizável

    Returns:
        DataFrame com repasses VAAR por município ou None se não encontrado
    """
    logger.info(f"Buscando planilha VAAR {ano} no FNDE...")

    # Primeiro: buscar links de download na página de dados estatísticos
    try:
        resp = session.get(URL_BASE_EXTRATOS, headers=HEADERS, timeout=TIMEOUT_S)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "lxml")

        # Encontrar link da planilha do ano correspondente
        url_planilha = _encontrar_link_vaar(soup, ano)

        if not url_planilha:
            logger.warning(f"Link VAAR {ano} não encontrado na página — tentando URL direta.")
            url_planilha = _url_direta_fnde(ano)

        if not url_planilha:
            return None

        return _baixar_e_processar(url_planilha, ano, session)

    except requests.RequestException as e:
        logger.error(f"Erro HTTP ao acessar FNDE: {e}")
        raise


def _encontrar_link_vaar(soup: BeautifulSoup, ano: int) -> str | None:
    """
    Procura link de download da planilha VAAR na página do FNDE.
    Os links normalmente contêm 'VAAR' e o ano no texto ou href.
    """
    for link in soup.find_all("a", href=True):
        href = link["href"].lower()
        texto = link.get_text(strip=True).lower()
        if str(ano) in (href + texto) and "vaar" in (href + texto):
            url = link["href"]
            if not url.startswith("http"):
                url = "https://www.fnde.gov.br" + url
            logger.debug(f"Link VAAR {ano} encontrado: {url}")
            return url
    return None


def _url_direta_fnde(ano: int) -> str | None:
    """
    Constrói URL direta para planilhas FNDE com padrão conhecido.
    O FNDE segue padrão: .../complementacao-vaar-{ano}.xlsx
    """
    padroes = [
        f"https://www.fnde.gov.br/index.php/financiamento/fundeb/item/download/complementacao-vaar-{ano}",
        f"https://www.fnde.gov.br/financiamento/fundeb/complementacao-vaar-{ano}.xlsx",
        f"https://www.fnde.gov.br/financiamento/fundeb/area-para-gestores/dados-estatisticos/item/download/vaar-{ano}",
    ]
    return padroes[0]  # retorna o primeiro padrão para tentativa


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=3, max=15))
def _baixar_e_processar(url: str, ano: int, session: requests.Session) -> pd.DataFrame | None:
    """Baixa o arquivo XLS/XLSX e retorna DataFrame padronizado."""
    logger.info(f"Baixando: {url}")

    resp = session.get(url, headers=HEADERS, timeout=60, stream=True)
    resp.raise_for_status()

    conteudo = resp.content
    extensao = url.split(".")[-1].lower()

    # Salvar arquivo bruto
    arquivo_bruto = DATA_RAW / f"fnde_vaar_{ano}.{extensao}"
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    arquivo_bruto.write_bytes(conteudo)
    logger.debug(f"Arquivo salvo: {arquivo_bruto}")

    # Ler planilha
    try:
        engine = "openpyxl" if extensao == "xlsx" else "xlrd"
        df = pd.read_excel(io.BytesIO(conteudo), engine=engine, header=0)
    except Exception as e:
        logger.error(f"Erro ao ler planilha {url}: {e}")
        return None

    return _padronizar_fnde(df, ano)


def _padronizar_fnde(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """
    Padroniza colunas da planilha FNDE para o esquema do projeto.

    O FNDE pode usar variações de nomes de colunas entre anos.
    """
    df.columns = [str(c).strip().upper() for c in df.columns]

    # Mapa de colunas FNDE → padrão do projeto
    mapa = {
        # Código IBGE
        "CO_MUNICIPIO": "cod_ibge", "CD_MUNICIPIO": "cod_ibge",
        "CODIGO": "cod_ibge", "CÓD": "cod_ibge", "COD": "cod_ibge",
        # Município
        "NO_MUNICIPIO": "municipio", "NM_MUNICIPIO": "municipio",
        "MUNICIPIO": "municipio", "MUNICÍPIO": "municipio",
        # UF
        "SG_UF": "uf", "UF": "uf", "ESTADO": "uf",
        # Coeficiente VAAR
        "COEFICIENTE": "coef_vaar", "COEF_VAAR": "coef_vaar",
        "COEFICIENTE_VAAR": "coef_vaar",
        # Valor repassado
        "VL_REPASSE": "repasse_vaar", "VALOR_REPASSE": "repasse_vaar",
        "REPASSE": "repasse_vaar", "VALOR": "repasse_vaar",
        # Competência
        "COMPETENCIA": "competencia", "MES_ANO": "competencia",
    }

    # Renomear colunas encontradas
    renomear = {col: mapa[col] for col in df.columns if col in mapa}
    df = df.rename(columns=renomear)

    # Filtrar apenas municípios de MG
    if "uf" in df.columns:
        df = df[df["uf"].str.upper().str.strip() == "MG"]

    # Agregar por município (soma anual dos repasses mensais)
    colunas_num = [c for c in ["coef_vaar", "repasse_vaar"] if c in df.columns]
    if colunas_num and "cod_ibge" in df.columns:
        df = (
            df.groupby(["cod_ibge", "municipio"], as_index=False)[colunas_num]
            .sum()
        )

    df["ano"] = ano

    # Garantir cod_ibge como string
    if "cod_ibge" in df.columns:
        df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip().str.zfill(7)

    logger.info(f"FNDE {ano}: {len(df)} municípios de MG processados.")
    return df


# ── Execução principal ───────────────────────────────────────────────────────

def coletar_todos_anos(anos: list[int] = ANOS_COLETA) -> pd.DataFrame:
    """Coleta repasses VAAR do FNDE para todos os anos."""
    caminho_cache = DATA_PROCESSED / "fnde_vaar.parquet"
    if cache_valido(caminho_cache):
        logger.info("Cache FNDE válido — carregando do disco.")
        return pd.read_parquet(caminho_cache)

    dfs = []
    session = requests.Session()

    for ano in anos:
        logger.info(f"── Coletando FNDE VAAR {ano} ──")
        try:
            df = baixar_planilha_vaar(ano, session)
            if df is not None and not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.error(f"Falha FNDE {ano}: {e}")
            continue

    session.close()

    if not dfs:
        logger.warning("Nenhum dado FNDE coletado.")
        return pd.DataFrame()

    df_total = pd.concat(dfs, ignore_index=True)
    salvar_parquet(df_total, "fnde_vaar")
    logger.success(f"FNDE: {len(df_total)} registros coletados.")
    return df_total


if __name__ == "__main__":
    df = coletar_todos_anos()
    print(df.head(10))
    print(f"\nTotal: {len(df)} registros")
