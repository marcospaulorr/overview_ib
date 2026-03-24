"""Funcoes base para classificacao heuristica das oportunidades do radar."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

TEXT_COLUMN_HINTS = {
    "assunto",
    "company",
    "companhia",
    "company_name",
    "conteudo",
    "deal",
    "descricao",
    "descricao_curta",
    "descricao_longa",
    "detalhes",
    "emissor",
    "empresa",
    "headline",
    "issuer",
    "nota",
    "noticia",
    "observacoes",
    "resumo",
    "segmento",
    "setor",
    "summary",
    "texto",
    "title",
    "titulo",
}

SOURCE_COLUMN_HINTS = {
    "canal",
    "fonte",
    "origem",
    "origem_sinal",
    "publisher",
    "source",
    "source_name",
    "veiculo",
}

OUTPUT_COLUMN_HINTS = {
    "produto_trilha",
    "subtipo",
}


def load_taxonomy_config(config_path: str | Path) -> dict[str, Any]:
    """Carrega a taxonomia de classificacao a partir de um arquivo YAML."""
    with Path(config_path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparacoes heuristicas simples.

    A normalizacao remove acentos, converte para minusculas, substitui
    pontuacao por espacos e compacta espacos repetidos.
    """
    if value is None:
        return ""

    try:
        if pd.isna(value):
            return ""
    except TypeError:
        pass

    text = str(value).strip().lower()
    if not text:
        return ""

    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def classify_product_track(row: pd.Series, taxonomy: dict[str, Any]) -> str:
    """Classifica a trilha principal usando palavras-chave e hints de fonte.

    O metodo calcula um score simples por trilha e escolhe a mais aderente.
    Para evitar classificacoes fracas demais, a fonte so desempata ou ajuda
    quando ja ha algum sinal textual ou quando ha varias evidencias de fonte.
    """
    defaults = taxonomy.get("defaults", {})
    default_product = defaults.get("produto_trilha", "a_validar_manual")
    text_context = _build_text_context(row)
    source_context = _build_source_context(row)

    best_product = default_product
    best_score = 0
    best_signal_strength = 0

    for product_key, product_config in taxonomy.get("produtos", {}).items():
        product_name = str(product_config.get("nome", product_key))
        keyword_hits = _count_matches(text_context, product_config.get("palavras_chave", []))
        alias_hits = _count_matches(text_context, product_config.get("aliases", []))
        source_hits = _count_matches(source_context, product_config.get("fontes_chave", []))
        subtype_hits = _count_subtype_signal_hits(text_context, source_context, product_config)

        signal_strength = keyword_hits + alias_hits + subtype_hits
        score = (keyword_hits * 3) + (alias_hits * 2) + (subtype_hits * 2) + source_hits

        has_minimum_signal = signal_strength > 0 or source_hits >= 2
        if not has_minimum_signal:
            continue

        if score > best_score or (score == best_score and signal_strength > best_signal_strength):
            best_product = product_name
            best_score = score
            best_signal_strength = signal_strength

    return best_product


def classify_subtype(
    row: pd.Series,
    taxonomy: dict[str, Any],
    product_track: str | None = None,
) -> str:
    """Classifica o subtipo dentro da trilha principal ja definida."""
    defaults = taxonomy.get("defaults", {})
    default_subtype = defaults.get("subtipo", "a_definir")
    selected_product = product_track or classify_product_track(row, taxonomy)

    product_config = _find_product_config(taxonomy, selected_product)
    if not product_config:
        return default_subtype

    text_context = _build_text_context(row)
    source_context = _build_source_context(row)

    best_subtype = default_subtype
    best_score = 0

    for subtype_name, subtype_config in _iter_subtype_rules(product_config):
        keyword_hits = _count_matches(text_context, subtype_config.get("palavras_chave", []))
        alias_hits = _count_matches(text_context, subtype_config.get("aliases", []))
        source_hits = _count_matches(source_context, subtype_config.get("fontes_chave", []))
        score = (keyword_hits * 3) + (alias_hits * 2) + source_hits

        if score > best_score:
            best_subtype = subtype_name
            best_score = score

    return best_subtype if best_score > 0 else default_subtype


def classify_row(row: pd.Series, taxonomy: dict[str, Any]) -> dict[str, str]:
    """Classifica uma linha individual em trilha principal e subtipo."""
    product_track = classify_product_track(row, taxonomy)
    subtype = classify_subtype(row, taxonomy, product_track=product_track)
    return {
        "produto_trilha": product_track,
        "subtipo": subtype,
    }


def classify_opportunities(
    df: pd.DataFrame,
    taxonomy: dict[str, Any],
) -> pd.DataFrame:
    """Adiciona colunas de classificacao ao DataFrame de oportunidades."""
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


def _build_text_context(row: pd.Series) -> str:
    """Monta o contexto textual principal a partir das colunas mais provaveis."""
    explicit_text = _join_row_values(row, include_columns=TEXT_COLUMN_HINTS)
    if explicit_text:
        return explicit_text

    return _join_row_values(
        row,
        exclude_columns=SOURCE_COLUMN_HINTS | OUTPUT_COLUMN_HINTS,
    )


def _build_source_context(row: pd.Series) -> str:
    """Monta o contexto da fonte, veiculo ou origem do sinal."""
    return _join_row_values(row, include_columns=SOURCE_COLUMN_HINTS)


def _join_row_values(
    row: pd.Series,
    include_columns: set[str] | None = None,
    exclude_columns: set[str] | None = None,
) -> str:
    """Concatena valores textuais da linha com filtros simples por coluna."""
    fragments: list[str] = []

    for column_name, value in row.items():
        normalized_column = normalize_text(column_name)
        if include_columns is not None and normalized_column not in include_columns:
            continue
        if exclude_columns is not None and normalized_column in exclude_columns:
            continue

        normalized_value = normalize_text(value)
        if normalized_value:
            fragments.append(normalized_value)

    return " ".join(fragments)


def _count_matches(text: str, patterns: list[str] | tuple[str, ...] | None) -> int:
    """Conta quantas palavras-chave aparecem no texto normalizado."""
    if not text or not patterns:
        return 0

    padded_text = f" {text} "
    hits = 0

    for pattern in patterns:
        normalized_pattern = normalize_text(pattern)
        if normalized_pattern and f" {normalized_pattern} " in padded_text:
            hits += 1

    return hits


def _count_subtype_signal_hits(
    text_context: str,
    source_context: str,
    product_config: dict[str, Any],
) -> int:
    """Conta quantos subtipos do produto apresentam algum sinal relevante."""
    hits = 0

    for _, subtype_config in _iter_subtype_rules(product_config):
        keyword_hits = _count_matches(text_context, subtype_config.get("palavras_chave", []))
        alias_hits = _count_matches(text_context, subtype_config.get("aliases", []))
        source_hits = _count_matches(source_context, subtype_config.get("fontes_chave", []))

        if keyword_hits + alias_hits + source_hits > 0:
            hits += 1

    return hits


def _iter_subtype_rules(product_config: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """Normaliza a estrutura de regras de subtipo para iteracao simples."""
    raw_rules = product_config.get("subtipos_regras", {})

    if not raw_rules and isinstance(product_config.get("subtipos"), dict):
        raw_rules = product_config["subtipos"]

    if not raw_rules and isinstance(product_config.get("subtipos"), list):
        raw_rules = {
            subtype_name: {"palavras_chave": [subtype_name]}
            for subtype_name in product_config["subtipos"]
        }

    rules: list[tuple[str, dict[str, Any]]] = []

    for subtype_name, subtype_config in raw_rules.items():
        if isinstance(subtype_config, dict):
            rules.append((str(subtype_name), subtype_config))
            continue

        rules.append(
            (
                str(subtype_name),
                {"palavras_chave": list(subtype_config) if isinstance(subtype_config, list) else []},
            )
        )

    return rules


def _find_product_config(taxonomy: dict[str, Any], product_track: str) -> dict[str, Any]:
    """Encontra a configuracao de um produto usando o nome exibido no output."""
    normalized_target = normalize_text(product_track)

    for product_key, product_config in taxonomy.get("produtos", {}).items():
        product_name = str(product_config.get("nome", product_key))
        if normalize_text(product_name) == normalized_target:
            return product_config

    return {}
