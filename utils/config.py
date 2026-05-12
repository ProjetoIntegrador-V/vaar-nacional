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
    "ibge_malha":      "https://servicodados.ibge.gov.br/api/v2/malhas/31/?resolucao=5&formato=application/vnd.geo+json",
    "ibge_municipios": "https://servicodados.ibge.gov.br/api/v1/localidades/estados/31/municipios",
}

# ── Parâmetros gerais ────────────────────────────────────────────────────────
CACHE_TTL_H   = 24
TIMEOUT_S     = 60
MAX_RETRIES   = 3
SELENIUM_WAIT = 15

# ── IBGE ─────────────────────────────────────────────────────────────────────
COD_ESTADO_MG   = 31
PREFIXO_IBGE_MG = "31"

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
    2025: 1_600_000_000.0,
    2026: 1_800_000_000.0,
}
