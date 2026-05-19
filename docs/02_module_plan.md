# Plano de Módulos — DNIT Painel de Pavimentos Paragon

Este documento define o que cada módulo deve conter e como deve ser entregue.

## Etapa 0 — Base arquitetural

Objetivo:

Preparar estrutura mínima para que os módulos sejam implementados sem bagunçar o projeto.

Entregas:

- `core/dashboard_provider.py`
- `core/database.py`, se ainda não existir
- `core/filters.py`
- `core/constants.py`
- `utils/colors.py`
- `utils/formatting.py`
- estrutura de pastas `services/`, `components/`, `models/`

Validação:

- app continua rodando;
- nenhuma tela existente quebra;
- filtros globais aparecem ou ficam preparados.

## Etapa 1 — Diagnóstico técnico `/diagnostico`

Objetivo:

Criar a tela principal de diagnóstico técnico da rodovia.

Componentes:

- `LayeredHighwayMap`
- `LinearDiagram`
- `AlertsPanel`
- `SegmentDetail`

Dados necessários:

- segmentos;
- geometria;
- IRI;
- IGG;
- FWD;
- IAP;
- IQO;
- ICDS;
- ICDP;
- ICDE;
- solução recomendada;
- vida útil pós-intervenção.

Arquivos esperados:

```txt
pages/diagnostico.py
services/diagnostico_service.py
components/maps/layered_highway_map.py
components/charts/linear_diagram.py
components/panels/alerts_panel.py
components/panels/segment_detail.py
```

Validação:

- mapa renderiza;
- camada alterna entre IQO, IRI, IGG, FWD e IAP;
- diagramas por km aparecem;
- alertas apontam para trechos;
- detalhe lateral mostra o segmento selecionado.

## Etapa 2 — Soluções Paragon `/solucoes`

Objetivo:

Criar tela de engenharia aplicada à decisão.

Componentes:

- `PriorityMatrix`
- `SolutionMix`
- `CostBenefitChart`
- `InvestmentTimeline`

Arquivos esperados:

```txt
pages/solucoes.py
services/solucoes_service.py
components/charts/priority_matrix.py
components/charts/solution_mix.py
components/charts/cost_benefit_chart.py
components/charts/investment_timeline.py
```

Validação:

- matriz criticidade x custo-benefício funciona;
- mix de soluções mostra km e percentual;
- custo x benefício compara soluções;
- cronograma distribui investimento por período.

## Etapa 3 — Projeção de desempenho `/projecao`

Objetivo:

Mostrar como o pavimento se comporta no tempo.

Componentes:

- `PerformanceProjection`
- `InterventionLifeChart`

Arquivos esperados:

```txt
pages/projecao.py
services/projecao_service.py
components/charts/performance_projection.py
components/charts/intervention_life_chart.py
```

Validação:

- curva sem intervenção aparece;
- curvas com intervenção aparecem;
- vida útil por solução é comparável;
- seleção de trecho altera os gráficos.

## Etapa 4 — Risco & alertas `/risco`

Objetivo:

Identificar onde a rede vai falhar primeiro.

Componentes:

- `PredictiveAlerts`
- `AlertsPanel`

Arquivos esperados:

```txt
pages/risco.py
services/risco_service.py
components/panels/predictive_alerts.py
components/panels/alerts_panel.py
```

Validação:

- alertas preditivos aparecem;
- falha estrutural, transição de condição e janela crítica são indicadas;
- alertas são priorizados.

## Etapa 5 — Cenário econômico `/cenario`

Objetivo:

Comparar custo de intervir agora vs. adiar.

Componentes:

- `BudgetSimulator`
- `LccaScenario`

Arquivos esperados:

```txt
pages/cenario.py
services/cenario_service.py
components/panels/budget_simulator.py
components/panels/lcca_scenario.py
```

Validação:

- usuário ajusta orçamento;
- km cobertos, custo acumulado, custo evitado, backlog e IQO médio reagem;
- LCCA compara executar agora vs. adiar 1, 3 e 5 anos.

## Etapa 6 — Revisão final

Objetivo:

Refinar integração, consistência visual e estabilidade.

Validação final:

- todas as páginas rodam;
- navegação funciona;
- filtros globais sincronizam;
- estados vazios estão tratados;
- erros de banco são amigáveis;
- componentes seguem protótipos;
- código está modular.
