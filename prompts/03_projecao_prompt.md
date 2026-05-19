# Prompt Codex — Etapa 3: Projeção de Desempenho

Você vai implementar apenas o módulo `/projecao`.

Leia:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

Analise os prints do protótipo enviados nesta etapa.

## Objetivo

Mostrar como o pavimento vai se comportar no tempo.

## Componentes obrigatórios

- `PerformanceProjection`
- `InterventionLifeChart`

## Arquivos esperados

```txt
pages/projecao.py
services/projecao_service.py
components/charts/performance_projection.py
components/charts/intervention_life_chart.py
```

## Dados necessários

- segmento selecionado
- ano
- cenário
- IQO projetado
- tipo de intervenção
- vida útil projetada
- custo acumulado, se existir

## Cenários esperados

- sem intervenção
- manutenção preventiva
- restauração
- reforço
- reconstrução

## Antes de implementar

1. Identifique se já existem projeções no banco.
2. Verifique se as curvas precisam ser calculadas.
3. Se cálculo for necessário, isole em `projecao_service.py`.
4. Liste arquivos que serão criados ou alterados.

## Regras

- Não inventar curva técnica sem avisar.
- Se usar aproximação, documentar claramente.
- Seleção de segmento deve alterar os gráficos.
- Seguir prints do protótipo.
- Não alterar outros módulos sem necessidade.

## Critério de pronto

- Página `/projecao` carrega.
- Curvas de IQO aparecem.
- Comparativo de vida útil aparece.
- Estados vazios e erros são tratados.
