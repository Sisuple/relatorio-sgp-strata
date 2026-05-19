# Prompt Codex — Etapa 1: Diagnóstico Técnico

Você vai implementar apenas o módulo `/diagnostico`.

Antes de codar, leia:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

Também analise os prints do protótipo que serão enviados nesta etapa.

## Objetivo

Criar a tela de diagnóstico técnico da rodovia, funcionando como exame clínico do pavimento.

## Componentes obrigatórios

- `LayeredHighwayMap`
- `LinearDiagram`
- `AlertsPanel`
- `SegmentDetail`

## Arquivos esperados

```txt
pages/diagnostico.py
services/diagnostico_service.py
components/maps/layered_highway_map.py
components/charts/linear_diagram.py
components/panels/alerts_panel.py
components/panels/segment_detail.py
```

## Dados necessários

- rodovia
- km inicial
- km final
- geometria
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
- custo estimado

## Antes de implementar

1. Inspecione a conexão com banco.
2. Localize tabelas ou views que contenham os indicadores.
3. Mapeie as colunas reais para o contrato `Segment`.
4. Liste o que existe e o que está faltando.
5. Liste os arquivos que serão criados ou alterados.

## Regras

- Não usar SQL dentro da página.
- Criar funções em `diagnostico_service.py`.
- Cada componente deve receber DataFrame pronto.
- O mapa deve alternar entre IQO, IRI, IGG, FWD e IAP.
- Os diagramas lineares devem ser organizados por km.
- Alertas devem ser priorizados.
- O detalhe do segmento deve reagir ao segmento selecionado.
- Seguir visualmente os prints do protótipo.

## Critério de pronto

- Página `/diagnostico` carrega.
- Mapa renderiza ou exibe estado sem geometria.
- Diagramas aparecem.
- Alertas aparecem.
- Detalhe do segmento aparece.
- Estados vazios são tratados.
- Erros de banco são tratados.
- `streamlit run app.py` roda sem erro.
