"""
scraper/fnde_coef_loader.py
Baixa e processa o arquivo de coeficientes VAAR do FNDE.

Arquivo: "Redes beneficiadas, coeficientes de distribuição e
          complementação-VAAR prevista"

Colunas: UF | Ente Federado | Código IBGE |
         Coeficiente VAAR | Complementação VAAR (R$)

Disponível em:
  2025: XLSX — portaria de novembro 2025
  2026: CSV/XLSX — publicações-2026

Uso:
    python -m scraper.fnde_coef_loader
"""
from __future__ import annotations
import io
import re
import requests
import pandas as pd
from pathlib import Path
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import (
    ANOS_COLETA, PREFIXO_IBGE_MG, TIMEOUT_S, DATA_RAW,
)
from utils.cache import salvar_parquet, cache_valido, DATA_PROCESSED

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    )
}

# URLs conhecidas do arquivo de coeficientes por ano
# O discovery automático também busca por palavras-chave
URLS_COEF_FALLBACK = {
    2025: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2025-1/4a-publicacao-2013-portaria-mec-mf-no-11-de-27-de-novembro-de-2025/redes-beneficiadas-coeficientes-de-distribuicao-e-complementacao-vaar-prevista.pdf",
    2026: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2026-1/publicacoes-2026/redes-beneficiadas-coeficientes-de-distribuicao-e-complementacao-vaar-prevista.csv",
}

# Palavras-chave para discovery automático
KEYWORDS_COEF = [
    "beneficiad", "coeficiente", "coeficientes-de-distribuicao",
    "redes-beneficiadas", "complementacao-vaar-prevista",
]


def _descobrir_url_coef(ano: int) -> str | None:
    """Busca URL do arquivo de coeficientes na página índice do FNDE."""
    from scraper.fnde_discovery import _buscar_links_pagina
    from utils.config import FNDE_PAGINAS_INDICE, FNDE_FORMATOS_PREFERIDOS

    pagina = FNDE_PAGINAS_INDICE.get(ano)
    if not pagina:
        return URLS_COEF_FALLBACK.get(ano)

    logger.info(f"Buscando URL de coeficientes VAAR para {ano}...")
    links = _buscar_links_pagina(pagina, KEYWORDS_COEF)

    melhor = (0, None)
    for score, url, texto in links:
        ext = url.lower().split("?")[0]
        eh_arquivo = any(ext.endswith(f) for f in [".pdf",".csv",".xlsx",".xls"])
        if eh_arquivo and score > melhor[0]:
            melhor = (score, url)

    if melhor[1]:
        logger.success(f"URL coeficientes {ano} encontrada: {melhor[1]}")
        return melhor[1]

    # Fallback
    url_fb = URLS_COEF_FALLBACK.get(ano)
    if url_fb:
        logger.warning(f"Usando fallback para coeficientes {ano}: {url_fb}")
    return url_fb


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def _baixar(url: str, nome: str) -> bytes | None:
    """Baixa arquivo e salva em data/raw/."""
    logger.info(f"Baixando coeficientes: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S, stream=True)
        resp.raise_for_status()
        conteudo = resp.content
        DATA_RAW.mkdir(parents=True, exist_ok=True)
        ext = Path(url.split("?")[0]).suffix or ".bin"
        caminho = DATA_RAW / f"{nome}{ext}"
        caminho.write_bytes(conteudo)
        logger.debug(f"Salvo: {caminho} ({len(conteudo)/1024:.1f} KB)")
        return conteudo
    except requests.RequestException as e:
        logger.error(f"Erro ao baixar: {e}")
        raise


def _converter_valor(texto: str) -> float | None:
    """Converte string BR para float."""
    if not texto or str(texto).strip() in ("-","—","","None","nan"):
        return None
    try:
        limpo = re.sub(r"[^\d,.]", "", str(texto))
        if "," in limpo and "." in limpo:
            limpo = limpo.replace(".", "").replace(",", ".")
        elif "," in limpo:
            limpo = limpo.replace(",", ".")
        return float(limpo) if limpo else None
    except (ValueError, AttributeError):
        return None


def _filtrar_mg(df: pd.DataFrame) -> pd.DataFrame:
    """Filtra apenas MG."""
    if df.empty:
        return df
    if "uf" in df.columns:
        df = df[df["uf"].astype(str).str.strip().str.upper() == "MG"].copy()
    elif "cod_ibge" in df.columns:
        df = df[df["cod_ibge"].astype(str).str.startswith(PREFIXO_IBGE_MG)].copy()
    if "cod_ibge" in df.columns:
        df["cod_ibge"] = (
            df["cod_ibge"].astype(str).str.strip()
            .str.replace(r"\D", "", regex=True).str.zfill(7)
        )
    logger.info(f"Após filtro MG: {len(df)} registros.")
    return df.reset_index(drop=True)


def _parsear_csv(conteudo: bytes, ano: int) -> pd.DataFrame:
    """
    Processa CSV de coeficientes VAAR 2026+
    Estrutura similar ao CSV de receitas — cabeçalho na linha 9.
    """
    # Tentar diferentes linhas de cabeçalho
    for header_row in [9, 8, 7, 0]:
        try:
            df = pd.read_csv(
                io.BytesIO(conteudo), sep=";",
                header=header_row, dtype=str,
                encoding="latin-1", skip_blank_lines=False
            )
            df.columns = [str(c).strip() for c in df.columns]
            cols_lower = [c.lower() for c in df.columns]

            tem_ibge  = any("ibge" in c for c in cols_lower)
            tem_coef  = any("coef" in c or "distribuic" in c for c in cols_lower)
            tem_ente  = any("ente" in c or "entidade" in c for c in cols_lower)

            if tem_ibge and (tem_coef or tem_ente):
                logger.debug(f"CSV coeficientes — header linha {header_row}: {list(df.columns)}")
                break
        except Exception:
            continue
    else:
        logger.warning("Cabeçalho CSV coeficientes não identificado automaticamente.")
        df = pd.read_csv(
            io.BytesIO(conteudo), sep=";", header=9,
            dtype=str, encoding="latin-1"
        )
        df.columns = [str(c).strip() for c in df.columns]

    return _mapear_e_processar(df, ano)


def _parsear_xlsx(conteudo: bytes, ano: int) -> pd.DataFrame:
    """Processa XLSX de coeficientes VAAR."""
    try:
        xl = pd.ExcelFile(io.BytesIO(conteudo))
        aba = xl.sheet_names[0]

        # Encontrar linha do cabeçalho
        for header_row in range(12):
            df = pd.read_excel(
                io.BytesIO(conteudo), sheet_name=aba,
                header=header_row, dtype=str
            )
            df.columns = [str(c).strip() for c in df.columns]
            cols_lower = [c.lower() for c in df.columns]

            tem_ibge = any("ibge" in c or "código" in c for c in cols_lower)
            tem_coef = any("coef" in c or "distribuic" in c for c in cols_lower)

            if tem_ibge and tem_coef:
                logger.debug(f"XLSX coeficientes — header linha {header_row}: {list(df.columns)}")
                return _mapear_e_processar(df, ano)

    except Exception as e:
        logger.error(f"Erro ao ler XLSX coeficientes: {e}")
    return pd.DataFrame()


def _parsear_pdf(conteudo: bytes, ano: int) -> pd.DataFrame:
    """Processa PDF de coeficientes VAAR via pdfplumber."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber não instalado")
        return pd.DataFrame()

    registros = []
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        for pagina in pdf.pages:
            tabela = pagina.extract_table()
            if not tabela:
                continue
            for linha in tabela:
                if not linha or len(linha) < 4:
                    continue
                cels = [str(c).strip() if c else "" for c in linha]

                # Ignorar cabeçalho
                if cels[0].upper() in ("UF", "SIGLA", ""):
                    continue

                uf = cels[0].strip().upper()
                municipio = cels[1].strip().title() if len(cels) > 1 else ""

                # Código IBGE
                cod_ibge = ""
                for c in cels[2:4]:
                    if re.match(r"^\d{6,7}$", c.replace(" ", "")):
                        cod_ibge = c.replace(" ", "").zfill(7)
                        break

                # Coeficiente e valor
                valores = [_converter_valor(v) for v in cels[3:]
                           if _converter_valor(v) is not None]

                if not uf or not municipio:
                    continue

                reg = {
                    "uf": uf,
                    "cod_ibge": cod_ibge,
                    "municipio": municipio,
                    "coef_vaar": valores[0] if len(valores) > 0 else None,
                    "compl_vaar_prevista": valores[1] if len(valores) > 1 else None,
                    "ano": ano,
                }
                registros.append(reg)

    df = pd.DataFrame(registros)
    return _filtrar_mg(df) if not df.empty else df


def _mapear_e_processar(df: pd.DataFrame, ano: int) -> pd.DataFrame:
    """Mapeia colunas e processa valores numéricos."""
    mapa = {}
    for col in df.columns:
        cl = col.lower().replace("\n", " ")
        if "ibge" in cl:
            mapa[col] = "cod_ibge"
        elif "ente" in cl or "entidade" in cl or "munic" in cl:
            mapa[col] = "municipio"
        elif col.upper() == "UF":
            mapa[col] = "uf"
        elif "coef" in cl and "distribuic" in cl:
            mapa[col] = "coef_vaar"
        elif "coef" in cl:
            mapa[col] = "coef_vaar"
        elif "complement" in cl and "vaar" in cl:
            mapa[col] = "compl_vaar_prevista"
        elif "vaar" in cl and ("r$" in cl or "valor" in cl or "prevista" in cl):
            mapa[col] = "compl_vaar_prevista"

    df = df.rename(columns=mapa)

    # Filtrar linhas válidas
    if "municipio" in df.columns:
        df = df[df["municipio"].notna()].copy()
        df = df[df["municipio"].astype(str).str.strip() != ""].copy()
        df = df[df["municipio"].astype(str).str.strip() != "nan"].copy()

    # Converter numéricos
    for col in ["coef_vaar", "compl_vaar_prevista"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: _converter_valor(str(x)) if x else None
            )

    if "cod_ibge" in df.columns:
        df["cod_ibge"] = (
            df["cod_ibge"].astype(str).str.strip()
            .str.replace(r"\.0$", "", regex=True)
            .str.zfill(7)
        )

    df["ano"] = ano
    return _filtrar_mg(df) if not df.empty else df


def carregar_coeficientes(ano: int, url: str) -> pd.DataFrame:
    """Baixa e processa coeficientes VAAR para um ano."""
    conteudo = _baixar(url, f"fnde_coef_{ano}")
    if not conteudo:
        return pd.DataFrame()

    url_l = url.lower()
    if url_l.endswith(".csv"):
        df = _parsear_csv(conteudo, ano)
    elif url_l.endswith((".xlsx", ".xls")):
        df = _parsear_xlsx(conteudo, ano)
    else:
        df = _parsear_pdf(conteudo, ano)

    logger.success(f"Coeficientes {ano}: {len(df)} municípios de MG.")
    return df


def coletar_todos_anos(anos: list[int] = ANOS_COLETA) -> pd.DataFrame:
    """Coleta coeficientes VAAR para todos os anos."""
    cache_path = DATA_PROCESSED / "fnde_coeficientes.parquet"
    if cache_valido(cache_path):
        logger.info("Cache coeficientes válido — carregando do disco.")
        return pd.read_parquet(cache_path)

    dfs = []
    for ano in anos:
        url = _descobrir_url_coef(ano)
        if not url:
            logger.warning(f"URL coeficientes não encontrada para {ano}.")
            continue
        try:
            df = carregar_coeficientes(ano, url)
            if not df.empty:
                dfs.append(df)
        except Exception as e:
            logger.error(f"Falha coeficientes {ano}: {e}")

    if not dfs:
        logger.warning("Nenhum coeficiente coletado.")
        return pd.DataFrame()

    df_final = pd.concat(dfs, ignore_index=True)
    salvar_parquet(df_final, "fnde_coeficientes")
    logger.success(f"Coeficientes: {len(df_final)} registros coletados.")
    return df_final


if __name__ == "__main__":
    df = coletar_todos_anos()
    if not df.empty:
        print(df[["municipio", "ano", "coef_vaar", "compl_vaar_prevista"]].head(15))
        print(f"\nTotal: {len(df)} | Anos: {sorted(df['ano'].unique())}")
        print(f"Municípios com coef_vaar: {df['coef_vaar'].notna().sum()}")
    else:
        print("Nenhum dado coletado.")
