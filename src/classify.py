"""Funcoes base para classificacao das oportunidades do radar."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml


def load_taxonomy_config(config_path: str | Path) -> dict[str, Any]:
    """Carrega a taxonomia de classificacao a partir de um arquivo YAML."""
    with Path(config_path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def classify_row(row: pd.Series, taxonomy: dict[str, Any]) -> dict[str, str]:
    """Classifica uma linha individual.

    Placeholder: nesta etapa, a funcao apenas devolve marcadores padrao.
    Em uma versao futura, ela deve aplicar regras por palavras-chave,
    setor, contexto da noticia e sinais estruturados do input.
    """
    _ = (row, taxonomy)
    return {
        "produto_trilha": "a_validar_manual",
        "subtipo": "a_definir",
    }


def classify_opportunities(
    df: pd.DataFrame,
    taxonomy: dict[str, Any],
) -> pd.DataFrame:
    """Adiciona colunas de classificacao ao DataFrame de oportunidades.

    A funcao preserva o conteudo original e cria as colunas esperadas pela
    V1 do pipeline, mesmo antes da implementacao final das regras.
    """
    classified_df = df.copy()

    if classified_df.empty:
        classified_df["produto_trilha"] = pd.Series(dtype="object")
        classified_df["subtipo"] = pd.Series(dtype="object")
        return classified_df

    classifications = classified_df.apply(
        lambda row: classify_row(row, taxonomy),
        axis=1,
        result_type="expand",
    )

    classified_df["produto_trilha"] = classifications["produto_trilha"]
    classified_df["subtipo"] = classifications["subtipo"]
    return classified_df
