"""Funcoes base para organizar a fila editorial e gerar o memo semanal."""

from __future__ import annotations

from typing import Iterable

import pandas as pd


def build_memo_queue(df: pd.DataFrame) -> pd.DataFrame:
    """Prepara uma fila editorial simples a partir do DataFrame scored.

    Placeholder: por enquanto, a funcao apenas ordena pelo score total
    quando a coluna estiver disponivel.
    """
    queue_df = df.copy()

    if "score_total" in queue_df.columns:
        queue_df = queue_df.sort_values("score_total", ascending=False)

    return queue_df.reset_index(drop=True)


def build_weekly_memo_markdown(df: pd.DataFrame) -> str:
    """Gera um markdown inicial para o memo semanal.

    A estrutura foi mantida propositalmente enxuta para facilitar futuros
    refinamentos editoriais.
    """
    highlights = _format_highlights(df.head(5).to_dict(orient="records"))
    return "\n".join(
        [
            "# Memo Semanal IB",
            "",
            "## Destaques",
            highlights or "- Sem oportunidades priorizadas nesta versao inicial.",
            "",
            "## Observacoes",
            "- Estrutura placeholder pronta para futura geracao automatica.",
        ]
    )


def _format_highlights(rows: Iterable[dict]) -> str:
    """Formata os principais itens do memo em bullets simples."""
    lines: list[str] = []

    for index, row in enumerate(rows, start=1):
        titulo = row.get("titulo") or row.get("empresa") or f"Oportunidade {index}"
        score_total = row.get("score_total", "n/d")
        trilha = row.get("produto_trilha", "n/d")
        lines.append(f"- {titulo} | score {score_total} | trilha {trilha}")

    return "\n".join(lines)
