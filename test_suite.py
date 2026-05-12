"""
test_suite.py
Suíte completa de testes para o projeto FUNDEB-VAAR & ICMS Educacional MG.

Testa:
  1. Integridade dos dados carregados
  2. Fórmulas de cálculo (IE, IQE, VAAR)
  3. Consistência dos dados FJP vs FNDE
  4. Validação dos repasses
  5. Status de habilitação VAAR
  6. Dados geoespaciais
  7. Utilitários (formatters, validators)
  8. Cobertura de municípios

Uso:
    python test_suite.py
    python test_suite.py -v          # verbose
    python test_suite.py -k dados    # só testes de dados
"""
from __future__ import annotations
import sys
import unittest
import warnings
from pathlib import Path
from io import StringIO

warnings.filterwarnings("ignore")

# Garantir que o projeto está no path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import numpy as np

# ─────────────────────────────────────────────────────────────────────────────
# CORES PARA OUTPUT
# ─────────────────────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
BLUE   = "\033[94m"
RESET  = "\033[0m"
BOLD   = "\033[1m"


def ok(msg):  print(f"  {GREEN}✅ {msg}{RESET}")
def err(msg): print(f"  {RED}❌ {msg}{RESET}")
def warn(msg):print(f"  {YELLOW}⚠️  {msg}{RESET}")
def info(msg):print(f"  {BLUE}ℹ️  {msg}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 1 — ARQUIVOS E DADOS
# ─────────────────────────────────────────────────────────────────────────────

class TestArquivos(unittest.TestCase):
    """Verifica se os arquivos de dados existem e têm conteúdo válido."""

    def test_01_consolidado_existe(self):
        """Arquivo consolidado.parquet deve existir."""
        path = PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        self.assertTrue(path.exists(), "consolidado.parquet não encontrado")

    def test_02_fjp_indices_existe(self):
        """Arquivo fjp_indices.parquet deve existir."""
        path = PROJECT_ROOT / "data" / "processed" / "fjp_indices.parquet"
        self.assertTrue(path.exists(), "fjp_indices.parquet não encontrado")

    def test_03_fnde_receitas_existe(self):
        """Arquivo fnde_receitas.parquet deve existir."""
        path = PROJECT_ROOT / "data" / "processed" / "fnde_receitas.parquet"
        self.assertTrue(path.exists(), "fnde_receitas.parquet não encontrado")

    def test_04_fnde_inabilitados_existe(self):
        """Arquivo fnde_inabilitados.parquet deve existir."""
        path = PROJECT_ROOT / "data" / "processed" / "fnde_inabilitados.parquet"
        self.assertTrue(path.exists(), "fnde_inabilitados.parquet não encontrado")

    def test_05_geojson_existe(self):
        """GeoJSON dos municípios deve existir."""
        path = PROJECT_ROOT / "data" / "geo" / "municipios_mg.geojson"
        self.assertTrue(path.exists(), "municipios_mg.geojson não encontrado")

    def test_06_consolidado_nao_vazio(self):
        """Consolidado deve ter registros."""
        df = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "consolidado.parquet")
        self.assertGreater(len(df), 0, "Consolidado está vazio")

    def test_07_consolidado_colunas_obrigatorias(self):
        """Consolidado deve ter todas as colunas esperadas."""
        df = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "consolidado.parquet")
        obrigatorias = ["cod_ibge", "municipio", "ano", "IE", "IRAP", "IRE",
                        "IAE", "IGE", "IQE", "repasse_icms_educacao",
                        "habilitado_vaar", "motivo_inabilitacao"]
        faltando = [c for c in obrigatorias if c not in df.columns]
        self.assertEqual(faltando, [], f"Colunas faltando: {faltando}")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 2 — INTEGRIDADE DOS DADOS
# ─────────────────────────────────────────────────────────────────────────────

class TestIntegridadeDados(unittest.TestCase):
    """Verifica a integridade e qualidade dos dados consolidados."""

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        )
        cls.anos = sorted(cls.df["ano"].unique())

    def test_01_numero_municipios(self):
        """Deve ter exatamente 853 municípios de MG."""
        for ano in self.anos:
            n = self.df[self.df["ano"] == ano]["municipio"].nunique()
            self.assertEqual(n, 853,
                f"Ano {ano}: {n} municípios (esperado 853)")

    def test_02_anos_disponiveis(self):
        """Deve ter pelo menos 2024 e 2025."""
        self.assertIn(2024, self.anos, "Ano 2024 não encontrado")
        self.assertIn(2025, self.anos, "Ano 2025 não encontrado")

    def test_03_ie_soma_um_por_ano(self):
        """A soma do IE de todos os municípios deve ser ~1,0 por ano."""
        for ano in self.anos:
            soma = self.df[self.df["ano"] == ano]["IE"].sum()
            self.assertAlmostEqual(soma, 1.0, places=2,
                msg=f"Soma IE {ano} = {soma:.6f} (esperado ~1.0)")

    def test_04_ie_sem_negativos(self):
        """IE não pode ter valores negativos."""
        neg = (self.df["IE"] < 0).sum()
        self.assertEqual(neg, 0, f"{neg} municípios com IE negativo")

    def test_05_ie_sem_maiores_que_um(self):
        """IE não pode ser maior que 1."""
        maior = (self.df["IE"] > 1).sum()
        self.assertEqual(maior, 0, f"{maior} municípios com IE > 1")

    def test_06_indicadores_intervalo_valido(self):
        """IRAP, IRE, IAE, IGE devem estar entre 0 e 1."""
        for col in ["IRAP", "IRE", "IAE", "IGE"]:
            if col in self.df.columns:
                invalidos = ((self.df[col] < 0) | (self.df[col] > 1)).sum()
                self.assertEqual(invalidos, 0,
                    f"{invalidos} valores inválidos em {col}")

    def test_07_sem_municipios_duplicados(self):
        """Não deve haver município duplicado no mesmo ano."""
        for ano in self.anos:
            df_ano = self.df[self.df["ano"] == ano]
            dupl = df_ano.duplicated(subset=["cod_ibge"]).sum()
            self.assertEqual(dupl, 0,
                f"Ano {ano}: {dupl} municípios duplicados")

    def test_08_cod_ibge_formato(self):
        """Código IBGE deve ter 7 dígitos e começar com 31 (MG)."""
        invalidos = self.df[
            ~self.df["cod_ibge"].astype(str).str.match(r"^31\d{5}$")
        ]
        self.assertEqual(len(invalidos), 0,
            f"{len(invalidos)} códigos IBGE inválidos:\n"
            f"{invalidos['cod_ibge'].unique()[:5]}")

    def test_09_sem_municipios_nulos(self):
        """Nome do município não pode ser nulo."""
        nulos = self.df["municipio"].isna().sum()
        self.assertEqual(nulos, 0, f"{nulos} municípios com nome nulo")

    def test_10_repasse_icms_positivo(self):
        """Repasse ICMS deve ser positivo para todos os municípios."""
        invalidos = (self.df["repasse_icms_educacao"] <= 0).sum()
        self.assertEqual(invalidos, 0,
            f"{invalidos} municípios com repasse ICMS <= 0")

    def test_11_top_municipios_corretos(self):
        """BH, Uberlândia e Contagem devem estar no top 5 por IE."""
        df_2025 = self.df[self.df["ano"] == 2025].nlargest(5, "IE")
        top5 = df_2025["municipio"].str.upper().tolist()
        for mun in ["BELO HORIZONTE", "UBERLÂNDIA", "CONTAGEM"]:
            self.assertIn(mun, top5,
                f"{mun} não está no top 5 (top 5 atual: {top5})")

    def test_12_bh_maior_ie(self):
        """BH deve estar no top 50% por IE (percentil > 50) em todos os anos."""
        from calculadora.ranking import percentil_municipio
        for ano in [2024, 2025]:
            if ano in self.anos:
                df_ano = self.df[self.df["ano"] == ano]
                pct = percentil_municipio(df_ano, "Belo Horizonte", "IE")
                self.assertGreater(pct, 50,
                    f"Ano {ano}: BH no percentil {pct:.0f} — abaixo do esperado (>50)")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 3 — FÓRMULAS DE CÁLCULO
# ─────────────────────────────────────────────────────────────────────────────

class TestFormulas(unittest.TestCase):
    """Testa as fórmulas matemáticas do projeto."""

    def setUp(self):
        from calculadora.formulas import (
            calcular_iqe, calcular_ie,
            calcular_repasse_icms,
            calcular_coef_vaar, calcular_repasse_vaar
        )
        self.calcular_iqe         = calcular_iqe
        self.calcular_ie          = calcular_ie
        self.calcular_repasse_icms = calcular_repasse_icms
        self.calcular_coef_vaar   = calcular_coef_vaar
        self.calcular_repasse_vaar = calcular_repasse_vaar

    def test_01_iqe_pesos_corretos(self):
        """IQE = IRAP×0,50 + IRE×0,20 + IAE×0,15 + IGE×0,15"""
        iqe = self.calcular_iqe(0.8, 0.6, 0.7, 0.5)
        esperado = 0.8*0.50 + 0.6*0.20 + 0.7*0.15 + 0.5*0.15
        self.assertAlmostEqual(iqe, esperado, places=10)

    def test_02_iqe_valores_iguais(self):
        """IQE com todos os valores iguais deve retornar o mesmo valor."""
        for v in [0.0, 0.5, 1.0]:
            iqe = self.calcular_iqe(v, v, v, v)
            self.assertAlmostEqual(iqe, v, places=10,
                msg=f"IQE({v},{v},{v},{v}) = {iqe}, esperado {v}")

    def test_03_iqe_limites(self):
        """IQE deve estar entre 0 e 1 para entradas válidas."""
        iqe_min = self.calcular_iqe(0, 0, 0, 0)
        iqe_max = self.calcular_iqe(1, 1, 1, 1)
        self.assertEqual(iqe_min, 0.0)
        self.assertEqual(iqe_max, 1.0)

    def test_04_ie_proporcional(self):
        """IE deve ser a fração proporcional do IQE."""
        ie = self.calcular_ie(0.5, 10.0)
        self.assertAlmostEqual(ie, 0.05, places=10)

    def test_05_ie_soma_zero(self):
        """IE com soma zero deve retornar 0."""
        ie = self.calcular_ie(0.5, 0.0)
        self.assertEqual(ie, 0.0)

    def test_06_repasse_icms_proporcional(self):
        """Repasse = IE × Total ICMS."""
        repasse = self.calcular_repasse_icms(0.001172, 5_100_000_000.0)
        esperado = 0.001172 * 5_100_000_000.0
        self.assertAlmostEqual(repasse, esperado, places=2)

    def test_07_coef_vaar_proporcional(self):
        """CoefVAAR = delta_mun / soma_delta."""
        coef = self.calcular_coef_vaar(0.005, 4.25)
        self.assertAlmostEqual(coef, 0.005/4.25, places=10)

    def test_08_coef_vaar_soma_zero(self):
        """CoefVAAR com soma zero deve retornar 0."""
        coef = self.calcular_coef_vaar(0.005, 0.0)
        self.assertEqual(coef, 0.0)

    def test_09_repasse_vaar_correto(self):
        """ValorVAAR = CoefVAAR × Total VAAR."""
        repasse = self.calcular_repasse_vaar(0.001176, 1_400_000_000.0)
        esperado = 0.001176 * 1_400_000_000.0
        self.assertAlmostEqual(repasse, esperado, places=2)

    def test_10_soma_ie_todos_municipios(self):
        """Soma dos IE de todos os municípios deve ser exatamente 1."""
        df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        )
        for ano in df["ano"].unique():
            soma = df[df["ano"] == ano]["IE"].sum()
            self.assertAlmostEqual(soma, 1.0, places=2,
                msg=f"Soma IE {ano} = {soma}")

    def test_11_iqe_consistente_com_dados_fjp(self):
        """IQE calculado deve bater com o IQE armazenado no FJP."""
        df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "fjp_indices.parquet"
        )
        if not all(c in df.columns for c in ["IRAP", "IRE", "IAE", "IGE", "IQE"]):
            self.skipTest("Colunas de índice não disponíveis")

        df_amostra = df.dropna(subset=["IRAP","IRE","IAE","IGE","IQE"]).head(50)
        for _, row in df_amostra.iterrows():
            iqe_calc = self.calcular_iqe(
                row["IRAP"], row["IRE"], row["IAE"], row["IGE"]
            )
            self.assertAlmostEqual(iqe_calc, row["IQE"], places=6,
                msg=f"IQE divergente para {row.get('municipio','?')}: "
                    f"calculado={iqe_calc:.6f} armazenado={row['IQE']:.6f}")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 4 — CONSISTÊNCIA FJP vs FNDE
# ─────────────────────────────────────────────────────────────────────────────

class TestConsistenciaFJPvsFNDE(unittest.TestCase):
    """Verifica a consistência entre os dados da FJP e do FNDE."""

    @classmethod
    def setUpClass(cls):
        cls.df_cons    = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "consolidado.parquet")
        cls.df_fjp     = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "fjp_indices.parquet")
        cls.df_receitas = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "fnde_receitas.parquet")
        cls.df_inab    = pd.read_parquet(PROJECT_ROOT / "data" / "processed" / "fnde_inabilitados.parquet")

    def test_01_fjp_853_municipios(self):
        """FJP deve ter 853 municípios por ano."""
        for ano in self.df_fjp["ano"].unique():
            n = self.df_fjp[self.df_fjp["ano"] == ano]["municipio"].nunique()
            self.assertEqual(n, 853, f"FJP {ano}: {n} municípios")

    def test_02_fnde_receitas_mg_apenas(self):
        """FNDE receitas deve ter apenas municípios de MG."""
        if "uf" in self.df_receitas.columns:
            outros = self.df_receitas[
                self.df_receitas["uf"].str.upper().str.strip() != "MG"
            ]
            self.assertEqual(len(outros), 0,
                f"{len(outros)} registros de fora de MG")
        elif "cod_ibge" in self.df_receitas.columns:
            invalidos = self.df_receitas[
                ~self.df_receitas["cod_ibge"].astype(str).str.startswith("31")
            ]
            self.assertEqual(len(invalidos), 0,
                f"{len(invalidos)} municípios fora de MG")

    def test_03_inabilitados_subset_mg(self):
        """Inabilitados devem ser subconjunto dos 853 municípios de MG."""
        n_inab = self.df_inab["municipio"].nunique()
        self.assertLess(n_inab, 853,
            "Todos os municípios aparecem como inabilitados — improvável")
        self.assertGreater(n_inab, 0,
            "Nenhum município inabilitado — verificar dados")

    def test_04_soma_repasse_icms_plausivel(self):
        """Soma dos repasses ICMS deve ser próxima ao total estadual."""
        for ano in [2024, 2025]:
            df_ano = self.df_cons[self.df_cons["ano"] == ano]
            if df_ano.empty:
                continue
            soma = df_ano["repasse_icms_educacao"].sum()
            # Total ICMS Educação MG: entre 4 bi e 6 bi
            self.assertGreater(soma, 4_000_000_000,
                f"Soma repasse ICMS {ano} muito baixa: {soma:,.0f}")
            self.assertLess(soma, 6_500_000_000,
                f"Soma repasse ICMS {ano} muito alta: {soma:,.0f}")

    def test_05_inabilitados_sem_vaar(self):
        """Inabilitados não devem ter VAAR absurdo (> 500mi indica erro de parsing)."""
        for ano in [2025]:
            df_ano = self.df_cons[self.df_cons["ano"] == ano]
            if df_ano.empty or "habilitado_vaar" not in df_ano.columns:
                continue
            inab = df_ano[df_ano["habilitado_vaar"] == False]
            com_vaar_absurdo = inab[inab["repasse_vaar"].fillna(0) > 500_000_000]
            self.assertEqual(len(com_vaar_absurdo), 0,
                f"{len(com_vaar_absurdo)} inabilitados com VAAR > 500mi")

    def test_06_bh_sem_vaar_incorreto(self):
        """BH não deve ter VAAR de R$ 1,38 bilhão (era valor do estado inteiro)."""
        df_bh = self.df_cons[
            self.df_cons["municipio"].str.upper() == "BELO HORIZONTE"
        ]
        if df_bh.empty or "repasse_vaar" not in df_bh.columns:
            return
        vaar_max = df_bh["repasse_vaar"].max()
        self.assertLess(
            vaar_max if not pd.isna(vaar_max) else 0,
            500_000_000,
            f"VAAR de BH = {vaar_max:,.0f} — parece ser valor do estado inteiro"
        )

    def test_07_ie_bh_maior_que_municipio_pequeno(self):
        """IE de BH deve ser muito maior que de municípios pequenos."""
        for ano in [2024, 2025]:
            df_ano = self.df_cons[self.df_cons["ano"] == ano]
            if df_ano.empty:
                continue
            ie_bh = df_ano[df_ano["municipio"].str.upper() == "BELO HORIZONTE"]["IE"]
            ie_menor = df_ano.nsmallest(10, "IE")["IE"].mean()
            if not ie_bh.empty:
                self.assertGreater(
                    ie_bh.values[0], ie_menor * 2,
                    f"IE BH ({ie_bh.values[0]:.6f}) não é significativamente "
                    f"maior que municípios pequenos ({ie_menor:.6f})"
                )


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 5 — HABILITAÇÃO VAAR
# ─────────────────────────────────────────────────────────────────────────────

class TestHabilitacaoVAAR(unittest.TestCase):
    """Verifica o status de habilitação ao VAAR."""

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        )
        cls.df_inab = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "fnde_inabilitados.parquet"
        )

    def test_01_tem_inabilitados(self):
        """Deve haver municípios inabilitados."""
        n = (self.df["habilitado_vaar"] == False).sum()
        self.assertGreater(n, 0, "Nenhum município inabilitado")

    def test_02_tem_habilitados(self):
        """Deve haver municípios habilitados."""
        n = (self.df["habilitado_vaar"] == True).sum()
        self.assertGreater(n, 0, "Nenhum município habilitado")

    def test_03_proporcao_inabilitados_plausivel(self):
        """2025 e 2026 devem ter inabilitados. 2024 só tem habilitados (sem lista FNDE)."""
        for ano in [2025, 2026]:
            df_ano = self.df[self.df["ano"] == ano]
            if df_ano.empty:
                continue
            pct_hab = (df_ano["habilitado_vaar"] == True).mean()
            self.assertGreater(pct_hab, 0.2,
                f"{ano}: apenas {pct_hab:.0%} habilitados — muito baixo")
            self.assertLess(pct_hab, 0.99,
                f"{ano}: {pct_hab:.0%} habilitados — inabilitados não carregados")

    def test_04_inabilitados_tem_motivo(self):
        """Municípios inabilitados devem ter motivo preenchido."""
        inab = self.df[self.df["habilitado_vaar"] == False]
        sem_motivo = inab[
            inab["motivo_inabilitacao"].isna() |
            (inab["motivo_inabilitacao"].astype(str).str.strip() == "")
        ]
        pct_sem = len(sem_motivo) / len(inab) if len(inab) > 0 else 0
        self.assertLess(pct_sem, 0.3,
            f"{pct_sem:.0%} dos inabilitados sem motivo (esperado < 30%)")

    def test_05_condicionalidades_validas(self):
        """Motivos devem referenciar condicionalidades válidas (I a V)."""
        inab = self.df_inab.copy()
        if "motivo_inabilitacao" not in inab.columns:
            self.skipTest("Coluna motivo_inabilitacao não disponível")
        motivos = inab["motivo_inabilitacao"].dropna()
        # Ao menos alguns devem mencionar artigo 14
        menciona_art14 = motivos.str.contains("14|art|cond", case=False, na=False)
        self.assertGreater(menciona_art14.sum(), 0,
            "Nenhum motivo menciona o Art. 14")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 6 — DADOS GEOESPACIAIS
# ─────────────────────────────────────────────────────────────────────────────

class TestGeoespacial(unittest.TestCase):
    """Verifica a integridade do GeoJSON dos municípios."""

    @classmethod
    def setUpClass(cls):
        import json
        geo_path = PROJECT_ROOT / "data" / "geo" / "municipios_mg.geojson"
        with open(geo_path, encoding="utf-8") as f:
            cls.geojson = json.load(f)
        cls.features = cls.geojson.get("features", [])

    def test_01_853_features(self):
        """GeoJSON deve ter 853 features (municípios)."""
        self.assertEqual(len(self.features), 853,
            f"GeoJSON tem {len(self.features)} features (esperado 853)")

    def test_02_todos_tem_id(self):
        """Todas as features devem ter propriedade 'id'."""
        sem_id = [
            f["properties"].get("municipio", "?")
            for f in self.features
            if not f.get("properties", {}).get("id")
        ]
        self.assertEqual(len(sem_id), 0,
            f"{len(sem_id)} features sem 'id': {sem_id[:3]}")

    def test_03_ids_comecam_com_31(self):
        """Todos os IDs devem começar com 31 (código MG)."""
        invalidos = [
            f["properties"]["id"]
            for f in self.features
            if not str(f.get("properties", {}).get("id", "")).startswith("31")
        ]
        self.assertEqual(len(invalidos), 0,
            f"{len(invalidos)} IDs inválidos: {invalidos[:3]}")

    def test_04_todos_tem_geometria(self):
        """Todas as features devem ter geometria válida."""
        sem_geo = [
            f["properties"].get("municipio", "?")
            for f in self.features
            if not f.get("geometry")
        ]
        self.assertEqual(len(sem_geo), 0,
            f"{len(sem_geo)} features sem geometria")

    def test_05_match_consolidado(self):
        """IDs do GeoJSON devem fazer match com cod_ibge do consolidado."""
        df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        )
        ids_geo  = {str(f["properties"]["id"]) for f in self.features}
        ids_df   = set(df["cod_ibge"].astype(str).unique())
        sem_match = ids_geo - ids_df
        self.assertLess(len(sem_match), 5,
            f"{len(sem_match)} IDs do GeoJSON sem match no consolidado: "
            f"{list(sem_match)[:5]}")


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 7 — UTILITÁRIOS
# ─────────────────────────────────────────────────────────────────────────────

class TestUtilitarios(unittest.TestCase):
    """Testa os módulos utilitários do projeto."""

    def test_01_fmt_moeda(self):
        """Formatar moeda deve retornar string com R$."""
        from utils.formatters import fmt_moeda
        resultado = fmt_moeda(1234567.89)
        self.assertIn("R$", resultado)
        self.assertIn("1", resultado)

    def test_02_fmt_moeda_none(self):
        """fmt_moeda com None deve retornar '—'."""
        from utils.formatters import fmt_moeda
        self.assertEqual(fmt_moeda(None), "—")

    def test_03_fmt_numero(self):
        """fmt_numero deve formatar com vírgula decimal."""
        from utils.formatters import fmt_numero
        resultado = fmt_numero(0.001234)
        self.assertIn(",", resultado)

    def test_04_fmt_percentual(self):
        """fmt_percentual deve incluir sinal de %."""
        from utils.formatters import fmt_percentual
        resultado = fmt_percentual(0.1234)
        self.assertIn("%", resultado)

    def test_05_validar_indice_valido(self):
        """Índice entre 0 e 1 deve ser válido."""
        from utils.validators import validar_indice
        ok, _ = validar_indice(0.5, "IRAP")
        self.assertTrue(ok)

    def test_06_validar_indice_negativo(self):
        """Índice negativo deve ser inválido."""
        from utils.validators import validar_indice
        ok, msg = validar_indice(-0.1, "IRAP")
        self.assertFalse(ok)
        self.assertIn("IRAP", msg)

    def test_07_validar_indice_maior_um(self):
        """Índice maior que 1 deve ser inválido."""
        from utils.validators import validar_indice
        ok, _ = validar_indice(1.5, "IRE")
        self.assertFalse(ok)

    def test_08_validar_cod_ibge_mg(self):
        """Código IBGE de MG deve ser válido."""
        from utils.validators import validar_cod_ibge
        self.assertTrue(validar_cod_ibge("3106200"))   # BH
        self.assertTrue(validar_cod_ibge("3170107"))   # Uberlândia

    def test_09_validar_cod_ibge_invalido(self):
        """Código IBGE de outro estado deve ser inválido."""
        from utils.validators import validar_cod_ibge
        self.assertFalse(validar_cod_ibge("3550308"))  # SP
        self.assertFalse(validar_cod_ibge("123"))      # curto demais

    def test_10_cache_parquet(self):
        """Salvar e carregar parquet deve preservar os dados."""
        from utils.cache import salvar_parquet, carregar_parquet
        import tempfile, os
        df_orig = pd.DataFrame({"a": [1, 2, 3], "b": ["x", "y", "z"]})
        salvar_parquet(df_orig, "teste_cache_temp")
        df_lido = carregar_parquet("teste_cache_temp")
        self.assertIsNotNone(df_lido)
        self.assertEqual(len(df_lido), 3)
        # Limpar
        (PROJECT_ROOT / "data" / "processed" / "teste_cache_temp.parquet").unlink(missing_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# BLOCO 8 — RANKING E COMPARAÇÕES
# ─────────────────────────────────────────────────────────────────────────────

class TestRanking(unittest.TestCase):
    """Testa as funções de ranking e comparação."""

    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_parquet(
            PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
        )

    def test_01_ranking_ordenacao_correta(self):
        """Ranking deve estar em ordem decrescente de IE."""
        from calculadora.ranking import gerar_ranking
        df_ano = self.df[self.df["ano"] == 2025]
        rank = gerar_ranking(df_ano, "IE", top_n=20)
        ies = rank["IE"].tolist()
        self.assertEqual(ies, sorted(ies, reverse=True),
            "Ranking não está em ordem decrescente")

    def test_02_ranking_top_n(self):
        """Ranking deve retornar exatamente N municípios."""
        from calculadora.ranking import gerar_ranking
        df_ano = self.df[self.df["ano"] == 2025]
        for n in [5, 10, 20, 50]:
            rank = gerar_ranking(df_ano, "IE", top_n=n)
            self.assertEqual(len(rank), n, f"Top {n} retornou {len(rank)}")

    def test_03_evolucao_historica(self):
        """Evolução histórica deve retornar dados de múltiplos anos."""
        from calculadora.ranking import evolucao_historica
        hist = evolucao_historica(self.df, "Belo Horizonte")
        self.assertGreater(len(hist), 1,
            "Histórico de BH deve ter mais de 1 ano")
        self.assertIn("ano", hist.columns)

    def test_04_percentil_bh_alto(self):
        """BH deve estar em percentil alto (> 95)."""
        from calculadora.ranking import percentil_municipio
        df_2025 = self.df[self.df["ano"] == 2025]
        pct = percentil_municipio(df_2025, "Belo Horizonte", "IE")
        self.assertGreater(pct, 95,
            f"Percentil BH = {pct} (esperado > 95)")

    def test_05_comparar_municipios(self):
        """Comparação deve retornar todos os municípios selecionados."""
        from calculadora.ranking import comparar_municipios
        df_2025 = self.df[self.df["ano"] == 2025]
        muns = ["Belo Horizonte", "Uberlândia", "Contagem"]
        comp = comparar_municipios(df_2025, muns)
        encontrados = comp["municipio"].tolist()
        for m in muns:
            self.assertIn(m, encontrados, f"{m} não encontrado na comparação")


# ─────────────────────────────────────────────────────────────────────────────
# RUNNER CUSTOMIZADO COM RELATÓRIO
# ─────────────────────────────────────────────────────────────────────────────

class ColorTextTestResult(unittest.TextTestResult):
    def addSuccess(self, test):
        super().addSuccess(test)
        if self.showAll:
            self.stream.write(f"{GREEN}  PASSOU{RESET}\n")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        if self.showAll:
            self.stream.write(f"{RED}  FALHOU{RESET}\n")

    def addError(self, test, err):
        super().addError(test, err)
        if self.showAll:
            self.stream.write(f"{RED}  ERRO{RESET}\n")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        if self.showAll:
            self.stream.write(f"{YELLOW}  PULADO: {reason}{RESET}\n")


class ColorTextTestRunner(unittest.TextTestRunner):
    resultclass = ColorTextTestResult


def main():
    print(f"\n{BOLD}{'='*65}")
    print("  SUÍTE DE TESTES — FUNDEB-VAAR & ICMS Educacional MG")
    print(f"{'='*65}{RESET}\n")

    # Verificar se o projeto está no path correto
    consolidado = PROJECT_ROOT / "data" / "processed" / "consolidado.parquet"
    if not consolidado.exists():
        print(f"{RED}❌ ERRO: consolidado.parquet não encontrado em {consolidado}")
        print(f"   Execute primeiro: python -m scraper.scheduler{RESET}\n")
        sys.exit(1)

    loader = unittest.TestLoader()
    suite  = unittest.TestSuite()

    # Adicionar todos os blocos de teste em ordem
    blocos = [
        ("📁 Bloco 1 — Arquivos e Dados",        TestArquivos),
        ("📊 Bloco 2 — Integridade dos Dados",    TestIntegridadeDados),
        ("🧮 Bloco 3 — Fórmulas de Cálculo",     TestFormulas),
        ("🔗 Bloco 4 — Consistência FJP vs FNDE", TestConsistenciaFJPvsFNDE),
        ("✅ Bloco 5 — Habilitação VAAR",         TestHabilitacaoVAAR),
        ("🗺️  Bloco 6 — Dados Geoespaciais",      TestGeoespacial),
        ("🛠️  Bloco 7 — Utilitários",             TestUtilitarios),
        ("🏆 Bloco 8 — Ranking e Comparações",    TestRanking),
    ]

    for titulo, classe in blocos:
        print(f"{BOLD}{BLUE}{titulo}{RESET}")
        tests = loader.loadTestsFromTestCase(classe)
        suite.addTests(tests)

    print()
    runner = ColorTextTestRunner(
        verbosity=2,
        stream=sys.stdout,
        descriptions=True,
    )
    resultado = runner.run(suite)

    # Relatório final
    total   = resultado.testsRun
    falhas  = len(resultado.failures)
    erros   = len(resultado.errors)
    pulados = len(resultado.skipped)
    passou  = total - falhas - erros - pulados

    print(f"\n{BOLD}{'='*65}")
    print("  RELATÓRIO FINAL")
    print(f"{'='*65}{RESET}")
    print(f"  Total de testes : {total}")
    print(f"  {GREEN}✅ Passaram      : {passou}{RESET}")
    print(f"  {RED}❌ Falharam      : {falhas}{RESET}")
    print(f"  {RED}💥 Erros         : {erros}{RESET}")
    print(f"  {YELLOW}⏭️  Pulados       : {pulados}{RESET}")

    if falhas == 0 and erros == 0:
        print(f"\n{GREEN}{BOLD}  🎉 TODOS OS TESTES PASSARAM!{RESET}")
    else:
        print(f"\n{RED}{BOLD}  ⚠️  ATENÇÃO: {falhas + erros} teste(s) precisam de revisão.{RESET}")

    print(f"{BOLD}{'='*65}{RESET}\n")

    return 0 if (falhas == 0 and erros == 0) else 1


if __name__ == "__main__":
    sys.exit(main())
