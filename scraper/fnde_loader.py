"""
scraper/fnde_loader.py  (versão 2 — suporte a PDF, XLSX e CSV)

Formatos por ano:
  2024 receitas:     PDF (portaria interministerial)      → header em linha variável
  2024 inabilitados: XLSX Planilha1                       → header linha 5, tem VAAR devida
  2025 receitas:     PDF (portaria interministerial)      → header em linha variável
  2025 inabilitados: PDF                                  → parsing por tabela/texto
  2026 receitas:     CSV sep=';'                          → header linha 9, municípios individuais
  2026 inabilitados: CSV sep=';'                          → header linha 9, Cond. I/II/III/IV/V Sim/Não
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
    ANOS_COLETA, PREFIXO_IBGE_MG, TIMEOUT_S,
    DATA_RAW, CONDICIONALIDADES, MOTIVO_SEM_EVOLUCAO,
)
from utils.cache import salvar_parquet, cache_valido, DATA_PROCESSED
from scraper.fnde_discovery import descobrir_todas_urls

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    )
}


# ─────────────────────────────────────────────────────────────────────────────
# DOWNLOAD
# ─────────────────────────────────────────────────────────────────────────────

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def _baixar_arquivo(url: str, nome_local: str) -> bytes | None:
    """Baixa qualquer arquivo e salva em data/raw/."""
    logger.info(f"Baixando: {url}")
    try:
        resp = requests.get(url, headers=HEADERS, timeout=TIMEOUT_S, stream=True)
        resp.raise_for_status()
        conteudo = resp.content
        DATA_RAW.mkdir(parents=True, exist_ok=True)
        ct = resp.headers.get("Content-Type", "")
        if "pdf"  in ct or url.lower().endswith(".pdf"):  ext = ".pdf"
        elif "csv" in ct or url.lower().endswith(".csv"):  ext = ".csv"
        elif "xlsx" in ct or url.lower().endswith(".xlsx"): ext = ".xlsx"
        elif "xls"  in ct or url.lower().endswith(".xls"):  ext = ".xls"
        else: ext = Path(url.split("?")[0]).suffix or ".bin"
        caminho = DATA_RAW / f"{nome_local}{ext}"
        caminho.write_bytes(conteudo)
        logger.debug(f"Salvo: {caminho} ({len(conteudo)/1024:.1f} KB)")
        return conteudo
    except requests.RequestException as e:
        logger.error(f"Erro ao baixar {url}: {e}")
        raise


# ─────────────────────────────────────────────────────────────────────────────
# DETECTAR FORMATO
# ─────────────────────────────────────────────────────────────────────────────

def _detectar_formato(url: str, conteudo: bytes) -> str:
    """Retorna 'pdf', 'csv' ou 'xlsx'/'xls' baseado na URL e conteúdo."""
    url_l = url.lower()
    if url_l.endswith(".csv"):  return "csv"
    if url_l.endswith(".xlsx"): return "xlsx"
    if url_l.endswith(".xls"):  return "xls"
    if url_l.endswith(".pdf"):  return "pdf"
    # Detectar por magic bytes
    if conteudo[:4] == b"%PDF": return "pdf"
    if conteudo[:2] == b"PK":   return "xlsx"
    if b"\r\n" in conteudo[:100] or b";" in conteudo[:200]: return "csv"
    return "pdf"


# ─────────────────────────────────────────────────────────────────────────────
# PARSING RECEITAS
# ─────────────────────────────────────────────────────────────────────────────

def _parsear_receitas_csv(conteudo: bytes, ano: int) -> pd.DataFrame:
    """
    CSV de receitas 2026+
    Cabeçalho na linha 9, separador ';', colunas incluem VAAR por município.
    """
    df = pd.read_csv(
        io.BytesIO(conteudo), sep=";", header=9,
        dtype=str, encoding="latin-1", skip_blank_lines=False
    )
    df.columns = [str(c).strip() for c in df.columns]
    logger.debug(f"CSV receitas colunas: {list(df.columns)}")

    # Mapear colunas
    mapa = {}
    for col in df.columns:
        cl = col.lower().replace("\n", " ")
        if "ibge" in cl:                         mapa[col] = "cod_ibge"
        elif "entidade" in cl or "ente" in cl:   mapa[col] = "municipio"
        elif col.upper() == "UF":                mapa[col] = "uf"
        elif "vaar" in cl and "complement" in cl: mapa[col] = "compl_vaar"
        elif "total" in cl and "receita" in cl:  mapa[col] = "total_previsto"
    df = df.rename(columns=mapa)

    # Converter valores monetários
    for col in ["compl_vaar", "total_previsto"]:
        if col in df.columns:
            df[col] = df[col].apply(_converter_valor)

    df["ano"] = ano
    return _filtrar_mg(df)


def _parsear_receitas_xlsx(conteudo: bytes, ano: int) -> pd.DataFrame:
    """
    XLSX de receitas — Ajuste Anual 2024.
    Só tem totais por estado — não tem VAAR por município.
    Retorna DataFrame vazio (não é útil para o projeto).
    """
    logger.warning(f"XLSX de receitas {ano} é ajuste anual por estado — sem dados municipais.")
    return pd.DataFrame()


def _parsear_receitas_pdf(conteudo: bytes, ano: int) -> pd.DataFrame:
    """PDF de receitas (2024 e 2025)."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber não instalado")
        return pd.DataFrame()

    registros = []
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        for pagina in pdf.pages:
            tabela = pagina.extract_table()
            if tabela:
                for linha in tabela:
                    reg = _parsear_linha_receita_pdf(linha, ano)
                    if reg:
                        registros.append(reg)

    df = pd.DataFrame(registros)
    if df.empty:
        return df
    return _filtrar_mg(df)


def _parsear_linha_receita_pdf(linha: list, ano: int) -> dict | None:
    """Converte linha do PDF de receitas em dicionário."""
    try:
        cels = [str(c).strip() if c else "" for c in linha]
        # Identificar código IBGE (7 dígitos)
        cod_ibge = ""
        for c in cels:
            if re.match(r"^\d{7}$", c.replace(" ", "")):
                cod_ibge = c.replace(" ", "")
                break
        if not cod_ibge:
            return None

        idx = next(i for i, c in enumerate(cels)
                   if re.match(r"^\d{7}$", c.replace(" ", "")))
        municipio = cels[idx + 1] if idx + 1 < len(cels) else ""
        uf = cels[0] if re.match(r"^[A-Z]{2}$", cels[0]) else ""

        valores = [_converter_valor(v) for v in cels[idx+2:]
                   if _converter_valor(v) is not None]

        reg = {"uf": uf, "cod_ibge": cod_ibge,
               "municipio": municipio.strip().title(), "ano": ano}

        # Tentar mapear colunas por posição típica do PDF do FNDE
        # Ordem: contribuição estados | VAAF | VAAT | VAAR | total
        colunas = ["receita_contribuicao", "compl_vaaf",
                   "compl_vaat", "compl_vaar", "total_previsto"]
        for i, col in enumerate(colunas):
            reg[col] = valores[i] if i < len(valores) else None
        return reg
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────────────────────
# PARSING INABILITADOS
# ─────────────────────────────────────────────────────────────────────────────

def _parsear_inabilitados_csv_2026(conteudo: bytes, ano: int) -> pd.DataFrame:
    """
    CSV de inabilitados 2026+
    Cabeçalho linha 9, colunas: UF | Código IBGE | Entidade | Cond.I | Cond.II | ...
    Valores: 'Sim' = cumpriu, 'Não' = descumpriu.
    """
    df = pd.read_csv(
        io.BytesIO(conteudo), sep=";", header=9,
        dtype=str, encoding="latin-1", skip_blank_lines=False
    )
    df.columns = [str(c).strip() for c in df.columns]
    logger.debug(f"CSV inabilitados colunas: {list(df.columns)}")

    # Mapear colunas base
    mapa = {}
    for col in df.columns:
        cl = col.lower()
        if "ibge" in cl:                         mapa[col] = "cod_ibge"
        elif "entidade" in cl or "ente" in cl:   mapa[col] = "municipio"
        elif col.upper() == "UF":                mapa[col] = "uf"
    df = df.rename(columns=mapa)

    # Identificar colunas de condicionalidades (Cond. I, Cond. II, etc.)
    cols_cond = {col: col for col in df.columns
                 if re.search(r"cond", col, re.IGNORECASE)}

    # Montar motivo e habilitação
    registros = []
    for _, row in df.iterrows():
        cod  = str(row.get("cod_ibge", "")).strip()
        mun  = str(row.get("municipio", "")).strip().title()
        uf   = str(row.get("uf", "")).strip().upper()

        if not cod or not mun or mun == "Nan":
            continue

        # Descobrir quais condicionalidades falharam (valor = 'Não')
        descumpridas = []
        for col in cols_cond:
            val = str(row.get(col, "")).strip().upper()
            if val == "NÃO" or val == "NAO" or val == "N":
                # Extrair inciso romano do nome da coluna
                inciso = re.search(r"\b(I{1,3}V?|VI{0,3}|IV|V)\b", col)
                if inciso:
                    i = inciso.group(1)
                    descumpridas.append(f"{i} — {CONDICIONALIDADES.get(i, i)}")

        # Se todas as condicionalidades são Sim mas não recebe VAAR = sem evolução
        habilitado = len(descumpridas) == 0

        # Para o CSV de 2026, todos os registros são beneficiários OU não beneficiários
        # Verificar se há coluna de beneficiário
        for col in df.columns:
            if "benefici" in col.lower() or "habilitad" in col.lower():
                val = str(row.get(col, "")).strip().upper()
                if "NÃO" in val or "NAO" in val or "N" == val:
                    habilitado = False
                    if not descumpridas:
                        descumpridas.append(MOTIVO_SEM_EVOLUCAO)
                break

        if not habilitado:
            registros.append({
                "uf": uf,
                "cod_ibge": cod.zfill(7),
                "municipio": mun,
                "motivo_inabilitacao": "; ".join(descumpridas) or "Não beneficiário",
                "condicionalidades_descumpridas": " | ".join(descumpridas),
                "habilitado_vaar": False,
                "ano": ano,
            })

    df_result = pd.DataFrame(registros)
    logger.info(f"CSV inabilitados {ano}: {len(df_result)} não beneficiários.")
    return _filtrar_mg(df_result) if not df_result.empty else df_result


def _parsear_inabilitados_xlsx_2024(conteudo: bytes, ano: int) -> pd.DataFrame:
    """
    XLSX de inabilitados 2024 — Ajuste VAAR.
    Aba: Planilha1, cabeçalho linha 5.
    Colunas: UF | Ente Federado | Código IBGE | VAAR devida | VAAR distribuída | Ajuste
    Contém os repasses VAAR reais de 2024 por município!
    """
    df = pd.read_excel(
        io.BytesIO(conteudo), sheet_name="Planilha1",
        header=5, dtype=str
    )
    df.columns = [str(c).strip() for c in df.columns]
    logger.debug(f"XLSX inabilitados 2024 colunas: {list(df.columns)}")

    # Mapear colunas
    mapa = {}
    for col in df.columns:
        cl = col.lower()
        if "ibge" in cl or "código" in cl:           mapa[col] = "cod_ibge"
        elif "ente" in cl or "federado" in cl:       mapa[col] = "municipio"
        elif col.upper() == "UF":                    mapa[col] = "uf"
        elif "devida" in cl and "vaar" in cl:        mapa[col] = "compl_vaar"
        elif "distribuída" in cl or "distribuida" in cl: mapa[col] = "vaar_distribuido"
        elif "ajuste" in cl:                         mapa[col] = "ajuste_vaar"
    df = df.rename(columns=mapa)

    # Converter valores
    for col in ["compl_vaar", "vaar_distribuido", "ajuste_vaar"]:
        if col in df.columns:
            df[col] = df[col].apply(
                lambda x: _converter_valor(str(x)) if x else None
            )

    # Filtrar linhas com cod_ibge válido
    if "cod_ibge" in df.columns:
        df = df[df["cod_ibge"].astype(str).str.match(r"^\d{6,7}$", na=False)].copy()
        df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip().str.zfill(7)

    if "municipio" in df.columns:
        df["municipio"] = df["municipio"].astype(str).str.strip().str.title()

    df["ano"] = ano
    df["habilitado_vaar"] = True  # este arquivo é de ajuste — todos receberam VAAR
    df["motivo_inabilitacao"] = ""

    resultado = _filtrar_mg(df)
    logger.info(f"XLSX repasses VAAR {ano}: {len(resultado)} municípios de MG.")
    return resultado


def _parsear_inabilitados_pdf(conteudo: bytes, ano: int) -> pd.DataFrame:
    """PDF de inabilitados (2025)."""
    try:
        import pdfplumber
    except ImportError:
        logger.error("pdfplumber não instalado")
        return pd.DataFrame()

    registros = []
    with pdfplumber.open(io.BytesIO(conteudo)) as pdf:
        for pagina in pdf.pages:
            tabela = pagina.extract_table()
            if tabela:
                for linha in tabela:
                    reg = _parsear_linha_inabilitado_pdf(linha, ano)
                    if reg:
                        registros.append(reg)
            else:
                texto = pagina.extract_text() or ""
                registros += _parsear_texto_inabilitados(texto, ano)

    df = pd.DataFrame(registros)
    return _filtrar_mg(df) if not df.empty else df


def _parsear_linha_inabilitado_pdf(linha: list, ano: int) -> dict | None:
    """Converte linha do PDF de inabilitados."""
    try:
        cels = [str(c).strip() if c else "" for c in linha]
        if len(cels) < 3:
            return None
        if cels[0].upper() in ("UF", "SIGLA", ""):
            return None

        uf = cels[0].strip().upper()
        municipio = cels[1].strip().title() if len(cels) > 1 else ""
        cod_ibge = ""
        motivo = ""

        for c in cels[2:4]:
            if re.match(r"^\d{6,7}$", c.replace(" ", "")):
                cod_ibge = c.replace(" ", "").zfill(7)
                break

        for c in reversed(cels):
            if len(c) > 20:
                motivo = c
                break

        if not uf or not municipio:
            return None

        return {
            "uf": uf, "cod_ibge": cod_ibge,
            "municipio": municipio,
            "motivo_inabilitacao": motivo,
            "habilitado_vaar": False,
            "condicionalidades_descumpridas": _extrair_condicionalidades(motivo),
            "ano": ano,
        }
    except Exception:
        return None


def _parsear_texto_inabilitados(texto: str, ano: int) -> list[dict]:
    """Extrai inabilitados de texto livre do PDF."""
    registros = []
    padrao = re.compile(
        r"([A-Z]{2})\s+"
        r"([A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇ][A-ZÁÉÍÓÚÂÊÎÔÛÃÕÇa-záéíóúâêîôûãõç\s]+?)\s+"
        r"(\d{6,7})\s+"
        r"(Não.{10,200}?)(?=\n[A-Z]{2}\s|\Z)",
        re.DOTALL
    )
    for match in padrao.finditer(texto):
        uf, mun, cod, motivo = match.groups()
        registros.append({
            "uf": uf.strip(),
            "cod_ibge": cod.strip().zfill(7),
            "municipio": mun.strip().title(),
            "motivo_inabilitacao": motivo.strip(),
            "habilitado_vaar": False,
            "condicionalidades_descumpridas": _extrair_condicionalidades(motivo),
            "ano": ano,
        })
    return registros


# ─────────────────────────────────────────────────────────────────────────────
# UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

def _extrair_condicionalidades(motivo: str) -> str:
    if not motivo:
        return ""
    if MOTIVO_SEM_EVOLUCAO.lower() in motivo.lower():
        return "Sem evolução nos indicadores (Art. 14 §2º)"
    incisos = re.findall(r"\b(I{1,3}V?|VI{0,3}|IV|V)\b", motivo)
    vistos, resultado = set(), []
    for i in incisos:
        if i not in vistos:
            vistos.add(i)
            resultado.append(f"{i} — {CONDICIONALIDADES.get(i, i)}")
    return " | ".join(resultado)


def _converter_valor(texto: str) -> float | None:
    if not texto or str(texto).strip() in ("-", "—", "", "None", "nan"):
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


# ─────────────────────────────────────────────────────────────────────────────
# FUNÇÕES PRINCIPAIS
# ─────────────────────────────────────────────────────────────────────────────

def carregar_receitas(ano: int, url: str) -> pd.DataFrame:
    """Baixa e processa receitas FUNDEB detectando o formato automaticamente."""
    conteudo = _baixar_arquivo(url, f"fnde_receitas_{ano}")
    if not conteudo:
        return pd.DataFrame()
    fmt = _detectar_formato(url, conteudo)
    logger.info(f"Receitas {ano}: formato={fmt}")
    if fmt == "csv":
        df = _parsear_receitas_csv(conteudo, ano)
    elif fmt in ("xlsx", "xls"):
        df = _parsear_receitas_xlsx(conteudo, ano)
    else:
        df = _parsear_receitas_pdf(conteudo, ano)
    logger.success(f"Receitas {ano}: {len(df)} municípios de MG.")
    return df


def carregar_inabilitados(ano: int, url: str) -> pd.DataFrame:
    """Baixa e processa inabilitados/ajuste VAAR detectando o formato."""
    conteudo = _baixar_arquivo(url, f"fnde_inabilitados_{ano}")
    if not conteudo:
        return pd.DataFrame()
    fmt = _detectar_formato(url, conteudo)
    logger.info(f"Inabilitados {ano}: formato={fmt}")
    if fmt == "csv":
        df = _parsear_inabilitados_csv_2026(conteudo, ano)
    elif fmt in ("xlsx", "xls"):
        df = _parsear_inabilitados_xlsx_2024(conteudo, ano)
    else:
        df = _parsear_inabilitados_pdf(conteudo, ano)
    logger.success(f"Inabilitados/repasses {ano}: {len(df)} municípios de MG.")
    return df


def coletar_todos_anos(anos: list[int] = ANOS_COLETA) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Pipeline principal: descobre URLs, baixa e processa para todos os anos."""
    cache_rec  = DATA_PROCESSED / "fnde_receitas.parquet"
    cache_inab = DATA_PROCESSED / "fnde_inabilitados.parquet"
    from utils.cache import cache_valido
    if cache_valido(cache_rec) and cache_valido(cache_inab):
        logger.info("Cache FNDE válido — carregando do disco.")
        return pd.read_parquet(cache_rec), pd.read_parquet(cache_inab)

    logger.info("=== Descobrindo URLs FNDE ===")
    urls_por_ano = descobrir_todas_urls(anos)

    dfs_rec, dfs_inab = [], []
    for ano in anos:
        urls = urls_por_ano.get(ano, {})

        url_rec = urls.get("receitas")
        if url_rec:
            try:
                df = carregar_receitas(ano, url_rec)
                if not df.empty:
                    dfs_rec.append(df)
            except Exception as e:
                logger.error(f"Receitas {ano}: {e}")

        url_inab = urls.get("inabilitados")
        if url_inab:
            try:
                df = carregar_inabilitados(ano, url_inab)
                if not df.empty:
                    dfs_inab.append(df)
            except Exception as e:
                logger.error(f"Inabilitados {ano}: {e}")

    df_rec  = pd.concat(dfs_rec,  ignore_index=True) if dfs_rec  else pd.DataFrame()
    df_inab = pd.concat(dfs_inab, ignore_index=True) if dfs_inab else pd.DataFrame()

    if not df_rec.empty:
        salvar_parquet(df_rec,  "fnde_receitas")
    if not df_inab.empty:
        salvar_parquet(df_inab, "fnde_inabilitados")

    logger.success(f"FNDE: {len(df_rec)} receitas | {len(df_inab)} inabilitados/repasses")
    return df_rec, df_inab


if __name__ == "__main__":
    df_rec, df_inab = coletar_todos_anos()
    print("\n=== RECEITAS (amostra) ===")
    cols = [c for c in ["municipio","ano","compl_vaar","total_previsto"] if c in df_rec.columns]
    print(df_rec[cols].dropna(subset=["municipio"]).head(10))
    print(f"\nTotal receitas: {len(df_rec)}")
    print("\n=== INABILITADOS/REPASSES (amostra) ===")
    cols2 = [c for c in ["municipio","ano","compl_vaar","motivo_inabilitacao","habilitado_vaar"] if c in df_inab.columns]
    print(df_inab[cols2].head(10))
    print(f"\nTotal: {len(df_inab)}")
