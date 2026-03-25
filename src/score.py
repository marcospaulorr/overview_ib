"""Motor heuristico de score decomposto para o radar de oportunidades."""

from __future__ import annotations

import re
import unicodedata
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

DEFAULT_COLUMN_ALIASES = {
    "valor_divulgado": [
        "valor_divulgado",
        "valor",
        "valor_operacao",
        "deal_value",
        "enterprise_value",
    ],
    "data_evento": [
        "data_evento",
        "data_fato",
        "event_date",
        "data",
    ],
    "data_captura": [
        "data_captura",
        "data_coleta",
        "data_referencia",
        "capture_date",
    ],
    "tipo_fonte": [
        "tipo_fonte",
        "categoria_fonte",
        "source_type",
    ],
    "fonte": [
        "fonte",
        "source",
        "publisher",
        "origem",
        "veiculo",
    ],
    "produto_trilha": [
        "produto_trilha",
        "produto",
        "trilha",
    ],
    "subtipo": [
        "subtipo",
        "sub_type",
    ],
    "titulo": [
        "titulo",
        "title",
        "headline",
        "assunto",
    ],
    "descricao": [
        "descricao",
        "descricao_curta",
        "descricao_longa",
        "texto",
        "noticia",
    ],
    "situacao_resumida": [
        "situacao_resumida",
        "resumo",
        "summary",
        "observacoes",
    ],
}


def load_scoring_config(config_path: str | Path) -> dict[str, Any]:
    """Carrega as configuracoes de score a partir de um arquivo YAML."""
    with Path(config_path).open("r", encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}


def normalize_text(value: Any) -> str:
    """Normaliza texto para comparacoes heuristicas simples."""
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


def score_materialidade(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia porte economico com base em valor divulgado ou sinais de escala."""
    facts = _build_row_facts(row, scoring_config)
    return _score_materialidade_from_facts(facts, scoring_config)


def score_mandatabilidade(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia a probabilidade de o caso virar mandato assessorado."""
    facts = _build_row_facts(row, scoring_config)
    return _score_mandatabilidade_from_facts(facts, scoring_config)


def score_timing(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia o quao acionavel e atual e o timing da oportunidade."""
    facts = _build_row_facts(row, scoring_config)
    return _score_timing_from_facts(facts, scoring_config)


def score_qualidade_sinal(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia a robustez da fonte e da evidencia observada."""
    facts = _build_row_facts(row, scoring_config)
    return _score_qualidade_sinal_from_facts(facts, scoring_config)


def score_aderencia(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia o encaixe da oportunidade com o escopo pratico do radar."""
    facts = _build_row_facts(row, scoring_config)
    return _score_aderencia_from_facts(facts, scoring_config)


def score_competitividade(row: pd.Series, scoring_config: dict[str, Any]) -> tuple[int, str]:
    """Avalia o crowding esperado na originacao da oportunidade."""
    facts = _build_row_facts(row, scoring_config)
    return _score_competitividade_from_facts(facts, scoring_config)


def calculate_row_score(row: pd.Series, scoring_config: dict[str, Any]) -> dict[str, Any]:
    """Calcula score decomposto, justificativas e sinais editoriais."""
    facts = _build_row_facts(row, scoring_config)

    score_materialidade_value, just_materialidade = _score_materialidade_from_facts(
        facts,
        scoring_config,
    )
    score_mandatabilidade_value, just_mandatabilidade = _score_mandatabilidade_from_facts(
        facts,
        scoring_config,
    )
    score_timing_value, just_timing = _score_timing_from_facts(
        facts,
        scoring_config,
    )
    score_qualidade_sinal_value, just_qualidade_sinal = _score_qualidade_sinal_from_facts(
        facts,
        scoring_config,
    )
    score_aderencia_value, just_aderencia = _score_aderencia_from_facts(
        facts,
        scoring_config,
    )
    score_competitividade_value, just_competitividade = _score_competitividade_from_facts(
        facts,
        scoring_config,
    )

    score_total = min(
        int(
            score_materialidade_value
            + score_mandatabilidade_value
            + score_timing_value
            + score_qualidade_sinal_value
            + score_aderencia_value
            + score_competitividade_value
        ),
        int(scoring_config.get("score_total_maximo", 100)),
    )

    prioridade = _get_priority(score_total, scoring_config)

    return {
        "score_materialidade": score_materialidade_value,
        "just_materialidade": just_materialidade,
        "score_mandatabilidade": score_mandatabilidade_value,
        "just_mandatabilidade": just_mandatabilidade,
        "score_timing": score_timing_value,
        "just_timing": just_timing,
        "score_qualidade_sinal": score_qualidade_sinal_value,
        "just_qualidade_sinal": just_qualidade_sinal,
        "score_aderencia": score_aderencia_value,
        "just_aderencia": just_aderencia,
        "score_competitividade": score_competitividade_value,
        "just_competitividade": just_competitividade,
        "score_total": score_total,
        "nivel_prioridade": prioridade["nivel_prioridade"],
        "entra_memo": prioridade["entra_memo"],
    }


def score_opportunities(
    df: pd.DataFrame,
    scoring_config: dict[str, Any],
) -> pd.DataFrame:
    """Aplica o score decomposto a um DataFrame inteiro de oportunidades."""
    scored_df = df.copy()

    output_columns = [
        "score_materialidade",
        "just_materialidade",
        "score_mandatabilidade",
        "just_mandatabilidade",
        "score_timing",
        "just_timing",
        "score_qualidade_sinal",
        "just_qualidade_sinal",
        "score_aderencia",
        "just_aderencia",
        "score_competitividade",
        "just_competitividade",
        "score_total",
        "nivel_prioridade",
        "entra_memo",
    ]

    if scored_df.empty:
        for column in output_columns:
            scored_df[column] = pd.Series(dtype="object")
        return scored_df

    scores = scored_df.apply(
        lambda row: calculate_row_score(row, scoring_config),
        axis=1,
        result_type="expand",
    )

    for column in output_columns:
        scored_df[column] = scores[column]

    return scored_df


def _score_materialidade_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua materialidade pelo valor divulgado ou por sinais de escala."""
    component_config = scoring_config.get("componentes", {}).get("materialidade", {})
    max_score = int(component_config.get("peso_maximo", 25))
    disclosed_value = facts["valor_numerico"]

    for faixa in sorted(
        component_config.get("faixas_valor", []),
        key=lambda item: item.get("valor_minimo", 0),
        reverse=True,
    ):
        if disclosed_value is not None and disclosed_value >= float(faixa.get("valor_minimo", 0)):
            score = _clamp_score(faixa.get("score", 0), max_score)
            just = faixa.get("justificativa", "valor divulgado em faixa relevante")
            return score, str(just)

    if disclosed_value is not None:
        return 0, str(
            component_config.get(
                "justificativa_abaixo_corte",
                "valor abaixo do corte minimo",
            )
        )

    strong_signal = component_config.get("sinais_fortes_sem_valor", {})
    if _matches_product_or_subtype(
        facts,
        strong_signal.get("produtos", []),
        strong_signal.get("subtipos", []),
    ) or _contains_any(facts["text_context"], strong_signal.get("palavras_chave", []))[0]:
        score = _clamp_score(strong_signal.get("score", 5), max_score)
        just = strong_signal.get(
            "justificativa",
            "valor nao divulgado; ha sinais de porte relevante",
        )
        return score, str(just)

    return 0, str(
        component_config.get(
            "justificativa_sem_dados",
            "sem valor ou indicio suficiente de porte",
        )
    )


def _score_mandatabilidade_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua o potencial comercial de virar mandato."""
    component_config = scoring_config.get("componentes", {}).get("mandatabilidade", {})
    max_score = int(component_config.get("peso_maximo", 25))
    text_context = facts["full_context"]

    advisor_signal, _ = _contains_any(text_context, component_config.get("sinais_assessor", []))
    formal_signal, _ = _contains_any(text_context, component_config.get("sinais_formais", []))
    very_likely_signal, likely_match = _contains_any(
        text_context,
        component_config.get("sinais_muito_provaveis", []),
    )
    forming_signal, forming_match = _contains_any(
        text_context,
        component_config.get("sinais_boa_chance", []),
    )
    hypothesis_signal, hypothesis_match = _contains_any(
        text_context,
        component_config.get("sinais_hipotese", []),
    )
    weak_signal, _ = _contains_any(text_context, component_config.get("sinais_fracos", []))

    if advisor_signal or (
        formal_signal
        and _matches_product_or_subtype(
            facts,
            component_config.get("produtos_formais", []),
            component_config.get("subtipos_formais", []),
        )
    ):
        return _clamp_score(25, max_score), str(
            component_config.get(
                "justificativa_25",
                "evento formal com clara demanda de assessor",
            )
        )

    if formal_signal or _matches_product_or_subtype(
        facts,
        component_config.get("produtos_muito_provaveis", []),
        component_config.get("subtipos_muito_provaveis", []),
    ):
        return _clamp_score(20, max_score), str(
            component_config.get(
                "justificativa_20",
                "estrutura muito provavel de gerar mandato",
            )
        )

    if very_likely_signal or _matches_product_or_subtype(
        facts,
        component_config.get("produtos_boa_chance", []),
        component_config.get("subtipos_boa_chance", []),
    ):
        just = component_config.get(
            "justificativa_15",
            "boa chance de mandato, ainda em formacao",
        )
        if likely_match:
            just = f"{just}: {likely_match}"
        return _clamp_score(15, max_score), str(just)

    if forming_signal or hypothesis_signal:
        just = component_config.get(
            "justificativa_10",
            "hipotese razoavel, ainda pouco concreta",
        )
        if forming_match or hypothesis_match:
            just = f"{just}: {forming_match or hypothesis_match}"
        return _clamp_score(10, max_score), str(just)

    if weak_signal or facts["produto_trilha_norm"]:
        return _clamp_score(5, max_score), str(
            component_config.get(
                "justificativa_5",
                "sinal fraco de mandatabilidade",
            )
        )

    return 0, str(
        component_config.get(
            "justificativa_0",
            "dificil virar mandato com os dados atuais",
        )
    )


def _score_timing_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua o timing com base em datas ou sinais textuais de janela."""
    component_config = scoring_config.get("componentes", {}).get("timing", {})
    max_score = int(component_config.get("peso_maximo", 15))
    days_distance = facts["dias_para_evento"]

    if days_distance is not None:
        if days_distance <= int(component_config.get("dias_muito_bom_max", 30)):
            return _clamp_score(15, max_score), f"evento a {days_distance} dias da referencia"
        if days_distance <= int(component_config.get("dias_bom_max", 90)):
            return _clamp_score(10, max_score), f"janela de {days_distance} dias; monitorar de perto"
        if days_distance <= int(component_config.get("dias_monitorar_max", 180)):
            return _clamp_score(5, max_score), f"janela mais distante ({days_distance} dias)"
        return 0, f"timing distante ou envelhecido ({days_distance} dias)"

    text_context = facts["full_context"]
    urgent_signal, _ = _contains_any(text_context, component_config.get("sinais_muito_bons", []))
    good_signal, _ = _contains_any(text_context, component_config.get("sinais_bons", []))
    weak_signal, _ = _contains_any(text_context, component_config.get("sinais_fracos", []))

    if urgent_signal:
        return _clamp_score(15, max_score), str(
            component_config.get(
                "justificativa_15",
                "timing muito bom pelos sinais textuais",
            )
        )
    if good_signal:
        return _clamp_score(10, max_score), str(
            component_config.get(
                "justificativa_10",
                "janela boa para monitorar de perto",
            )
        )
    if weak_signal:
        return _clamp_score(5, max_score), str(
            component_config.get(
                "justificativa_5",
                "timing ainda cedo ou pouco definido",
            )
        )

    fallback_score = _clamp_score(component_config.get("fallback_score", 5), max_score)
    return fallback_score, str(
        component_config.get(
            "fallback_justificativa",
            "sem data objetiva; timing tratado de forma conservadora",
        )
    )


def _score_qualidade_sinal_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua robustez do sinal a partir da fonte e do tipo de fonte."""
    component_config = scoring_config.get("componentes", {}).get("qualidade_sinal", {})
    max_score = int(component_config.get("peso_maximo", 15))

    if _source_in_group(
        facts,
        component_config.get("tipos_primarios", []),
        component_config.get("fontes_primarias", []),
    ):
        return _clamp_score(15, max_score), str(
            component_config.get(
                "justificativa_15",
                "fonte primaria oficial",
            )
        )

    multiple_sources_min = int(component_config.get("multiplas_fontes_minimo", 2))
    if facts["quantidade_fontes"] >= multiple_sources_min and not _source_in_group(
        facts,
        component_config.get("tipos_rumor", []),
        component_config.get("fontes_rumor", []),
    ):
        return _clamp_score(12, max_score), str(
            component_config.get(
                "justificativa_12",
                "multiplas fontes consistentes",
            )
        )

    if _source_in_group(
        facts,
        component_config.get("tipos_especializados", []),
        component_config.get("fontes_especializadas", []),
    ):
        return _clamp_score(8, max_score), str(
            component_config.get(
                "justificativa_8",
                "midia especializada confiavel",
            )
        )

    if facts["fonte_norm"] or facts["tipo_fonte_norm"]:
        return _clamp_score(4, max_score), str(
            component_config.get(
                "justificativa_4",
                "fonte identificada, mas ainda preliminar",
            )
        )

    return 0, str(
        component_config.get(
            "justificativa_0",
            "sem fonte identificavel ou sinal muito ruidoso",
        )
    )


def _score_aderencia_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua fit com a estrategia atual do radar."""
    component_config = scoring_config.get("componentes", {}).get("aderencia", {})
    max_score = int(component_config.get("peso_maximo", 10))
    text_context = facts["full_context"]

    outside_match, _ = _contains_any(text_context, component_config.get("palavras_chave_fora_escopo", []))
    low_fit_match, _ = _contains_any(text_context, component_config.get("palavras_chave_baixa", []))

    if outside_match:
        return 0, str(
            component_config.get(
                "justificativa_0",
                "fora do alcance pratico atual",
            )
        )

    if low_fit_match:
        return _clamp_score(2, max_score), str(
            component_config.get(
                "justificativa_2",
                "baixo encaixe com o foco atual",
            )
        )

    product_score = _score_from_mapping(
        facts["produto_trilha_display"],
        component_config.get("base_por_produto", {}),
    )
    subtype_score = _score_from_mapping(
        facts["subtipo_display"],
        component_config.get("override_por_subtipo", {}),
    )

    if subtype_score is not None:
        return _clamp_score(subtype_score, max_score), str(
            component_config.get(
                "justificativa_10",
                "subtipo bem alinhado ao escopo do radar",
            )
        )

    if product_score is not None:
        return _clamp_score(product_score, max_score), str(
            component_config.get(
                "justificativa_8",
                "trilha coberta pelo radar",
            )
        )

    if _contains_any(text_context, component_config.get("palavras_chave_neutras", []))[0]:
        return _clamp_score(component_config.get("score_neutro", 5), max_score), str(
            component_config.get(
                "justificativa_5",
                "encaixe ainda pouco claro, mas plausivel",
            )
        )

    return _clamp_score(component_config.get("score_baixo_padrao", 2), max_score), str(
        component_config.get(
            "justificativa_2",
            "baixo encaixe com o foco atual",
        )
    )


def _score_competitividade_from_facts(
    facts: dict[str, Any],
    scoring_config: dict[str, Any],
) -> tuple[int, str]:
    """Pontua crowding esperado para abordar a oportunidade."""
    component_config = scoring_config.get("componentes", {}).get("competitividade", {})
    max_score = int(component_config.get("peso_maximo", 10))
    text_context = facts["full_context"]

    extreme_match, _ = _contains_any(text_context, component_config.get("sinais_crowding_extremo", []))
    crowded_match, _ = _contains_any(text_context, component_config.get("sinais_muito_concorridos", []))
    proprietary_match, _ = _contains_any(text_context, component_config.get("sinais_menos_crowded", []))

    if extreme_match:
        return 0, str(
            component_config.get(
                "justificativa_0",
                "crowding extremo para originacao",
            )
        )

    base_score = _score_from_mapping(
        facts["produto_trilha_display"],
        component_config.get("base_por_produto", {}),
    )
    subtype_score = _score_from_mapping(
        facts["subtipo_display"],
        component_config.get("override_por_subtipo", {}),
    )
    current_score = subtype_score if subtype_score is not None else base_score

    if current_score is None:
        current_score = component_config.get("score_padrao", 5)

    if crowded_match:
        current_score = min(int(current_score), int(component_config.get("score_muito_concorrido", 2)))
        return _clamp_score(current_score, max_score), str(
            component_config.get(
                "justificativa_2",
                "processo muito concorrido",
            )
        )

    if proprietary_match:
        current_score = max(int(current_score), int(component_config.get("score_menos_crowded", 10)))
        return _clamp_score(current_score, max_score), str(
            component_config.get(
                "justificativa_10",
                "menos obvio e potencialmente proprietario",
            )
        )

    if int(current_score) >= 8:
        return _clamp_score(current_score, max_score), str(
            component_config.get(
                "justificativa_8",
                "competicao moderada a baixa",
            )
        )

    return _clamp_score(current_score, max_score), str(
        component_config.get(
            "justificativa_5",
            "tema visivel, mas ainda abordavel",
        )
    )


def _build_row_facts(row: pd.Series, scoring_config: dict[str, Any]) -> dict[str, Any]:
    """Consolida texto, datas, valores e classificacao em um unico contexto."""
    titulo = _safe_string(_get_row_value(row, "titulo", scoring_config))
    descricao = _safe_string(_get_row_value(row, "descricao", scoring_config))
    situacao_resumida = _safe_string(_get_row_value(row, "situacao_resumida", scoring_config))
    fonte = _safe_string(_get_row_value(row, "fonte", scoring_config))
    tipo_fonte = _safe_string(_get_row_value(row, "tipo_fonte", scoring_config))
    produto_trilha = _safe_string(_get_row_value(row, "produto_trilha", scoring_config))
    subtipo = _safe_string(_get_row_value(row, "subtipo", scoring_config))

    text_context = " ".join(
        fragment for fragment in [titulo, descricao, situacao_resumida] if fragment
    )
    full_context = " ".join(
        fragment
        for fragment in [titulo, descricao, situacao_resumida, produto_trilha, subtipo]
        if fragment
    )

    event_date = _parse_date(_get_row_value(row, "data_evento", scoring_config))
    capture_date = _parse_date(_get_row_value(row, "data_captura", scoring_config))
    reference_date = capture_date or (pd.Timestamp.today().normalize() if event_date is not None else None)
    days_distance = None
    if event_date is not None and reference_date is not None:
        days_distance = abs((event_date - reference_date).days)

    return {
        "titulo": titulo,
        "descricao": descricao,
        "situacao_resumida": situacao_resumida,
        "fonte": fonte,
        "tipo_fonte": tipo_fonte,
        "produto_trilha_display": produto_trilha,
        "subtipo_display": subtipo,
        "produto_trilha_norm": normalize_text(produto_trilha),
        "subtipo_norm": normalize_text(subtipo),
        "fonte_norm": normalize_text(fonte),
        "tipo_fonte_norm": normalize_text(tipo_fonte),
        "text_context": normalize_text(text_context),
        "full_context": normalize_text(full_context),
        "source_context": normalize_text(" ".join(fragment for fragment in [fonte, tipo_fonte] if fragment)),
        "valor_numerico": _extract_disclosed_value(row, scoring_config, [titulo, descricao, situacao_resumida]),
        "data_evento": event_date,
        "data_captura": capture_date,
        "dias_para_evento": days_distance,
        "quantidade_fontes": _count_sources(fonte, tipo_fonte),
    }


def _get_row_value(row: pd.Series, logical_name: str, scoring_config: dict[str, Any]) -> Any:
    """Busca uma coluna logica a partir de aliases configuraveis."""
    custom_aliases = scoring_config.get("colunas", {}).get(logical_name, [])
    aliases = list(DEFAULT_COLUMN_ALIASES.get(logical_name, [])) + list(custom_aliases)

    for alias in aliases:
        for column_name in row.index:
            if normalize_text(column_name) != normalize_text(alias):
                continue

            value = row.get(column_name)
            if _is_missing(value):
                continue
            return value

    return None


def _extract_disclosed_value(
    row: pd.Series,
    scoring_config: dict[str, Any],
    text_candidates: list[str] | None = None,
) -> float | None:
    """Extrai um valor numerico divulgado a partir da linha ou do texto."""
    direct_value = _parse_amount(_get_row_value(row, "valor_divulgado", scoring_config))
    if direct_value is not None:
        return direct_value

    search_texts = text_candidates or []
    if not search_texts:
        search_texts = [
            _safe_string(_get_row_value(row, "titulo", scoring_config)),
            _safe_string(_get_row_value(row, "descricao", scoring_config)),
            _safe_string(_get_row_value(row, "situacao_resumida", scoring_config)),
        ]

    extracted_values: list[float] = []
    for text in search_texts:
        extracted_values.extend(_extract_amounts_from_text(text))

    return max(extracted_values) if extracted_values else None


def _extract_amounts_from_text(text: str) -> list[float]:
    """Extrai possiveis montantes monetarios de um texto livre."""
    if not text:
        return []

    amount_pattern = re.compile(
        r"(?P<number>\d{1,3}(?:[.\s]\d{3})*(?:,\d+)?|\d+(?:[.,]\d+)?)\s*(?P<unit>bi|bilhao|bilhoes|bn|mi|milhao|milhoes|mm|mn|mil)?",
        flags=re.IGNORECASE,
    )

    values: list[float] = []
    for match in amount_pattern.finditer(str(text).lower()):
        number = _parse_number(match.group("number"))
        if number is None:
            continue

        unit = normalize_text(match.group("unit"))
        if unit in {"bi", "bilhao", "bilhoes", "bn"}:
            values.append(number * 1_000_000_000)
            continue

        if unit in {"mi", "milhao", "milhoes", "mm", "mn"}:
            values.append(number * 1_000_000)
            continue

        if unit == "mil":
            values.append(number * 1_000)
            continue

        if number >= 1_000_000:
            values.append(number)

    return values


def _parse_amount(value: Any) -> float | None:
    """Converte um valor bruto em numero comparavel com as faixas do score."""
    if _is_missing(value):
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        numeric_value = float(value)
        return numeric_value if numeric_value > 0 else None

    if isinstance(value, str):
        extracted_values = _extract_amounts_from_text(value)
        if extracted_values:
            return max(extracted_values)

        fallback_number = _parse_number(value)
        if fallback_number is not None and fallback_number >= 1_000_000:
            return fallback_number

    return None


def _parse_number(value: Any) -> float | None:
    """Interpreta numeros em formatos comuns do contexto brasileiro."""
    if value is None:
        return None

    raw_value = str(value).strip()
    if not raw_value:
        return None

    cleaned = raw_value.replace(" ", "")
    cleaned = re.sub(r"[^0-9,.-]", "", cleaned)
    if not cleaned:
        return None

    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        integer_part, decimal_part = cleaned.rsplit(",", 1)
        if len(decimal_part) <= 2:
            cleaned = f"{integer_part.replace('.', '')}.{decimal_part}"
        else:
            cleaned = cleaned.replace(",", "")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts) > 1 and all(len(part) == 3 for part in parts[1:]):
            cleaned = "".join(parts)

    try:
        return float(cleaned)
    except ValueError:
        return None


def _parse_date(value: Any) -> pd.Timestamp | None:
    """Converte datas em Timestamp com fallback seguro."""
    if _is_missing(value):
        return None

    raw_value = str(value).strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw_value):
        parsed = pd.to_datetime(raw_value, errors="coerce", format="%Y-%m-%d")
    else:
        parsed = pd.to_datetime(raw_value, errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return None

    return pd.Timestamp(parsed).normalize()


def _contains_any(text: str, patterns: list[str] | tuple[str, ...] | None) -> tuple[bool, str]:
    """Informa se algum padrao configurado aparece no texto normalizado."""
    if not text or not patterns:
        return False, ""

    padded_text = f" {text} "
    for pattern in patterns:
        normalized_pattern = normalize_text(pattern)
        if normalized_pattern and f" {normalized_pattern} " in padded_text:
            return True, normalized_pattern

    return False, ""


def _matches_product_or_subtype(
    facts: dict[str, Any],
    products: list[str] | tuple[str, ...] | None,
    subtypes: list[str] | tuple[str, ...] | None,
) -> bool:
    """Verifica se produto ou subtipo da linha batem com a regra."""
    return _value_in_list(facts["produto_trilha_display"], products) or _value_in_list(
        facts["subtipo_display"],
        subtypes,
    )


def _value_in_list(value: str, options: list[str] | tuple[str, ...] | None) -> bool:
    """Compara um valor textual com uma lista de opcoes normalizadas."""
    normalized_value = normalize_text(value)
    if not normalized_value or not options:
        return False

    return normalized_value in {normalize_text(option) for option in options}


def _source_in_group(
    facts: dict[str, Any],
    source_types: list[str] | tuple[str, ...] | None,
    source_names: list[str] | tuple[str, ...] | None,
) -> bool:
    """Verifica se a linha pertence a um grupo configurado de fontes."""
    return _value_in_list(facts["tipo_fonte"], source_types) or _value_in_list(
        facts["fonte"],
        source_names,
    )


def _score_from_mapping(value: str, mapping: dict[str, Any]) -> int | None:
    """Busca score por chave textual em um dicionario configurado."""
    if not value or not mapping:
        return None

    normalized_target = normalize_text(value)
    for key, score in mapping.items():
        if normalize_text(key) == normalized_target:
            return int(score)

    return None


def _count_sources(fonte: str, tipo_fonte: str) -> int:
    """Conta quantas fontes foram indicadas em um campo textual."""
    normalized_type = normalize_text(tipo_fonte)
    if "multiplas fontes" in normalized_type:
        return 2

    if not fonte:
        return 0

    parts = re.split(r"\s*[;|/]\s*|\s+e\s+", str(fonte), flags=re.IGNORECASE)
    normalized_parts = {normalize_text(part) for part in parts if normalize_text(part)}
    return len(normalized_parts)


def _get_priority(score_total: int, scoring_config: dict[str, Any]) -> dict[str, str]:
    """Traduz score total em prioridade editorial e flag de memo."""
    regras = scoring_config.get("prioridade_editorial", {})
    sorted_rules = sorted(
        regras.items(),
        key=lambda item: item[1].get("score_minimo", 0),
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


def _clamp_score(score: Any, max_score: int) -> int:
    """Garante que o score fique no intervalo valido do componente."""
    try:
        numeric_score = int(score)
    except (TypeError, ValueError):
        numeric_score = 0

    return max(0, min(numeric_score, max_score))


def _safe_string(value: Any) -> str:
    """Converte valores diversos em string segura para heuristicas."""
    if _is_missing(value):
        return ""
    return str(value).strip()


def _is_missing(value: Any) -> bool:
    """Identifica valores vazios, nulos ou NaN."""
    if value is None:
        return True

    try:
        return bool(pd.isna(value))
    except TypeError:
        return False
