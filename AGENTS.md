# AGENTS.md — DNIT Painel de Pavimentos Paragon

Este arquivo orienta o Codex/IA a desenvolver o painel Streamlit sem se perder na arquitetura, no fluxo de dados e na ordem de entrega.

## Objetivo do sistema

Construir o **DNIT Painel de Pavimentos Paragon**, um painel analítico em Streamlit para gestão de pavimentos rodoviários.

A jornada analítica é:

1. Diagnóstico técnico
2. Soluções Paragon
3. Projeção de desempenho
4. Risco & alertas
5. Cenário econômico

A lógica do produto deve seguir a metáfora:

> diagnóstico → prescrição → prognóstico → risco → decisão econômica

## Stack esperada

- Python
- Streamlit
- Pandas
- Plotly
- Banco de dados já conectado no projeto
- Componentes reutilizáveis por tela
- Páginas organizadas por módulo

## Regra central de arquitetura

A aplicação deve seguir o fluxo:

```txt
page -> service -> dataframe -> component -> layout
```

Ou seja:

- `pages/` monta a tela.
- `services/` consulta o banco, prepara dados e aplica regras de negócio.
- `components/` renderiza mapas, gráficos, painéis, cards e simuladores.
- `core/` centraliza estado global, conexão, filtros e configurações.
- `models/` documenta contratos de dados.
- `utils/` contém formatação, cores, funções auxiliares e helpers.

## Estrutura alvo

```txt
app.py
core/
  dashboard_provider.py
  config.py
  database.py
  filters.py
  constants.py

pages/
  diagnostico.py
  solucoes.py
  projecao.py
  risco.py
  cenario.py

services/
  diagnostico_service.py
  solucoes_service.py
  projecao_service.py
  risco_service.py
  cenario_service.py

components/
  maps/
    layered_highway_map.py
  charts/
    linear_diagram.py
    priority_matrix.py
    solution_mix.py
    cost_benefit_chart.py
    investment_timeline.py
    performance_projection.py
    intervention_life_chart.py
  panels/
    alerts_panel.py
    segment_detail.py
    predictive_alerts.py
    budget_simulator.py
    lcca_scenario.py

models/
  segment.py
  alert.py
  solution.py
  scenario.py

utils/
  formatting.py
  colors.py
  geo.py
```

## Regras obrigatórias

1. Não colocar SQL dentro das páginas Streamlit.
2. Não criar arquitetura paralela.
3. Não usar dados mockados se houver dados reais disponíveis.
4. Se faltar tabela ou coluna, criar fallback isolado, documentado e fácil de remover.
5. Cada componente deve receber `DataFrame` ou objeto pronto.
6. Cada service deve ter funções pequenas e testáveis.
7. Toda tela deve tratar:
   - carregando;
   - ausência de dados;
   - erro de banco;
   - filtro sem resultado.
8. O trecho selecionado deve ser compartilhado entre telas via `DashboardProvider` ou estado equivalente.
9. O layout deve seguir fielmente os prints do protótipo enviados pelo usuário.
10. Antes de codar, sempre listar arquivos que serão criados ou alterados.

## Critério de pronto global

A tarefa só está pronta quando:

- `streamlit run app.py` executa sem erro.
- Todas as páginas carregam.
- Todos os componentes principais renderizam.
- Erros de banco são tratados.
- Estados sem dados são exibidos.
- O diff final é explicado.
- O Codex informa quais comandos executou.
- O Codex informa pendências reais, sem esconder limitação.

## Como trabalhar com prints do protótipo

Ao receber prints:

1. Identificar os componentes visuais.
2. Mapear cards, filtros, gráficos, tabelas e painéis.
3. Reproduzir hierarquia visual, espaçamento e ordem.
4. Manter a arquitetura do projeto.
5. Não “inventar” design novo sem necessidade.
6. Se algo no print depender de dado inexistente, registrar a dependência.

## Proibição importante

Não entregar tudo de uma vez em um único bloco grande. Trabalhar por etapas:

1. Base arquitetural
2. Diagnóstico
3. Soluções
4. Projeção
5. Risco
6. Cenário econômico
7. Revisão final
