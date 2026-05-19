# Especificação dos Componentes

## LayeredHighwayMap

Arquivo:

```txt
components/maps/layered_highway_map.py
```

Função:

Renderizar mapa interativo da rodovia com alternância de camada técnica.

Camadas:

- IQO, padrão
- IRI
- IGG
- FWD
- IAP

Entrada esperada:

```python
render_layered_highway_map(
    segments_df,
    active_layer,
    selected_segment_id=None
)
```

Comportamento:

- colorir segmento conforme classe do indicador;
- permitir seleção de segmento quando possível;
- destacar segmento selecionado;
- tratar ausência de geometria.

## LinearDiagram

Arquivo:

```txt
components/charts/linear_diagram.py
```

Função:

Renderizar diagramas lineares por km.

Categorias:

- dados estruturais: IRI, FWD, IGG;
- IQO consolidado;
- ICDS, ICDP, ICDE;
- IAP e solução recomendada.

Entrada esperada:

```python
render_linear_diagram(
    df,
    x_start_col="km_inicial",
    x_end_col="km_final",
    metrics=[]
)
```

## AlertsPanel

Arquivo:

```txt
components/panels/alerts_panel.py
```

Função:

Mostrar alertas priorizados.

Entrada esperada:

```python
render_alerts_panel(alerts_df, on_select_segment=None)
```

Campos mínimos:

- severidade
- mensagem
- km_inicial
- km_final
- indicador
- valor
- ação recomendada

## SegmentDetail

Arquivo:

```txt
components/panels/segment_detail.py
```

Função:

Mostrar detalhe técnico do segmento selecionado.

Entrada esperada:

```python
render_segment_detail(segment)
```

Deve mostrar:

- rodovia;
- km inicial/final;
- IRI;
- IGG;
- FWD;
- IAP;
- IQO;
- ICDS;
- ICDP;
- ICDE;
- solução recomendada;
- vida útil pós-intervenção;
- custo estimado.

## PriorityMatrix

Arquivo:

```txt
components/charts/priority_matrix.py
```

Função:

Scatter plot de criticidade x custo-benefício.

Entrada esperada:

```python
render_priority_matrix(solutions_df)
```

Eixos:

- x: custo-benefício;
- y: criticidade;
- tamanho: custo ou extensão;
- cor: tipo de intervenção.

## SolutionMix

Arquivo:

```txt
components/charts/solution_mix.py
```

Função:

Mostrar distribuição da rede por tipo de intervenção.

Métricas:

- km;
- percentual;
- quantidade de segmentos.

## CostBenefitChart

Arquivo:

```txt
components/charts/cost_benefit_chart.py
```

Função:

Comparar investimento vs. ganho de IQO por solução.

## InvestmentTimeline

Arquivo:

```txt
components/charts/investment_timeline.py
```

Função:

Mostrar distribuição temporal dos investimentos.

## PerformanceProjection

Arquivo:

```txt
components/charts/performance_projection.py
```

Função:

Curvas de IQO ao longo dos anos.

Cenários:

- sem intervenção;
- manutenção preventiva;
- restauração;
- reforço;
- reconstrução.

## InterventionLifeChart

Arquivo:

```txt
components/charts/intervention_life_chart.py
```

Função:

Barras comparando vida útil por intervenção.

## PredictiveAlerts

Arquivo:

```txt
components/panels/predictive_alerts.py
```

Função:

Mostrar previsão de falhas e janelas críticas.

Tipos:

- falha estrutural;
- mudança de faixa de condição;
- janela crítica de intervenção.

## BudgetSimulator

Arquivo:

```txt
components/panels/budget_simulator.py
```

Função:

Simular orçamento disponível.

Entradas:

- orçamento disponível;
- lista priorizada de soluções;
- custos por segmento.

Saídas:

- km cobertos;
- custo acumulado;
- custo evitado;
- backlog residual;
- IQO médio resultante.

## LccaScenario

Arquivo:

```txt
components/panels/lcca_scenario.py
```

Função:

Comparar custo de ciclo de vida.

Cenários:

- executar agora;
- adiar 1 ano;
- adiar 3 anos;
- adiar 5 anos.
