# Workflow para Codex — Desenvolvimento por Etapas

Use este documento como roteiro de execução.

## Como o Codex deve trabalhar

Para cada etapa:

1. Ler `AGENTS.md`.
2. Ler os documentos em `docs/`.
3. Inspecionar estrutura real do projeto.
4. Identificar conexão com banco.
5. Identificar padrões já existentes.
6. Ver prints do protótipo enviados pelo usuário.
7. Listar plano de arquivos.
8. Implementar apenas a etapa solicitada.
9. Rodar validação.
10. Explicar diff final.

## Formato obrigatório de resposta do Codex antes de codar

```md
## Entendimento da etapa

[Resumo do que será feito]

## Arquivos que vou criar ou alterar

- ...
- ...

## Dados necessários

- ...
- ...

## Riscos ou dependências

- ...
```

## Formato obrigatório de resposta do Codex ao finalizar

```md
## Implementado

- ...

## Arquivos alterados

- ...

## Comandos executados

- ...

## Como validar

- ...

## Pendências

- ...
```

## Regra de escopo

O Codex deve implementar uma etapa por vez.

Não deve implementar outra tela sem pedido explícito.

## Regra para prints

Quando o usuário enviar print do protótipo:

1. Reproduzir layout e hierarquia visual.
2. Usar nomes de componentes do projeto.
3. Não simplificar sem avisar.
4. Se o print mostrar dado não mapeado, registrar a coluna/fonte pendente.
5. Se o print mostrar gráfico, mapear:
   - tipo de gráfico;
   - eixos;
   - agrupamento;
   - filtros;
   - interação;
   - estado vazio.
