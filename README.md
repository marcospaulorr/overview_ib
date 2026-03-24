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
