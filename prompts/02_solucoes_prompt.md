# Prompt Codex — Etapa 2: Soluções Paragon

Você vai implementar apenas o módulo `/solucoes`.

Leia:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

Analise os prints do protótipo enviados nesta etapa.

## Objetivo

Criar a tela de engenharia aplicada à decisão: o que fazer, onde e quanto custa.

## Componentes obrigatórios

- `PriorityMatrix`
- `SolutionMix`
- `CostBenefitChart`
- `InvestmentTimeline`

## Arquivos esperados

```txt
pages/solucoes.py
services/solucoes_service.py
components/charts/priority_matrix.py
components/charts/solution_mix.py
components/charts/cost_benefit_chart.py
components/charts/investment_timeline.py
```

## Dados necessários

- segmento
- criticidade
- tipo de intervenção
- custo estimado
- ganho de IQO
- benefício
- custo-benefício
- prioridade
- extensão em km
- período ou ano de investimento

## Antes de implementar

1. Identifique tabelas/views de soluções ou intervenções.
2. Mapeie as colunas reais para o contrato `Solution`.
3. Verifique se criticidade e custo-benefício já existem ou precisam ser calculados.
4. Liste arquivos que serão criados ou alterados.

## Regras

- Não inventar fórmula técnica sem registrar.
- Se criticidade ou benefício não existirem, criar cálculo isolado no service com comentário.
- Componentes só recebem DataFrame pronto.
- Seguir fielmente os prints do protótipo.
- Não alterar o módulo de diagnóstico sem necessidade.

## Critério de pronto

- Página `/solucoes` carrega.
- Matriz criticidade x custo-benefício funciona.
- Mix de soluções mostra km e percentual.
- Custo x benefício compara soluções.
- Cronograma de investimento renderiza.
- Estados vazios e erros são tratados.
