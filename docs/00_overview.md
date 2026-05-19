# DNIT Painel de Pavimentos Paragon — Visão Geral

## Propósito

O painel implementa a metodologia Paragon de gestão de pavimentos, estruturada como uma jornada de decisão:

```txt
Diagnóstico técnico -> Soluções -> Projeção -> Risco -> Cenário econômico
```

O objetivo é transformar dados técnicos de pavimento em decisão de intervenção, priorização, risco e orçamento.

## Conceito do produto

O sistema funciona como um exame médico da rodovia:

- **Diagnóstico:** identifica a condição atual do pavimento.
- **Prescrição:** recomenda soluções de engenharia.
- **Prognóstico:** projeta comportamento futuro.
- **Risco:** antecipa falhas e pontos críticos.
- **Decisão econômica:** compara agir agora vs. adiar.

## Telas

### 1. Diagnóstico técnico — `/diagnostico`

Tela de exame técnico da rodovia.

Componentes:

- `LayeredHighwayMap`
- `LinearDiagram`
- `AlertsPanel`
- `SegmentDetail`

Indicadores principais:

- IRI
- IGG
- FWD
- IAP
- IQO
- ICDS
- ICDP
- ICDE
- solução recomendada
- vida útil pós-intervenção

### 2. Soluções Paragon — `/solucoes`

Tela de decisão de engenharia.

Componentes:

- `PriorityMatrix`
- `SolutionMix`
- `CostBenefitChart`
- `InvestmentTimeline`

### 3. Projeção de desempenho — `/projecao`

Tela de comportamento futuro do pavimento.

Componentes:

- `PerformanceProjection`
- `InterventionLifeChart`

### 4. Risco & alertas — `/risco`

Tela preditiva de falhas e alertas.

Componentes:

- `PredictiveAlerts`
- `AlertsPanel`

### 5. Cenário econômico — `/cenario`

Tela financeira e de ciclo de vida.

Componentes:

- `BudgetSimulator`
- `LccaScenario`

## Estado global

Todos os módulos devem reagir a:

- rodovia ativa;
- trecho selecionado;
- km inicial;
- km final;
- filtros globais;
- segmento selecionado.

Esse estado deve ficar centralizado em `DashboardProvider`, `st.session_state` ou camada equivalente já existente no projeto.

## Princípio de implementação

Cada módulo deve ser entregue isoladamente, validado e integrado antes do próximo.

Não desenvolver todas as telas ao mesmo tempo.
