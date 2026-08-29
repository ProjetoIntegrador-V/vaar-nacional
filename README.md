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

## Pré Requisitos
| IDE Sugerida: VsCode |
| Python 3.13 |
| Git |


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
# Projeto Integrador V 
# VAAR Nacional

Projeto desenvolvido no 6º semestre do curso de Ciência de Dados da FATEC Cotia, com foco no desenvolvimento de uma solução para o indicador VAAR (Valor Aluno Ano por Resultados) em âmbito nacional.

O Grupo 01 é responsável pelo nível nacional e trabalhará exclusivamente com o VAAR, utilizando bases de dados governamentais para realizar a coleta, processamento e reconstrução dos indicadores que compõem o cálculo. O projeto parte de uma calculadora-base previamente desenvolvida, que já possui mecanismos de web scraping e processamento dos dados, buscando ampliar, refinar e validar sua implementação para contemplar todos os municípios brasileiros.

## Objetivos

* Identificar e documentar as legislações relacionadas ao VAAR;
* Mapear as bases de dados governamentais utilizadas na composição dos indicadores;
* Armazenar e organizar a documentação e as legislações utilizadas;
* Automatizar a raspagem e coleta dos dados necessários;
* Processar e consolidar os dados provenientes das diferentes fontes;
* Reproduzir e refinar as fórmulas e indicadores que compõem o VAAR;
* Validar os resultados obtidos a partir das bases oficiais;
* Desenvolver uma solução capaz de apresentar os indicadores para os municípios brasileiros;
* Integrar posteriormente a solução à plataforma geral do Projeto Integrador;
* Apoiar a implementação de um sistema baseado em LLM para consulta à legislação do VAAR.

## Escopo do Grupo 01

O projeto terá abrangência nacional, considerando os municípios brasileiros. Diferentemente dos grupos responsáveis pelos modelos estaduais de ICMS Educacional, o Grupo 01 trabalhará exclusivamente com o VAAR e suas respectivas fontes, regras, indicadores e legislação.

A calculadora-base fornecida pelo professor já possui parte significativa da estrutura de raspagem e processamento dos dados. O trabalho do grupo será partir dessa implementação, retirar os componentes relacionados ao ICMS, ampliar o escopo de Minas Gerais para o Brasil e refinar a reconstrução dos indicadores e respectivas fórmulas.

Um dos objetivos centrais é realizar um levantamento das bases governamentais necessárias e verificar se é possível reconstruir o indicador a partir dos dados disponíveis, automatizando o processo de coleta e processamento.

## Legislação e LLM

Toda a legislação relacionada ao VAAR deverá ser levantada, armazenada e documentada. Esse material será utilizado posteriormente em conjunto com o desenvolvimento de um modelo de linguagem (LLM), permitindo consultas sobre a legislação e suas regras.

O projeto também busca verificar a relação entre a legislação, as fórmulas utilizadas e os dados necessários para a composição dos indicadores.

## Tecnologias e componentes

* Python
* Web scraping
* Processamento e consolidação de dados
* Bases de dados governamentais
* Automação de coleta de dados
* LLM / consulta à legislação
* Plataforma integrada

## Grupo 01 — VAAR Nacional

Emerson Silva
Flavio Vieira
Gustavo Tiedra
Nicolas Alves
Ricardo Henrique
William Borelli
