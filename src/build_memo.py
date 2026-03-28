"""Fila editorial e memo semanal para o radar de oportunidades."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.score import DEFAULT_COLUMN_ALIASES, load_scoring_config, normalize_text

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SCORING_PATH = PROJECT_ROOT / "config" / "scoring.yaml"
DEFAULT_INPUT_PATH = PROJECT_ROOT / "data_processed" / "opps_scored.xlsx"
DEFAULT_QUEUE_PATH = PROJECT_ROOT / "data_processed" / "memo_queue.xlsx"
DEFAULT_MEMO_PATH = PROJECT_ROOT / "outputs" / "memo_semana.md"

EDITORIAL_SECTION_LABELS = {
    "destaque_principal": "destaque principal",
    "memo_principal": "memo principal",
    "monitorar": "monitoramento",
    "base": "base",
}

PRIORITY_TO_SECTION = {
    "maxima": "destaque principal",
    "alta": "memo principal",
    "monitorar": "monitoramento",
    "base": "base",
}

SECTION_ORDER = {
    "destaque principal": 1,
    "memo principal": 2,
    "monitoramento": 3,
    "base": 4,
}

MEMO_DISPLAY_ALIASES = {
    "titulo_memo": list(DEFAULT_COLUMN_ALIASES["titulo"])
    + ["empresa", "companhia", "company", "issuer", "emissor", "deal"],
    "resumo_memo": list(DEFAULT_COLUMN_ALIASES["situacao_resumida"])
    + list(DEFAULT_COLUMN_ALIASES["descricao"])
    + ["conteudo", "texto", "noticia", "observacoes"],
    "fonte_memo": list(DEFAULT_COLUMN_ALIASES["fonte"]),
    "tipo_fonte_memo": list(DEFAULT_COLUMN_ALIASES["tipo_fonte"]),
    "produto_trilha_memo": list(DEFAULT_COLUMN_ALIASES["produto_trilha"]),
    "subtipo_memo": list(DEFAULT_COLUMN_ALIASES["subtipo"]),
    "data_evento_memo": list(DEFAULT_COLUMN_ALIASES["data_evento"]),
    "data_captura_memo": list(DEFAULT_COLUMN_ALIASES["data_captura"]),
}

SCORE_COMPONENTS = [
    ("score_materialidade", "materialidade", 25),
    ("score_mandatabilidade", "mandatabilidade", 25),
    ("score_timing", "timing", 15),
    ("score_qualidade_sinal", "qualidade_sinal", 15),
    ("score_aderencia", "aderencia", 10),
    ("score_competitividade", "competitividade", 10),
]


def build_memo_queue(
    df: pd.DataFrame,
    scoring_config: dict[str, Any] | None = None,
) -> pd.DataFrame:
    """Prepara uma fila editorial ordenada a partir do DataFrame scored."""
    queue_df = df.copy()
    scoring_config = scoring_config or {}

    derived_columns = [
        "secao_memo",
        "ordem_secao",
        "ordem_editorial",
        "ordem_na_secao",
        "titulo_memo",
        "resumo_memo",
        "fonte_memo",
        "tipo_fonte_memo",
        "produto_trilha_memo",
        "subtipo_memo",
        "data_evento_memo",
        "data_captura_memo",
        "score_decomposto",
    ]

    if queue_df.empty:
        for column in derived_columns:
            queue_df[column] = pd.Series(dtype="object")
        return queue_df

    normalized_columns = _build_normalized_column_map(queue_df.columns)

    score_total_series = _resolve_numeric_series(queue_df, normalized_columns, ["score_total"])
    queue_df["score_total"] = score_total_series.fillna(0).astype(int)

    for component_column, _, _ in SCORE_COMPONENTS:
        component_series = _resolve_numeric_series(
            queue_df,
            normalized_columns,
            [component_column],
        )
        queue_df[component_column] = component_series.astype("Int64")

    derived_priority = queue_df["score_total"].apply(
        lambda score_total: _derive_priority_from_score(int(score_total), scoring_config)
    )
    priority_frame = pd.DataFrame(list(derived_priority), index=queue_df.index)

    existing_priority = _resolve_text_series(queue_df, normalized_columns, ["nivel_prioridade"])
    existing_entra_memo = _resolve_text_series(queue_df, normalized_columns, ["entra_memo"])
    queue_df["nivel_prioridade"] = existing_priority.where(
        existing_priority.ne(""),
        priority_frame["nivel_prioridade"],
    )
    queue_df["entra_memo"] = existing_entra_memo.where(
        existing_entra_memo.ne(""),
        priority_frame["entra_memo"],
    )

    for target_column, aliases in MEMO_DISPLAY_ALIASES.items():
        queue_df[target_column] = _resolve_text_series(queue_df, normalized_columns, aliases)

    queue_df["titulo_memo"] = queue_df["titulo_memo"].where(
        queue_df["titulo_memo"].ne(""),
        queue_df.index.to_series().apply(lambda index: f"Oportunidade {index + 1}"),
    )
    queue_df["resumo_memo"] = queue_df["resumo_memo"].apply(
        lambda value: _truncate_text(value, max_length=280)
    )
    queue_df["data_evento_memo"] = queue_df["data_evento_memo"].apply(_format_date_display)
    queue_df["data_captura_memo"] = queue_df["data_captura_memo"].apply(_format_date_display)
    queue_df["secao_memo"] = queue_df.apply(
        lambda row: _determine_editorial_section(row, scoring_config),
        axis=1,
    )
    queue_df["ordem_secao"] = queue_df["secao_memo"].map(SECTION_ORDER).fillna(99).astype(int)
    queue_df["score_decomposto"] = queue_df.apply(_format_score_breakdown, axis=1)

    queue_df = queue_df.sort_values(
        by=[
            "ordem_secao",
            "score_total",
            "score_timing",
            "score_materialidade",
            "titulo_memo",
        ],
        ascending=[True, False, False, False, True],
        kind="stable",
        na_position="last",
    ).reset_index(drop=True)

    queue_df["ordem_editorial"] = range(1, len(queue_df) + 1)
    queue_df["ordem_na_secao"] = queue_df.groupby("secao_memo").cumcount() + 1

    ordered_front_columns = [
        "ordem_editorial",
        "ordem_na_secao",
        "secao_memo",
        "score_total",
        "nivel_prioridade",
        "entra_memo",
        "titulo_memo",
        "produto_trilha_memo",
        "subtipo_memo",
        "resumo_memo",
        "fonte_memo",
        "tipo_fonte_memo",
        "data_evento_memo",
        "data_captura_memo",
        "score_decomposto",
        "score_materialidade",
        "score_mandatabilidade",
        "score_timing",
        "score_qualidade_sinal",
        "score_aderencia",
        "score_competitividade",
    ]
    ordered_front_columns = [column for column in ordered_front_columns if column in queue_df.columns]

    remaining_columns = [
        column for column in queue_df.columns if column not in ordered_front_columns and column != "ordem_secao"
    ]
    return queue_df[ordered_front_columns + remaining_columns]


def build_weekly_memo_markdown(
    df: pd.DataFrame,
    generation_date: str | pd.Timestamp | None = None,
    title: str = "Memo Semanal IB",
) -> str:
    """Gera o memo semanal em Markdown com estrutura editorial simples."""
    if "secao_memo" not in df.columns:
        memo_df = build_memo_queue(df)
    else:
        memo_df = df.copy()

    generation_label = _format_generation_date(generation_date)
    relevant_df = memo_df[memo_df["secao_memo"].isin({"destaque principal", "memo principal", "monitoramento"})]

    lines = [
        f"# {title}",
        "",
        f"Data de geracao: {generation_label}",
        "",
        "## Resumo executivo",
    ]
    lines.extend(_build_executive_summary_lines(relevant_df))

    for section_name in ["destaque principal", "memo principal", "monitoramento"]:
        lines.extend(["", f"## {_format_section_title(section_name)}"])
        section_df = memo_df[memo_df["secao_memo"] == section_name]
        if section_df.empty:
            lines.append("- Sem oportunidades classificadas nesta secao.")
            continue

        for _, row in section_df.iterrows():
            lines.extend(_format_memo_entry(row))

    return "\n".join(lines).strip() + "\n"


def export_memo_queue(df: pd.DataFrame, output_path: str | Path = DEFAULT_QUEUE_PATH) -> Path:
    """Salva a fila editorial em Excel."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output, index=False)
    return output


def write_weekly_memo(markdown: str, output_path: str | Path = DEFAULT_MEMO_PATH) -> Path:
    """Salva o memo semanal em Markdown."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(markdown, encoding="utf-8")
    return output


def generate_memo_outputs(
    df: pd.DataFrame,
    scoring_config: dict[str, Any] | None = None,
    queue_output_path: str | Path = DEFAULT_QUEUE_PATH,
    memo_output_path: str | Path = DEFAULT_MEMO_PATH,
    generation_date: str | pd.Timestamp | None = None,
    title: str = "Memo Semanal IB",
) -> tuple[pd.DataFrame, str]:
    """Gera a fila editorial, salva os artefatos e devolve os resultados em memoria."""
    queue_df = build_memo_queue(df, scoring_config=scoring_config)
    memo_markdown = build_weekly_memo_markdown(
        queue_df,
        generation_date=generation_date,
        title=title,
    )

    export_memo_queue(queue_df, queue_output_path)
    write_weekly_memo(memo_markdown, memo_output_path)
    return queue_df, memo_markdown


def main() -> None:
    """Executa a geracao do memo a partir de um arquivo scored em Excel."""
    parser = argparse.ArgumentParser(description="Gera memo_queue.xlsx e memo_semana.md.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Caminho do arquivo opps_scored.xlsx.",
    )
    parser.add_argument(
        "--scoring-config",
        default=str(DEFAULT_SCORING_PATH),
        help="Caminho do arquivo config/scoring.yaml.",
    )
    parser.add_argument(
        "--queue-output",
        default=str(DEFAULT_QUEUE_PATH),
        help="Caminho de saida do memo_queue.xlsx.",
    )
    parser.add_argument(
        "--memo-output",
        default=str(DEFAULT_MEMO_PATH),
        help="Caminho de saida do memo semanal em markdown.",
    )
    parser.add_argument(
        "--title",
        default="Memo Semanal IB",
        help="Titulo do memo.",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Arquivo de input nao encontrado: {input_path}")

    scoring_config = load_scoring_config(args.scoring_config)
    scored_df = pd.read_excel(input_path)
    queue_df, _ = generate_memo_outputs(
        scored_df,
        scoring_config=scoring_config,
        queue_output_path=args.queue_output,
        memo_output_path=args.memo_output,
        title=args.title,
    )

    print(f"Fila editorial gerada com {len(queue_df)} linhas.")
    print(f"Arquivo Excel salvo em: {Path(args.queue_output).resolve()}")
    print(f"Memo semanal salvo em: {Path(args.memo_output).resolve()}")


def _build_normalized_column_map(columns: pd.Index) -> dict[str, str]:
    """Mapeia nomes normalizados de coluna para o nome original no DataFrame."""
    normalized_map: dict[str, str] = {}
    for column in columns:
        normalized_name = normalize_text(column)
        if normalized_name and normalized_name not in normalized_map:
            normalized_map[normalized_name] = str(column)
    return normalized_map


def _resolve_text_series(
    df: pd.DataFrame,
    normalized_columns: dict[str, str],
    aliases: list[str],
) -> pd.Series:
    """Busca a primeira coluna textual disponivel entre varios aliases."""
    column_name = _find_matching_column(normalized_columns, aliases)
    if not column_name:
        return pd.Series([""] * len(df), index=df.index, dtype="object")

    return df[column_name].apply(_safe_string)


def _resolve_numeric_series(
    df: pd.DataFrame,
    normalized_columns: dict[str, str],
    aliases: list[str],
) -> pd.Series:
    """Busca a primeira coluna numerica disponivel entre varios aliases."""
    column_name = _find_matching_column(normalized_columns, aliases)
    if not column_name:
        return pd.Series([pd.NA] * len(df), index=df.index, dtype="Float64")

    return pd.to_numeric(df[column_name], errors="coerce").astype("Float64")


def _find_matching_column(normalized_columns: dict[str, str], aliases: list[str]) -> str:
    """Encontra a primeira coluna cujo alias normalizado exista no DataFrame."""
    for alias in aliases:
        column_name = normalized_columns.get(normalize_text(alias))
        if column_name:
            return column_name
    return ""


def _derive_priority_from_score(score_total: int, scoring_config: dict[str, Any]) -> dict[str, str]:
    """Traduz o score em prioridade editorial usando o mesmo YAML do motor de score."""
    priority_rules = scoring_config.get("prioridade_editorial", {})
    sorted_rules = sorted(
        priority_rules.items(),
        key=lambda item: int(item[1].get("score_minimo", 0)),
        reverse=True,
    )

    for _, rule in sorted_rules:
        if score_total >= int(rule.get("score_minimo", 0)):
            return {
                "nivel_prioridade": str(rule.get("nivel_prioridade", "base")),
                "entra_memo": str(rule.get("entra_memo", "nao")),
            }

    return {
        "nivel_prioridade": "base",
        "entra_memo": "nao",
    }


def _determine_editorial_section(row: pd.Series, scoring_config: dict[str, Any]) -> str:
    """Mapeia a linha para a secao do memo, com fallback por score."""
    priority_value = normalize_text(row.get("nivel_prioridade", ""))
    if priority_value in PRIORITY_TO_SECTION:
        return PRIORITY_TO_SECTION[priority_value]

    score_total = _to_int_or_zero(row.get("score_total"))
    priority_rules = scoring_config.get("prioridade_editorial", {})
    sorted_rules = sorted(
        priority_rules.items(),
        key=lambda item: int(item[1].get("score_minimo", 0)),
        reverse=True,
    )

    for rule_key, rule in sorted_rules:
        if score_total >= int(rule.get("score_minimo", 0)):
            return EDITORIAL_SECTION_LABELS.get(rule_key, "base")

    return "base"


def _format_score_breakdown(row: pd.Series) -> str:
    """Condensa a decomposicao do score em uma linha legivel para o memo."""
    parts = []
    for column_name, label, max_score in SCORE_COMPONENTS:
        value = row.get(column_name)
        if _is_missing(value):
            parts.append(f"{label} n/d")
            continue
        parts.append(f"{label} {int(value)}/{max_score}")
    return " | ".join(parts)


def _build_executive_summary_lines(df: pd.DataFrame) -> list[str]:
    """Monta bullets curtos de resumo executivo para o topo do memo."""
    if df.empty:
        return ["- Nenhuma oportunidade atingiu o corte editorial desta rodada."]

    counts = df["secao_memo"].value_counts()
    top_row = df.sort_values("score_total", ascending=False, kind="stable").iloc[0]
    top_title = _safe_string(top_row.get("titulo_memo")) or "oportunidade sem titulo"
    top_product = _safe_string(top_row.get("produto_trilha_memo")) or "trilha indefinida"
    top_score = _to_int_or_zero(top_row.get("score_total"))

    return [
        f"- {len(df)} oportunidades com score igual ou superior a 50 nesta rodada.",
        (
            "- Distribuicao editorial: "
            f"{int(counts.get('destaque principal', 0))} em destaque principal, "
            f"{int(counts.get('memo principal', 0))} no memo principal e "
            f"{int(counts.get('monitoramento', 0))} em monitoramento."
        ),
        f"- Maior prioridade da semana: {top_title} ({top_score}/100, {top_product}).",
    ]


def _format_memo_entry(row: pd.Series) -> list[str]:
    """Formata uma oportunidade individual dentro do markdown semanal."""
    title = _safe_string(row.get("titulo_memo")) or "Oportunidade sem titulo"
    summary = _safe_string(row.get("resumo_memo")) or "Sem resumo disponivel."
    product = _safe_string(row.get("produto_trilha_memo")) or "n/d"
    subtype = _safe_string(row.get("subtipo_memo")) or "n/d"
    source = _safe_string(row.get("fonte_memo")) or "n/d"
    event_date = _safe_string(row.get("data_evento_memo")) or "n/d"
    score_total = _to_int_or_zero(row.get("score_total"))
    priority = _safe_string(row.get("nivel_prioridade")) or "base"
    score_breakdown = _safe_string(row.get("score_decomposto")) or "decomposicao indisponivel"

    return [
        "",
        f"### {title}",
        f"- Trilha: {product} | Subtipo: {subtype}",
        f"- Score total: {score_total}/100 | Prioridade editorial: {priority}",
        f"- Decomposicao do score: {score_breakdown}",
        f"- Fonte: {source} | Data do evento: {event_date}",
        f"- Resumo: {summary}",
    ]


def _format_generation_date(value: str | pd.Timestamp | None) -> str:
    """Padroniza a data mostrada no topo do memo."""
    if value is None:
        return pd.Timestamp.today().normalize().strftime("%d/%m/%Y")

    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)
    if pd.isna(parsed):
        return _safe_string(value) or pd.Timestamp.today().normalize().strftime("%d/%m/%Y")

    return pd.Timestamp(parsed).strftime("%d/%m/%Y")


def _format_date_display(value: Any) -> str:
    """Formata datas em estilo brasileiro e preserva vazio de forma segura."""
    if _is_missing(value):
        return ""

    parsed = _parse_display_date(value)
    if pd.isna(parsed):
        return _safe_string(value)

    return pd.Timestamp(parsed).strftime("%d/%m/%Y")


def _parse_display_date(value: Any) -> pd.Timestamp | Any:
    """Interpreta datas de forma previsivel para exibicao no memo."""
    raw_value = _safe_string(value)
    if not raw_value:
        return pd.NaT

    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value):
        return pd.to_datetime(raw_value, errors="coerce", format="%Y-%m-%d")

    return pd.to_datetime(raw_value, errors="coerce", dayfirst=True)


def _format_section_title(section_name: str) -> str:
    """Capitaliza apenas a primeira letra da secao para o markdown."""
    cleaned = _safe_string(section_name)
    if not cleaned:
        return "Secao"
    return cleaned[0].upper() + cleaned[1:]


def _truncate_text(value: Any, max_length: int = 280) -> str:
    """Encurta textos muito longos para manter o memo legivel."""
    text = _safe_string(value)
    if len(text) <= max_length:
        return text
    return text[: max_length - 3].rstrip() + "..."


def _safe_string(value: Any) -> str:
    """Converte qualquer valor em string segura para exibicao."""
    if _is_missing(value):
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    """Identifica nulos, NaN ou strings vazias."""
    if value is None:
        return True

    try:
        if bool(pd.isna(value)):
            return True
    except TypeError:
        pass

    if isinstance(value, str) and not value.strip():
        return True

    return False


def _to_int_or_zero(value: Any) -> int:
    """Converte valores numericos para inteiro com fallback seguro."""
    numeric_value = pd.to_numeric(value, errors="coerce")
    if pd.isna(numeric_value):
        return 0
    return int(numeric_value)


if __name__ == "__main__":
    main()
