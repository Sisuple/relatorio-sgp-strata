# Prompt Codex — Etapa 5: Cenário Econômico

Você vai implementar apenas o módulo `/cenario`.

Leia:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

Analise os prints do protótipo enviados nesta etapa.

## Objetivo

Criar a camada financeira: quanto custa intervir agora vs. adiar.

## Componentes obrigatórios

- `BudgetSimulator`
- `LccaScenario`

## Arquivos esperados

```txt
pages/cenario.py
services/cenario_service.py
components/panels/budget_simulator.py
components/panels/lcca_scenario.py
```

## Dados necessários

- orçamento disponível
- soluções priorizadas
- custo por segmento
- extensão coberta
- custo evitado
- backlog residual
- IQO médio resultante
- alternativas LCCA:
  - executar agora
  - adiar 1 ano
  - adiar 3 anos
  - adiar 5 anos

## Antes de implementar

1. Identifique se existem dados econômicos no banco.
2. Identifique tabelas de custos, soluções e orçamento.
3. Verifique se LCCA já existe ou precisa ser calculado.
4. Listar arquivos criados ou alterados.

## Regras

- Não inventar regra econômica sem registrar.
- Isolar cálculos no service.
- Componentes recebem DataFrame pronto.
- Simulador deve ser reativo.
- Seguir prints do protótipo.
- Não alterar outros módulos sem necessidade.

## Critério de pronto

- Página `/cenario` carrega.
- Simulador orçamentário funciona.
- LCCA compara executar agora vs. adiar.
- Estados vazios e erros são tratados.
