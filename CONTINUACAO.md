# 📋 Estado do Projeto — Guia de Continuação

## O que foi implementado

### Módulos completos e funcionais
| Arquivo | Status | Descrição |
|---|---|---|
| `utils/config.py` | ✅ | Extensível para 2026+ — basta adicionar URL da nova página índice |
| `utils/cache.py` | ✅ | Parquet, JSON, GeoJSON com TTL |
| `utils/formatters.py` | ✅ | Formatação de moeda, índices, percentuais |
| `utils/validators.py` | ✅ | Validação de índices e cod_ibge |
| `calculadora/formulas.py` | ✅ | Fórmulas IQE, IE, CoefVAAR, ValorVAAR |
| `calculadora/calc_icms.py` | ✅ | Cálculo para todos os municípios |
| `calculadora/calc_vaar.py` | ✅ | VAAR com verificação de condicionalidades |
| `calculadora/ranking.py` | ✅ | Rankings, comparações, histórico |
| `scraper/fnde_discovery.py` | ✅ | Descoberta automática de URLs por ano |
| `scraper/fnde_loader.py` | ✅ | Download + parsing PDF/CSV/XLSX receitas e inabilitados |
| `scraper/scheduler.py` | ✅ | Pipeline completo integrado com FNDE real |
| `scraper/downloader_inep.py` | ✅ | Microdados INEP |
| `scraper/geo_loader.py` | ✅ | Shapefile MG via API IBGE |
| `scraper/scraper_fjp.py` | ✅ | Selenium para portal FJP |
| `pages/1_Inicio.py` | ✅ | Visão geral e métricas |
| `pages/2_Calculadora.py` | ✅ | Calculadora interativa IE/VAAR |
| `pages/3_Mapa.py` | ✅ | Mapa choropleth MG |
| `pages/4_Consulta.py` | ✅ | Painel por município + status VAAR |
| `pages/5_Ranking.py` | ✅ | Ranking e comparação |
| `.github/workflows/coleta_dados.yml` | ✅ | GitHub Actions diário |

## Para adicionar um novo ano (ex: 2026)

1. Em `utils/config.py`, adicionar nas três seções:
```python
ANOS_COLETA = [2024, 2025, 2026]   # adicionar 2026

FNDE_PAGINAS_INDICE = {
    ...
    2026: "https://www.gov.br/fnde/.../2026-1",  # URL da página índice
}

TOTAL_ICMS_EDUCACAO_MG[2026] = 5_800_000_000.0   # atualizar após SEF-MG
TOTAL_VAAR_MG[2026]          = 1_800_000_000.0   # atualizar após FNDE
```

2. Executar: `python -m scraper.scheduler`

O sistema descobre automaticamente os PDFs do FNDE na nova página.

## Próximos passos sugeridos

- [ ] Testar o `fnde_loader.py` com os PDFs reais (2024 e 2025)
- [ ] Ajustar regex de parsing se o layout do PDF mudar entre anos
- [ ] Implementar página de administração no Streamlit para atualização manual
- [ ] Adicionar testes unitários para as fórmulas em `calculadora/`
- [ ] Publicar no Streamlit Cloud após validação local

## Como rodar localmente

```bash
cd fundeb_icms_mg
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Coleta completa (FJP + FNDE + INEP + GEO + consolidar)
python -m scraper.scheduler

# Ou módulo a módulo:
python -m scraper.fnde_loader       # Baixa PDFs do FNDE (discovery automático)
python -m scraper.scraper_fjp       # Índices FJP (requer Chrome)
python -m scraper.downloader_inep   # Microdados INEP
python -m scraper.geo_loader        # Shapefile MG

# Interface
streamlit run app.py
```
