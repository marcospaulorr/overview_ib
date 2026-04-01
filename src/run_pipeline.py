"""Orquestrador simples do pipeline ponta a ponta do radar IB."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from src.build_memo import generate_memo_outputs
from src.classify import classify_opportunities, load_taxonomy_config
from src.score import load_scoring_config, score_opportunities

DEFAULT_INPUT_PATH = PROJECT_ROOT / "data_raw" / "opps_raw.xlsx"
DEFAULT_TAXONOMY_PATH = PROJECT_ROOT / "config" / "taxonomia.yaml"
DEFAULT_SCORING_PATH = PROJECT_ROOT / "config" / "scoring.yaml"
DEFAULT_SCORED_OUTPUT_PATH = PROJECT_ROOT / "data_processed" / "opps_scored.xlsx"
DEFAULT_QUEUE_OUTPUT_PATH = PROJECT_ROOT / "data_processed" / "memo_queue.xlsx"
DEFAULT_MEMO_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "memo_semana.md"
DEFAULT_MEMO_TITLE = "Memo Semanal IB"


def run_pipeline(
    input_path: str | Path = DEFAULT_INPUT_PATH,
    taxonomy_path: str | Path = DEFAULT_TAXONOMY_PATH,
    scoring_path: str | Path = DEFAULT_SCORING_PATH,
    scored_output_path: str | Path = DEFAULT_SCORED_OUTPUT_PATH,
    queue_output_path: str | Path = DEFAULT_QUEUE_OUTPUT_PATH,
    memo_output_path: str | Path = DEFAULT_MEMO_OUTPUT_PATH,
    memo_title: str = DEFAULT_MEMO_TITLE,
) -> dict[str, Any]:
    """Roda classificacao, score e etapa editorial a partir de um Excel bruto."""
    resolved_input = Path(input_path)
    resolved_taxonomy = Path(taxonomy_path)
    resolved_scoring = Path(scoring_path)
    resolved_scored_output = Path(scored_output_path)
    resolved_queue_output = Path(queue_output_path)
    resolved_memo_output = Path(memo_output_path)

    _print_step(1, 6, f"Lendo base de entrada: {resolved_input}")
    raw_df = _read_raw_input(resolved_input)
    print(f"Base carregada com {len(raw_df)} linhas e {len(raw_df.columns)} colunas.")

    _print_step(2, 6, "Carregando configuracoes de taxonomia e score")
    taxonomy = _load_yaml_with_check(resolved_taxonomy, load_taxonomy_config, "taxonomia")
    scoring_config = _load_yaml_with_check(resolved_scoring, load_scoring_config, "score")

    _print_step(3, 6, "Aplicando classificacao heuristica")
    classified_df = classify_opportunities(raw_df, taxonomy)

    _print_step(4, 6, "Calculando score decomposto")
    scored_df = score_opportunities(classified_df, scoring_config)

    _print_step(5, 6, f"Salvando base scored em: {resolved_scored_output}")
    _save_excel(scored_df, resolved_scored_output)

    _print_step(6, 6, "Gerando fila editorial e memo semanal")
    memo_queue_df, memo_markdown = generate_memo_outputs(
        scored_df,
        scoring_config=scoring_config,
        queue_output_path=resolved_queue_output,
        memo_output_path=resolved_memo_output,
        title=memo_title,
    )

    print("")
    print("Pipeline concluido com sucesso.")
    print(f"- opps_scored.xlsx: {resolved_scored_output.resolve()}")
    print(f"- memo_queue.xlsx: {resolved_queue_output.resolve()}")
    print(f"- memo_semana.md: {resolved_memo_output.resolve()}")
    print(f"- Linhas processadas: {len(scored_df)}")
    print(f"- Oportunidades no memo: {int((memo_queue_df['secao_memo'] != 'base').sum())}")

    return {
        "raw_df": raw_df,
        "classified_df": classified_df,
        "scored_df": scored_df,
        "memo_queue_df": memo_queue_df,
        "memo_markdown": memo_markdown,
        "input_path": resolved_input,
        "scored_output_path": resolved_scored_output,
        "queue_output_path": resolved_queue_output,
        "memo_output_path": resolved_memo_output,
    }


def main() -> int:
    """Executa o pipeline com argumentos simples de linha de comando."""
    parser = argparse.ArgumentParser(description="Roda o pipeline ponta a ponta do radar IB.")
    parser.add_argument(
        "--input",
        default=str(DEFAULT_INPUT_PATH),
        help="Caminho do arquivo bruto opps_raw.xlsx.",
    )
    parser.add_argument(
        "--taxonomy-config",
        default=str(DEFAULT_TAXONOMY_PATH),
        help="Caminho do arquivo config/taxonomia.yaml.",
    )
    parser.add_argument(
        "--scoring-config",
        default=str(DEFAULT_SCORING_PATH),
        help="Caminho do arquivo config/scoring.yaml.",
    )
    parser.add_argument(
        "--scored-output",
        default=str(DEFAULT_SCORED_OUTPUT_PATH),
        help="Caminho de saida do opps_scored.xlsx.",
    )
    parser.add_argument(
        "--queue-output",
        default=str(DEFAULT_QUEUE_OUTPUT_PATH),
        help="Caminho de saida do memo_queue.xlsx.",
    )
    parser.add_argument(
        "--memo-output",
        default=str(DEFAULT_MEMO_OUTPUT_PATH),
        help="Caminho de saida do memo semanal em Markdown.",
    )
    parser.add_argument(
        "--memo-title",
        default=DEFAULT_MEMO_TITLE,
        help="Titulo do memo semanal.",
    )
    args = parser.parse_args()

    try:
        run_pipeline(
            input_path=args.input,
            taxonomy_path=args.taxonomy_config,
            scoring_path=args.scoring_config,
            scored_output_path=args.scored_output,
            queue_output_path=args.queue_output,
            memo_output_path=args.memo_output,
            memo_title=args.memo_title,
        )
    except FileNotFoundError as exc:
        print(f"Erro: {exc}")
        return 1
    except ValueError as exc:
        print(f"Erro: {exc}")
        return 1
    except Exception as exc:  # pragma: no cover - protecao simples para uso local
        print(f"Erro inesperado ao executar o pipeline: {exc}")
        return 1

    return 0


def _read_raw_input(input_path: Path) -> pd.DataFrame:
    """Le um arquivo Excel bruto com mensagem de erro clara."""
    if not input_path.exists():
        raise FileNotFoundError(
            "Arquivo de entrada nao encontrado. "
            f"Esperado: {input_path.resolve()}. "
            "Crie o arquivo data_raw/opps_raw.xlsx ou informe --input."
        )

    try:
        return pd.read_excel(input_path, engine="openpyxl")
    except Exception as exc:
        raise ValueError(
            f"Nao foi possivel ler o arquivo Excel em {input_path.resolve()}. "
            "Verifique se o arquivo existe, nao esta corrompido e pode ser aberto pelo openpyxl."
        ) from exc


def _load_yaml_with_check(
    config_path: Path,
    loader: Any,
    config_name: str,
) -> dict[str, Any]:
    """Carrega um arquivo de configuracao YAML com validacao simples."""
    if not config_path.exists():
        raise FileNotFoundError(
            f"Arquivo de configuracao de {config_name} nao encontrado: {config_path.resolve()}"
        )

    config = loader(config_path)
    if not isinstance(config, dict):
        raise ValueError(f"Configuracao de {config_name} invalida: {config_path.resolve()}")
    return config


def _save_excel(df: pd.DataFrame, output_path: Path) -> None:
    """Salva um DataFrame em Excel garantindo a existencia da pasta."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_path, index=False, engine="openpyxl")


def _print_step(step_number: int, total_steps: int, message: str) -> None:
    """Exibe progresso simples para execucao local em terminal."""
    print(f"[{step_number}/{total_steps}] {message}")


if __name__ == "__main__":
    raise SystemExit(main())
