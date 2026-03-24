# AGENTS.md

## Objetivo do projeto
Construir um radar de oportunidades de investment banking no Brasil, cobrindo:
- M&A
- Reestruturação / Distressed
- ECM
- DCM
- Special Situations
- Infra / Concessões / PPP

## Objetivo da V1
Implementar o motor analítico do radar, sem scraping pesado:
1. Ler um arquivo `opps_raw.xlsx`
2. Classificar cada linha em `produto_trilha` e `subtipo`
3. Calcular score decomposto
4. Gerar `opps_scored.xlsx`
5. Gerar `memo_queue.xlsx`
6. Gerar `memo_semana.md`

## Regras importantes
- Não implementar scraping complexo nesta fase.
- Preferir código simples, legível e modular.
- Não criar dependências desnecessárias.
- Comentar as funções principais.
- Preservar compatibilidade com execução local em Windows + VS Code.
- Usar pandas e openpyxl.
- Sempre explicar no final quais arquivos foram criados ou alterados.

## Score
O score total é de 0 a 100, composto por:
- materialidade: 0 a 25
- mandatabilidade: 0 a 25
- timing: 0 a 15
- qualidade_sinal: 0 a 15
- aderencia: 0 a 10
- competitividade: 0 a 10

## Prioridade editorial
- 80+: destaque principal
- 65-79: memo principal
- 50-64: monitorar
- abaixo de 50: base