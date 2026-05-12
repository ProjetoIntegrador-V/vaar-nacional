"""
scraper/downloader_inep.py
Baixa microdados do SAEB e Censo Escolar do INEP para compor
os indicadores IRAP (desempenho) e IRE (rendimento).

O INEP disponibiliza arquivos ZIP com CSVs de microdados.
Para este projeto, usamos os indicadores agregados por município
(mais leves que os microdados individuais).

Uso:
    python -m scraper.downloader_inep
"""
from __future__ import annotations
import io
import zipfile
import requests
import pandas as pd
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from utils.config import URLS, ANOS_COLETA, TIMEOUT_S, DATA_RAW
from utils.cache import salvar_parquet, cache_valido, DATA_PROCESSED

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 Chrome/124.0.0.0 Safari/537.36"
    )
}

# URLs dos indicadores educacionais municipais (mais leves que microdados)
# O INEP disponibiliza planilhas de indicadores agregados por município
URLS_INDICADORES_INEP = {
    "taxa_aprovacao": (
        "https://download.inep.gov.br/informacoes_estatisticas/"
        "indicadores_educacionais/taxa_aprovacao/taxa_aprovacao_{ano}.zip"
    ),
    "taxa_abandono": (
        "https://download.inep.gov.br/informacoes_estatisticas/"
        "indicadores_educacionais/taxa_abandono/taxa_abandono_{ano}.zip"
    ),
    "distorcao_idade_serie": (
        "https://download.inep.gov.br/informacoes_estatisticas/"
        "indicadores_educacionais/distorcao_idade_serie/distorcao_idade_serie_{ano}.zip"
    ),
    # SAEB — resultados por município
    "saeb_municipios": (
        "https://download.inep.gov.br/educacao_basica/saeb/"
        "resultados/{ano}/saeb_{ano}_municipios.zip"
    ),
}


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=5, max=30))
def baixar_indicador(indicador: str, ano: int, session: requests.Session) -> pd.DataFrame | None:
    """
    Baixa e processa um indicador educacional do INEP para um ano.

    Args:
        indicador: chave do indicador (ex: 'taxa_aprovacao')
        ano:       ano de referência
        session:   sessão HTTP reutilizável

    Returns:
        DataFrame com indicador por município de MG
    """
    url = URLS_INDICADORES_INEP[indicador].format(ano=ano)
    logger.info(f"Baixando {indicador} {ano}: {url}")

    try:
        resp = session.get(url, headers=HEADERS, timeout=120, stream=True)
        resp.raise_for_status()
    except requests.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning(f"{indicador} {ano} não disponível (404).")
            return None
        raise

    # Salvar ZIP bruto
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    arquivo_zip = DATA_RAW / f"inep_{indicador}_{ano}.zip"
    arquivo_zip.write_bytes(resp.content)

    # Extrair CSV do ZIP
    try:
        with zipfile.ZipFile(io.BytesIO(resp.content)) as zf:
            # Encontrar o CSV principal dentro do ZIP
            csvs = [n for n in zf.namelist() if n.endswith(".csv") and "municipio" in n.lower()]
            if not csvs:
                csvs = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csvs:
                logger.warning(f"Nenhum CSV encontrado em {indicador} {ano}.")
                return None

            csv_nome = csvs[0]
            logger.debug(f"Lendo arquivo: {csv_nome}")

            with zf.open(csv_nome) as f:
                df = pd.read_csv(
                    f, sep=";", encoding="latin-1",
                    dtype=str, low_memory=False
                )
    except zipfile.BadZipFile:
        logger.error(f"ZIP corrompido para {indicador} {ano}.")
        return None

    return _padronizar_inep(df, indicador, ano)


def _padronizar_inep(df: pd.DataFrame, indicador: str, ano: int) -> pd.DataFrame:
    """
    Padroniza colunas do INEP e filtra apenas municípios de MG.
    """
    df.columns = [c.strip().upper() for c in df.columns]

    # Mapa de colunas INEP → padrão do projeto
    mapa = {
        "CO_MUNICIPIO": "cod_ibge", "CO_MUN_IBGE": "cod_ibge",
        "NO_MUNICIPIO": "municipio", "NM_MUNICIPIO": "municipio",
        "SG_UF": "uf", "NO_UF": "uf",
        # Taxas — nomes variam por indicador e ano
        "VL_TAXA_APROVACAO": "taxa_aprovacao",
        "VL_TAXA_ABANDONO":  "taxa_abandono",
        "VL_TAXA_DISTORCAO": "taxa_distorcao",
        "VL_MEDIA_MATEMATICA": "media_matematica",
        "VL_MEDIA_LINGUA_PORTUGUESA": "media_portugues",
    }

    renomear = {c: mapa[c] for c in df.columns if c in mapa}
    df = df.rename(columns=renomear)

    # Filtrar MG
    if "uf" in df.columns:
        df = df[df["uf"].str.strip().str.upper() == "MG"].copy()

    # Converter colunas numéricas
    colunas_num = [c for c in df.columns if c not in ("cod_ibge", "municipio", "uf")]
    for col in colunas_num:
        df[col] = pd.to_numeric(df[col].str.replace(",", "."), errors="coerce")

    # Garantir cod_ibge como string de 7 dígitos
    if "cod_ibge" in df.columns:
        df["cod_ibge"] = df["cod_ibge"].astype(str).str.strip().str[:7].str.zfill(7)

    df["indicador"] = indicador
    df["ano"] = ano

    logger.info(f"INEP {indicador} {ano}: {len(df)} municípios de MG.")
    return df


def consolidar_indicadores_inep(dfs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """
    Consolida os indicadores do INEP em um único DataFrame por município/ano,
    calculando proxies para IRAP e IRE.

    IRAP (Desempenho Escolar) ← médias do SAEB (Português + Matemática)
    IRE  (Rendimento Escolar) ← taxas de aprovação, abandono, distorção idade-série
    """
    resultado = []

    # Obter lista de municípios/anos únicos
    todos_muns = set()
    for df in dfs.values():
        if df is not None and not df.empty and "cod_ibge" in df.columns:
            for _, row in df[["cod_ibge", "municipio", "ano"]].drop_duplicates().iterrows():
                todos_muns.add((row["cod_ibge"], row.get("municipio", ""), row["ano"]))

    for cod, mun, ano in sorted(todos_muns):
        reg = {"cod_ibge": cod, "municipio": mun, "ano": ano}

        # IRAP: normalizar médias SAEB para [0, 1]
        # Escala SAEB: 0–500 (Fundamental I) ou 0–425 (Fundamental II)
        saeb = dfs.get("saeb_municipios")
        if saeb is not None:
            mask = (saeb["cod_ibge"] == cod) & (saeb["ano"] == ano)
            row_saeb = saeb[mask]
            if not row_saeb.empty:
                media_port = row_saeb.get("media_portugues", pd.Series([None])).values[0]
                media_mat  = row_saeb.get("media_matematica", pd.Series([None])).values[0]
                if media_port and media_mat:
                    # Normaliza para [0, 1] assumindo escala máxima de 500
                    reg["IRAP"] = round(((media_port + media_mat) / 2) / 500, 4)

        # IRE: composto de aprovação (positivo) – abandono – distorção
        taxa_aprov = dfs.get("taxa_aprovacao")
        taxa_aband = dfs.get("taxa_abandono")
        taxa_dist  = dfs.get("distorcao_idade_serie")

        aprovacao  = _extrair_valor(taxa_aprov,  cod, ano, "taxa_aprovacao")
        abandono   = _extrair_valor(taxa_aband,  cod, ano, "taxa_abandono")
        distorcao  = _extrair_valor(taxa_dist,   cod, ano, "taxa_distorcao")

        if aprovacao is not None:
            # Fórmula simplificada: combina aprovação (positivo) com
            # penalização de abandono e distorção, normalizada para [0, 1]
            ire = aprovacao / 100
            if abandono is not None:
                ire -= (abandono / 100) * 0.3
            if distorcao is not None:
                ire -= (distorcao / 100) * 0.2
            reg["IRE"] = round(max(0.0, min(1.0, ire)), 4)

        resultado.append(reg)

    df_consolidado = pd.DataFrame(resultado)
    logger.success(f"INEP consolidado: {len(df_consolidado)} registros.")
    return df_consolidado


def _extrair_valor(df: pd.DataFrame | None, cod: str, ano: int, coluna: str) -> float | None:
    """Extrai valor de um indicador para um município/ano específico."""
    if df is None or df.empty or coluna not in df.columns:
        return None
    mask = (df["cod_ibge"] == cod) & (df["ano"] == ano)
    valores = df[mask][coluna].dropna().values
    return float(valores[0]) if len(valores) > 0 else None


# ── Execução principal ───────────────────────────────────────────────────────

def coletar_todos_anos(anos: list[int] = ANOS_COLETA) -> pd.DataFrame:
    """Coleta indicadores do INEP para todos os anos e consolida."""
    caminho_cache = DATA_PROCESSED / "inep_indicadores.parquet"
    if cache_valido(caminho_cache):
        logger.info("Cache INEP válido — carregando do disco.")
        return pd.read_parquet(caminho_cache)

    session = requests.Session()
    dfs_por_indicador: dict[str, list] = {k: [] for k in URLS_INDICADORES_INEP}

    for ano in anos:
        logger.info(f"── Coletando INEP {ano} ──")
        for indicador in URLS_INDICADORES_INEP:
            try:
                df = baixar_indicador(indicador, ano, session)
                if df is not None:
                    dfs_por_indicador[indicador].append(df)
            except Exception as e:
                logger.error(f"Falha INEP {indicador} {ano}: {e}")

    session.close()

    # Concatenar por indicador
    dfs_concat = {
        k: pd.concat(v, ignore_index=True) if v else None
        for k, v in dfs_por_indicador.items()
    }

    df_final = consolidar_indicadores_inep(dfs_concat)
    salvar_parquet(df_final, "inep_indicadores")
    logger.success(f"INEP: {len(df_final)} registros consolidados.")
    return df_final


if __name__ == "__main__":
    df = coletar_todos_anos()
    print(df.head(10))
    print(f"\nTotal: {len(df)} registros | Colunas: {list(df.columns)}")
