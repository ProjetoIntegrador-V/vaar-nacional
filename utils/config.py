"""
utils/config.py
Configurações centrais do projeto — URLs, caminhos, constantes.
Atualizado com URLs reais do FNDE para 2024, 2025 e 2026.
"""
from __future__ import annotations
from pathlib import Path

# ── Diretórios ──────────────────────────────────────────────────────────────
BASE_DIR       = Path(__file__).resolve().parent.parent
DATA_RAW       = BASE_DIR / "data" / "raw"
DATA_PROCESSED = BASE_DIR / "data" / "processed"
DATA_GEO       = BASE_DIR / "data" / "geo"

# ── Anos ────────────────────────────────────────────────────────────────────
ANOS_COLETA        = [2024, 2025, 2026]
ANO_MAIS_RECENTE   = 2026
ANO_BASE_HISTORICO = 2022

# ── Páginas índice do FNDE por ano (scraping para descobrir links) ───────────
FNDE_PAGINAS_INDICE = {
    2024: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2024-1",
    2025: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2025-1",
    2026: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2026",
}

# ── URLs diretas dos PDFs (fallback quando o scraping não encontrar) ─────────
FNDE_PDF_RECEITAS_FALLBACK = {
    2024: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2024-1/receita-total-do-fundeb-por-ente-federado-2024.pdf",
    2025: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/vaat/3-publicacao/receita-total-do-fundeb-por-ente-federado.pdf",
    2026: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2026/receita-total-do-fundeb-por-ente-federado.pdf",
}

FNDE_PDF_INABILITADOS_FALLBACK = {
    2024: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2024-1/RedesInabilitadasVAAR20241.pdf",
    2025: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2025-1/RedesInabilitadasVAAR20251.pdf",
    2026: "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb/2026/lista-entes-beneficiarios-nao-beneficiarios-vaar-2026.pdf",
}

# Página de listagem para scraping
FNDE_PAGINA_FUNDEB = "https://www.gov.br/fnde/pt-br/acesso-a-informacao/acoes-e-programas/financiamento/fundeb"

# ── Palavras-chave para identificar arquivos nas páginas do FNDE ─────────────
FNDE_KEYWORDS_RECEITAS = [
    "receita-total", "receita_total", "receitatotal",
    "por-ente-federado", "ente-federado",
    "portaria-interministerial",
]
FNDE_KEYWORDS_INABILITADOS = [
    "inabilitad", "redes-inabilitadas", "redesinabilitadas",
    "nao-beneficiarios", "beneficiarios",
    "vaar",
]
# Formatos preferidos — CSV/XLSX são mais fáceis de processar que PDF
FNDE_FORMATOS_PREFERIDOS = [".csv", ".xlsx", ".xls", ".pdf"]

# ── URLs das demais fontes ───────────────────────────────────────────────────
URLS = {
    "fjp_portal":      "https://robin-hood.fjp.mg.gov.br",
    "fnde_fundeb":     FNDE_PAGINA_FUNDEB,
    "inep_saeb":       "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/saeb",
    "inep_censo":      "https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/censo-escolar",
    "ibge_malha":      "https://servicodados.ibge.gov.br/api/v2/malhas/{cod}/?resolucao=5&formato=application/vnd.geo+json",
    "ibge_municipios": "https://servicodados.ibge.gov.br/api/v1/localidades/estados/{cod}/municipios",
    "geodata_br_mun":  "https://raw.githubusercontent.com/tbrugz/geodata-br/master/geojson/geojs-{cod}-mun.json",
}

# ── Parâmetros gerais ────────────────────────────────────────────────────────
CACHE_TTL_H   = 24
TIMEOUT_S     = 60
MAX_RETRIES   = 3
SELENIUM_WAIT = 15

# ── IBGE — UFs (código, câmera do mapa) ──────────────────────────────────────
# Centro e zoom aproximados para choropleth_mapbox (não são sede oficial).
ESTADOS: dict[str, dict] = {
    "AC": {"nome": "Acre",                "cod": "12", "lat": -9.0,  "lon": -70.5, "zoom": 6.0},
    "AL": {"nome": "Alagoas",             "cod": "27", "lat": -9.6,  "lon": -36.6, "zoom": 7.0},
    "AM": {"nome": "Amazonas",            "cod": "13", "lat": -3.5,  "lon": -65.0, "zoom": 4.8},
    "AP": {"nome": "Amapá",               "cod": "16", "lat": 1.4,   "lon": -51.8, "zoom": 6.2},
    "BA": {"nome": "Bahia",               "cod": "29", "lat": -12.5, "lon": -41.7, "zoom": 5.5},
    "CE": {"nome": "Ceará",               "cod": "23", "lat": -5.2,  "lon": -39.5, "zoom": 6.2},
    "DF": {"nome": "Distrito Federal",    "cod": "53", "lat": -15.8, "lon": -47.9, "zoom": 9.0},
    "ES": {"nome": "Espírito Santo",      "cod": "32", "lat": -19.6, "lon": -40.6, "zoom": 7.0},
    "GO": {"nome": "Goiás",               "cod": "52", "lat": -16.0, "lon": -49.6, "zoom": 5.8},
    "MA": {"nome": "Maranhão",            "cod": "21", "lat": -5.0,  "lon": -45.0, "zoom": 5.8},
    "MG": {"nome": "Minas Gerais",        "cod": "31", "lat": -18.5, "lon": -44.5, "zoom": 5.5},
    "MS": {"nome": "Mato Grosso do Sul",  "cod": "50", "lat": -20.5, "lon": -54.5, "zoom": 5.8},
    "MT": {"nome": "Mato Grosso",         "cod": "51", "lat": -12.6, "lon": -55.7, "zoom": 5.2},
    "PA": {"nome": "Pará",                "cod": "15", "lat": -3.8,  "lon": -52.5, "zoom": 5.0},
    "PB": {"nome": "Paraíba",             "cod": "25", "lat": -7.1,  "lon": -36.7, "zoom": 7.0},
    "PE": {"nome": "Pernambuco",          "cod": "26", "lat": -8.4,  "lon": -37.8, "zoom": 6.5},
    "PI": {"nome": "Piauí",               "cod": "22", "lat": -7.0,  "lon": -42.8, "zoom": 6.0},
    "PR": {"nome": "Paraná",              "cod": "41", "lat": -24.6, "lon": -51.4, "zoom": 6.0},
    "RJ": {"nome": "Rio de Janeiro",      "cod": "33", "lat": -22.3, "lon": -42.9, "zoom": 7.0},
    "RN": {"nome": "Rio Grande do Norte", "cod": "24", "lat": -5.6,  "lon": -36.6, "zoom": 7.0},
    "RO": {"nome": "Rondônia",            "cod": "11", "lat": -10.9, "lon": -62.8, "zoom": 6.0},
    "RR": {"nome": "Roraima",             "cod": "14", "lat": 1.8,   "lon": -61.3, "zoom": 6.0},
    "RS": {"nome": "Rio Grande do Sul",   "cod": "43", "lat": -29.8, "lon": -53.5, "zoom": 5.8},
    "SC": {"nome": "Santa Catarina",      "cod": "42", "lat": -27.3, "lon": -50.5, "zoom": 6.5},
    "SE": {"nome": "Sergipe",             "cod": "28", "lat": -10.6, "lon": -37.4, "zoom": 7.5},
    "SP": {"nome": "São Paulo",           "cod": "35", "lat": -22.2, "lon": -48.8, "zoom": 6.0},
    "TO": {"nome": "Tocantins",           "cod": "17", "lat": -9.5,  "lon": -48.2, "zoom": 5.8},
}

UF_PADRAO = "MG"
COD_ESTADO_MG = int(ESTADOS["MG"]["cod"])
PREFIXO_IBGE_MG = ESTADOS["MG"]["cod"]


def meta_estado(uf: str) -> dict:
    """Retorna metadados da UF (código IBGE, centro, zoom, nome)."""
    chave = uf.strip().upper()
    if chave not in ESTADOS:
        raise ValueError(f"UF inválida: {uf}. Use uma sigla de ESTADOS.")
    return ESTADOS[chave]


def nome_geojson_uf(uf: str) -> str:
    """Nome do arquivo GeoJSON sem extensão (ex.: municipios_mg)."""
    chave = uf.strip().lower()
    meta_estado(chave)
    return f"municipios_{chave}"


# ── Condicionalidades VAAR (Lei 14.113/2020, Art. 14 §1º) ────────────────────
CONDICIONALIDADES = {
    "I":   "Gestores escolares selecionados por mérito/desempenho",
    "II":  "Participação ≥ 80% dos alunos no SAEB",
    "III": "Redução de desigualdades socioeconômicas e raciais",
    "IV":  "Lei estadual ICMS Educação vigente (≥ 10%)",
    "V":   "Currículo alinhado à BNCC aprovado",
}
MOTIVO_SEM_EVOLUCAO = "Não apresentou melhoria em nenhum dos indicadores"

# ── Pesos da fórmula IQE (Lei 24.431/2023) ──────────────────────────────────
PESOS_IQE = {
    "IRAP": 0.50,
    "IRE":  0.20,
    "IAE":  0.15,
    "IGE":  0.15,
}

NOMES_INDICADORES = {
    "IE":   "Índice de Educação do Município",
    "IQE":  "Índice de Qualidade Educacional",
    "IRAP": "Índice de Desempenho Escolar",
    "IRE":  "Índice de Rendimento Escolar",
    "IAE":  "Índice de Atendimento Educacional",
    "IGE":  "Índice de Gestão Escolar",
}

PCT_ICMS_EDUCACAO = 0.10

COLUNAS_CONSOLIDADO = [
    "cod_ibge", "municipio", "ano",
    "IRAP", "IRE", "IAE", "IGE", "IQE", "IE",
    "repasse_icms_educacao", "repasse_vaar",
    "habilitado_vaar", "motivo_inabilitacao",
    "populacao", "area_km2",
]

# ── Totais estaduais MG (referência para cálculo do ICMS Educação) ───────────
# Fonte: SEF-MG e FNDE — atualizar anualmente
TOTAL_ICMS_EDUCACAO_MG = {
    2022: 4_200_000_000.0,
    2023: 4_600_000_000.0,
    2024: 5_100_000_000.0,
    2025: 5_500_000_000.0,
    2026: 5_800_000_000.0,
}

# ── Totais VAAR alocados a MG por ano ───────────────────────────────────────
# Fonte: PDFs de receitas do FNDE — atualizar após cada portaria
TOTAL_VAAR_MG = {
    2022:   850_000_000.0,
    2023: 1_100_000_000.0,
    2024: 1_400_000_000.0,
    2025: 4_459_289_692.0,   # acumulado 3 portarias (fonte: FNDE PDF 3a pub.)
    2026: 1_800_000_000.0,   # estimativa 1a portaria
}