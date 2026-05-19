# Contratos de Dados — DNIT Painel de Pavimentos Paragon

Este documento define os dados mínimos necessários para cada módulo.

O Codex deve mapear estes contratos para as tabelas reais existentes no banco. Não deve inventar dados se houver tabelas disponíveis.

## Segment

Representa um trecho homogêneo ou segmento da rodovia.

```python
Segment:
  segment_id: str | int
  rodovia: str
  uf: str | None
  km_inicial: float
  km_final: float
  extensao_km: float
  sentido: str | None
  faixa: str | None

  iri: float | None
  igg: float | None
  fwd: float | None
  iap: float | None
  iqo: float | None

  icds: float | None
  icdp: float | None
  icde: float | None

  classe_iqo: str | None
  classe_iri: str | None
  classe_igg: str | None
  classe_fwd: str | None
  classe_iap: str | None

  solucao_recomendada: str | None
  vida_util_pos_intervencao: float | None
  custo_estimado: float | None

  geometria: object | None
```

## Alert

Representa alerta técnico, preditivo ou econômico.

```python
Alert:
  alert_id: str | int
  tipo: str
  severidade: str
  rodovia: str
  segment_id: str | int
  km_inicial: float
  km_final: float
  indicador: str | None
  valor: float | None
  mensagem: str
  acao_recomendada: str | None
```

Severidades sugeridas:

```txt
critico
atencao
informativo
```

## Solution

Representa uma solução de intervenção aplicável a um segmento.

```python
Solution:
  solution_id: str | int
  segment_id: str | int
  tipo_intervencao: str
  descricao: str | None
  custo: float
  ganho_iqo: float | None
  beneficio: float | None
  custo_beneficio: float | None
  vida_util: float | None
  prioridade: float | None
```

Tipos sugeridos:

```txt
manutencao_preventiva
restauracao
reforco
reconstrucao
```

## PerformanceProjection

Representa curva de desempenho ao longo do tempo.

```python
PerformanceProjection:
  segment_id: str | int
  ano: int
  cenario: str
  iqo_projetado: float
  custo_acumulado: float | None
```

Cenários sugeridos:

```txt
sem_intervencao
manutencao_preventiva
restauracao
reforco
reconstrucao
```

## BudgetScenario

Representa resultado do simulador orçamentário.

```python
BudgetScenario:
  orcamento: float
  km_cobertos: float
  custo_acumulado: float
  custo_evitado: float
  backlog_residual: float
  iqo_medio_resultante: float
```

## LccaScenario

Representa análise de custo de ciclo de vida.

```python
LccaScenario:
  segment_id: str | int
  alternativa: str
  horizonte_anos: int
  custo_intervencao: float
  custo_manutencao: float
  custo_deterioracao_evitada: float
  custo_total: float
```

Alternativas sugeridas:

```txt
executar_agora
adiar_1_ano
adiar_3_anos
adiar_5_anos
```

## Observação crítica

Se algum campo não existir no banco, o Codex deve:

1. Registrar o campo faltante.
2. Procurar campo equivalente.
3. Criar adaptação no service.
4. Não espalhar fallback pela UI.
5. Documentar pendência ao final da etapa.
