"""Funcoes base para calculo de score do radar de oportunidades."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import yaml

SCORE_COMPONENTS = [
    "materialidade",
    "mandatabilidade",
    "timing",
    "qualidade_sinal",
    "aderencia",
    "competitividade",
]


def load_scoring_config(config_path: str | Path) -> dict[str, Any]:
    """Carrega as configuracoes de score a partir de um arquivo YAML."""
    with Path(config_path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def calculate_row_score(row: pd.Series, scoring_config: dict[str, Any]) -> dict[str, Any]:
    """Calcula o score de uma oportunidade.

    Placeholder: nesta fase, a funcao so devolve valores iniciais para
    manter o pipeline montado e facilitar a evolucao incremental.
    """
    _ = (row, scoring_config)
    score = {component: 0 for component in SCORE_COMPONENTS}
    score["score_total"] = 0
    score["prioridade_editorial"] = "base"
    return score


def score_opportunities(
    df: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> pd.DataFrame:
    """Adiciona score decomposto, score total e faixa editorial.

    A saida segue a estrutura esperada pela V1, mesmo com a logica ainda
    simplificada.
    """
    scored_df = df.copy()

    for component in SCORE_COMPONENTS:
        if component not in scored_df.columns:
            scored_df[component] = 0

    if scored_df.empty:
        scored_df["score_total"] = pd.Series(dtype="int64")
        scored_df["prioridade_editorial"] = pd.Series(dtype="object")
        return scored_df

    scores = scored_df.apply(
        lambda row: calculate_row_score(row, scoring_config),
        axis=1,
        result_type="expand",
    )

    for column in SCORE_COMPONENTS + ["score_total", "prioridade_editorial"]:
        scored_df[column] = scores[column]

    return scored_df
