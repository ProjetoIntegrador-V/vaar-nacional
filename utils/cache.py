"""
utils/cache.py
Funções de cache e persistência local dos dados coletados.
"""
from __future__ import annotations
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
from loguru import logger
from utils.config import DATA_RAW, DATA_PROCESSED, DATA_GEO, CACHE_TTL_H


def cache_valido(caminho: Path, ttl_horas: int = CACHE_TTL_H) -> bool:
    """Retorna True se o arquivo existe e foi modificado dentro do TTL."""
    if not caminho.exists():
        return False
    idade = datetime.now() - datetime.fromtimestamp(caminho.stat().st_mtime)
    return idade < timedelta(hours=ttl_horas)


def salvar_parquet(df: pd.DataFrame, nome: str, pasta: Path = DATA_PROCESSED) -> Path:
    """Salva DataFrame como Parquet comprimido."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{nome}.parquet"
    df.to_parquet(caminho, index=False, compression="snappy")
    logger.info(f"Salvo: {caminho} ({len(df)} linhas)")
    return caminho


def carregar_parquet(nome: str, pasta: Path = DATA_PROCESSED) -> pd.DataFrame | None:
    """Carrega DataFrame do Parquet se existir."""
    caminho = pasta / f"{nome}.parquet"
    if not caminho.exists():
        logger.warning(f"Arquivo não encontrado: {caminho}")
        return None
    df = pd.read_parquet(caminho)
    logger.info(f"Carregado: {caminho} ({len(df)} linhas)")
    return df


def salvar_json(dados: dict | list, nome: str, pasta: Path = DATA_RAW) -> Path:
    """Salva dados como JSON."""
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"{nome}.json"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)
    logger.info(f"Salvo: {caminho}")
    return caminho


def carregar_json(nome: str, pasta: Path = DATA_RAW) -> dict | list | None:
    """Carrega JSON se existir."""
    caminho = pasta / f"{nome}.json"
    if not caminho.exists():
        return None
    with open(caminho, "r", encoding="utf-8") as f:
        return json.load(f)


def salvar_geojson(geojson: dict, nome: str = "municipios_mg") -> Path:
    """Salva GeoJSON dos municípios de MG."""
    DATA_GEO.mkdir(parents=True, exist_ok=True)
    caminho = DATA_GEO / f"{nome}.geojson"
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(geojson, f, ensure_ascii=False)
    logger.info(f"GeoJSON salvo: {caminho}")
    return caminho
