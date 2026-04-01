# Radar de Oportunidades IB Brasil

Projeto inicial para estruturar um radar de oportunidades de investment banking no Brasil, com foco em M&A, reestruturacao, ECM, DCM, special situations e infra.

Nesta V1, o objetivo e montar o motor analitico basico:
- ler `opps_raw.xlsx`
- classificar oportunidades em `produto_trilha` e `subtipo`
- calcular score decomposto
- gerar fila editorial e memo semanal

O projeto foi organizado para execucao local simples em Windows + VS Code, sem scraping nesta etapa.

## Estrutura

```text
.
|-- config/
|-- data_processed/
|-- data_raw/
|-- notebooks/
|-- outputs/
`-- src/
```

## Pipeline V1

O pipeline da V1 roda ponta a ponta a partir de um arquivo Excel bruto:

1. le `data_raw/opps_raw.xlsx`
2. classifica cada linha em `produto_trilha` e `subtipo`
3. calcula o score decomposto
4. salva `data_processed/opps_scored.xlsx`
5. gera `data_processed/memo_queue.xlsx`
6. gera `outputs/memo_semana.md`

O script orquestrador fica em `src/run_pipeline.py` e reaproveita a logica existente dos modulos de classificacao, score e editorial.

## Como preparar a base de entrada

Crie o arquivo `data_raw/opps_raw.xlsx` com uma linha por oportunidade.

O pipeline foi desenhado para usar fallbacks de colunas quando alguns campos faltarem, mas a base funciona melhor quando inclui pelo menos parte das colunas abaixo:

- `titulo`
- `descricao`
- `situacao_resumida`
- `fonte`
- `tipo_fonte`
- `valor_divulgado`
- `data_evento`
- `data_captura`

Tambem sao aceitos aliases ja tratados pelo codigo, como `headline`, `summary`, `origem_sinal`, `categoria_fonte`, `valor_estimado` e outros equivalentes.

Exemplo de base minima:

| titulo | descricao | fonte | tipo_fonte | data_evento | data_captura |
|---|---|---|---|---|---|
| Companhia avalia aquisicao de ativo | Processo competitivo em andamento | Brazil Journal | midia especializada | 2026-04-10 | 2026-03-28 |

## Como rodar

No diretorio raiz do projeto:

```bash
python -m src.run_pipeline
```

Se quiser informar caminhos diferentes:

```bash
python -m src.run_pipeline --input data_raw/opps_raw_teste.xlsx --scored-output data_processed/opps_scored_teste.xlsx --queue-output data_processed/memo_queue_teste.xlsx --memo-output outputs/memo_semana_teste.md
```

O script falha de forma clara se `data_raw/opps_raw.xlsx` nao existir e informa o caminho esperado.

## Saidas geradas

Ao final da execucao, o pipeline produz:

- `data_processed/opps_scored.xlsx`
- `data_processed/memo_queue.xlsx`
- `outputs/memo_semana.md`

## Observacoes da V1

- nao ha scraping nesta etapa
- a classificacao e heuristica, baseada em taxonomia e palavras-chave
- o score depende da qualidade das colunas disponiveis na base
- o memo semanal usa a prioridade editorial ja configurada em `config/scoring.yaml`
