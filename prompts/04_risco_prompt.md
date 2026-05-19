# Prompt Codex — Etapa 4: Risco & Alertas

Você vai implementar apenas o módulo `/risco`.

Leia:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

Analise os prints do protótipo enviados nesta etapa.

## Objetivo

Identificar onde a rede vai falhar primeiro.

## Componentes obrigatórios

- `PredictiveAlerts`
- `AlertsPanel`

## Arquivos esperados

```txt
pages/risco.py
services/risco_service.py
components/panels/predictive_alerts.py
components/panels/alerts_panel.py
```

## Dados necessários

- segmento
- severidade
- tipo de alerta
- indicador
- valor
- previsão de falha
- transição de condição
- janela crítica
- ação recomendada

## Tipos de alerta

- falha estrutural
- mudança de faixa de condição
- janela crítica de intervenção

## Antes de implementar

1. Identifique se existem alertas no banco.
2. Identifique se alertas precisam ser derivados de indicadores.
3. Mapear contrato `Alert`.
4. Listar arquivos criados ou alterados.

## Regras

- Alertas devem ser priorizados.
- Não duplicar lógica do `AlertsPanel` se ele já existir.
- Reutilizar componente compartilhado.
- Seguir prints do protótipo.
- Não alterar outros módulos sem necessidade.

## Critério de pronto

- Página `/risco` carrega.
- Alertas preditivos aparecem.
- Painel consolidado aparece.
- Estados vazios e erros são tratados.
