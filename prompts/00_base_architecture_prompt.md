# Prompt Codex — Etapa 0: Base Arquitetural

Você é o engenheiro responsável por preparar a base arquitetural do DNIT Painel de Pavimentos Paragon em Streamlit.

Leia obrigatoriamente:

- `AGENTS.md`
- `docs/00_overview.md`
- `docs/01_data_contracts.md`
- `docs/02_module_plan.md`
- `docs/03_component_specs.md`
- `docs/04_codex_workflow.md`

## Tarefa

Preparar a estrutura base do projeto para desenvolvimento modular por telas.

## Antes de codar

1. Inspecione a estrutura atual do projeto.
2. Identifique como o app Streamlit inicia.
3. Identifique onde está a conexão com banco.
4. Identifique padrões já existentes de páginas, componentes e services.
5. Liste os arquivos que serão criados ou alterados.

## Implementar

Criar ou ajustar, respeitando o projeto existente:

```txt
core/dashboard_provider.py
core/database.py
core/filters.py
core/constants.py
utils/colors.py
utils/formatting.py
services/
components/
models/
```

## Regras

- Não quebrar telas existentes.
- Não mover arquivos sem necessidade.
- Não refatorar tudo.
- Criar estrutura mínima e clara.
- Se já existir equivalente, adaptar ao padrão existente.
- Não criar dados mockados.

## Critério de pronto

- `streamlit run app.py` roda sem erro.
- Estrutura modular está preparada.
- Estado global de rodovia/trecho/filtros está planejado ou implementado.
- O diff final é explicado.
