# 🎓 FUNDEB-VAAR & ICMS Educacional — Minas Gerais

Calculadora e mapa interativo de indicadores educacionais municipais de MG.

## Funcionalidades

| Página | Descrição |
|---|---|
| 🧮 Calculadora | Calcula IE, IQE e estimativa de repasse para qualquer município |
| 🗺️ Mapa | Choropleth interativo dos 853 municípios por indicador |
| 🔍 Consulta | Painel detalhado com todos os índices de um município |
| 🏆 Ranking | Comparação e ranking entre municípios |

## Legislação base

- **EC 108/2020** — Fundamentação constitucional do ICMS Educacional
- **Lei 14.113/2020** — Novo FUNDEB, complementação VAAR
- **Lei 18.030/2009** — Lei Robin Hood (ICMS Municipal MG)
- **Lei 24.431/2023** — ICMS Educacional MG (10% do ICMS + Índice IE)

## Fórmulas implementadas

```
IQE = IRAP×0,50 + IRE×0,20 + IAE×0,15 + IGE×0,15
IE(i) = IQE(i) / Σ IQE(i)
CoefVAAR = ΔIndicador_mun / Σ ΔIndicador_rede
ValorVAAR = CoefVAAR × Total_VAAR_UF
```

## Fontes de dados

| Fonte | Dados | Método |
|---|---|---|
| FJP (robin-hood.fjp.mg.gov.br) | IE, IRAP, IRE, IAE, IGE | Selenium |
| FNDE (fnde.gov.br) | Repasse VAAR por município | Download XLS |
| INEP (inep.gov.br/microdados) | SAEB, Censo Escolar | Download ZIP/CSV |
| IBGE (ibge.gov.br/api/v1) | Shapefile, população | API REST |

## Instalação

```bash
git clone https://github.com/henriqueribeiro19/fundeb-icms-mg.git
cd fundeb-icms-mg
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py
```

## Estrutura do projeto

```
fundeb_icms_mg/
├── app.py                    # Ponto de entrada Streamlit
├── requirements.txt
├── pages/
│   ├── 1_Inicio.py
│   ├── 2_Calculadora.py
│   ├── 3_Mapa.py
│   ├── 4_Consulta.py
│   └── 5_Ranking.py
├── scraper/
│   ├── scraper_fjp.py        # Selenium — portal FJP
│   ├── downloader_fnde.py    # Download planilhas FNDE
│   ├── downloader_inep.py    # Download microdados INEP
│   ├── geo_loader.py         # API IBGE — shapefile MG
│   └── scheduler.py          # Consolida todos os dados
├── calculadora/
│   ├── formulas.py           # Fórmulas puras (IE, IQE, VAAR)
│   ├── calc_icms.py          # ICMS Educacional por município
│   ├── calc_vaar.py          # VAAR por município
│   └── ranking.py            # Rankings e comparações
├── utils/
│   ├── config.py             # URLs, constantes, pesos
│   ├── cache.py              # Persistência local (Parquet/JSON)
│   ├── formatters.py         # Formatação de moeda, índices
│   └── validators.py         # Validação de entradas
├── data/
│   ├── raw/                  # Dados brutos coletados (gitignored)
│   ├── processed/            # Parquet consolidado (versionado)
│   └── geo/                  # GeoJSON municípios MG (versionado)
├── .streamlit/
│   ├── config.toml           # Tema e configurações
│   └── secrets.toml          # Credenciais (gitignored)
└── .github/workflows/
    └── coleta_dados.yml      # Scraping automático diário
```
