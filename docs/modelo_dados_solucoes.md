# Como o banco modela a solução de um segmento

Documento de referência levantado em 12/08/2026, medindo o banco de produção
(`sgp-ro`) nas rodovias BR-319, BR-364, BR-425 e BR-174, ciclo/ano 2027.

Existe porque o dashboard lê **três colunas diferentes** que descrevem a "solução"
de um segmento e as trata como se fossem a mesma coisa. Elas não são. Este
documento explica o que cada uma é, prova a explicação com medição, e lista o que
está errado hoje.

---

## 1. A ideia central, em uma frase

A análise é uma **simulação ano a ano** (na BR-364, 2027 a 2036). Para cada segmento
e cada ano o banco guarda a condição no **início do ano** (sufixo `a`), a condição no
**fim do mesmo ano** já degradada (sufixo `b`), e a **obra programada naquele ano**
(`solucao_corretiva_final` + `solucoes`). A obra executada zera a condição do ano
seguinte.

O dashboard colore o mapa pela condição do **início do ano** e monta a tabela pela
**obra programada**. A obra é dimensionada para a condição do **fim** do ano, não do
início — então as duas discordam legitimamente, e é por isso que filtrar um tipo de
solução mostrava outra coisa no mapa.

> **Correção:** a primeira versão deste documento descrevia `a` como "medido em
> campo" e `b` como "projetado para o ano da análise". Está errado. Ambos são do
> **mesmo ano**, e ambos mudam de ano para ano conforme a simulação avança.
> A prova está na §6.

---

## 2. As colunas de `analise_gerencial_intervencoes_iap`

Uma linha por segmento, por ciclo, por ano. As colunas vêm em famílias:

| família | colunas | significado |
|---|---|---|
| **A — início do ano** | `icdsa` `icdpa` `icdea` `d0a` `z_dea` `iapa` `conceito_iapa` `solucao_corretiva_a` | condição com que o segmento **entra** naquele ano |
| **B — fim do ano** | `icdsb` `icdpb` `icdeb` `d0b` `z_deb` `iapb` `conceito_iapb` `solucao_corretiva_b` | condição no **fim** do mesmo ano, já degradada |
| **após a obra** | `intervencao_iapb` `intervencao_icdsb` `intervencao_d0b` `intervencao_solucao_corretiva_b` … | como o segmento fica **depois** de intervir |
| **obra programada** | `solucao_corretiva_final`, `solucoes` (JSON) | o que foi de fato programado para aquele ano |
| **projeto da obra** | `espessura_reforco` `revestimento_reforco` `espessura_rev_rec` `material_rev_rec` `base_rec` `sub_base_rec` | dimensionamento |
| **rastreio** | `matriz_paragon_iap_id`, `created_at`, `updated_at` | qual linha da matriz gerou a solução |

Que `intervencao_solucao_corretiva_b` seja `OK` em quase toda linha com obra
programada confirma a leitura da família: **depois da intervenção, nada mais é
necessário**.

---

## 3. Como o código `iapa` é formado

`iapa` não é um número de IAP. É a **concatenação dos três índices de condição
arredondados**:

```
iapa = round(icdsa) · round(icdpa) · round(icdea)
iapb = round(icdsb) · round(icdpb) · round(icdeb)
```

Verificado em 6 de 6 linhas conferidas:

```
icdsb=4.0  icdpb=1.83  icdeb=2.96  ->  4,2,3  ->  iapb=423  ✓
icdsb=4.6  icdpb=3.09  icdeb=3.57  ->  5,3,4  ->  iapb=534  ✓
icdsb=3.3  icdpb=2.36  icdeb=3.22  ->  3,2,3  ->  iapb=323  ✓
icdsb=5.0  icdpb=3.86  icdeb=3.70  ->  5,4,4  ->  iapb=544  ✓
icdsb=3.9  icdpb=2.99  icdeb=3.57  ->  4,3,4  ->  iapb=434  ✓
icdsb=3.0  icdpb=2.88  icdeb=3.57  ->  3,3,4  ->  iapb=334  ✓
```

Atenção: é **arredondamento**, não truncamento. `4.6` vira `5`, não `4`.

---

## 4. A matriz Paragon está no banco — e nossa cópia tem erro

A tabela **`matriz_paragon_iap`** tem **125 linhas**, que são exatamente as
5 × 5 × 5 combinações de `icds` × `icdp` × `icde`, cada uma com
`solucao_corretiva_sigla` e `solucao_corretiva`. Há uma única matriz ativa
(`matriz_paragon_id = 1`), e cada segmento aponta para a linha que o gerou via
`analise_gerencial_intervencoes_iap.matriz_paragon_iap_id`.

O `_IAP_CODE_GROUPS` em `services/overview_service.py` é uma **transcrição manual
dessa tabela** — e está incompleta:

```
combinações que o BANCO classifica como CA:  441 442 451 452 541 542 551 552
o que o nosso código tem:                    441 442 451 452     542     552
faltando:                                    541 e 551
```

Os códigos **541** e **551** são `CA` no banco e o nosso código os trata como
**`REC` / Péssimo**. Consequência medida na BR-364: 15 a 16 segmentos aparecem como
"Péssimo / Reconstrução" quando o banco diz "Condição Anômala".

Isso também define o que ninguém sabia: **`CA` = "Condição Anômala"**, o texto está
em `conceito_iapa`. Não é uma classe de severidade — é a marca de uma combinação de
índices que a matriz considera inconsistente. Nesses segmentos, `solucao_corretiva_b`
e `solucao_corretiva_final` trazem `REC`.

Fora dos códigos CA, a matriz do nosso código reproduz `solucao_corretiva_a` em
**484 de 499** linhas da BR-364 — as 15 falhas são exatamente esse bug.

---

## 5. `solucao_corretiva_final` e o JSON `solucoes`

- `solucao_corretiva_final` é igual a `solucao_corretiva_b` sempre que está
  preenchida. É a obra **programada para aquele ano**.
- Quando é `NULL`, não há obra programada naquele ano para aquele segmento.
- O JSON `solucoes` está preenchido **exatamente** quando `final` está preenchida
  (BR-364: 250 de 499 linhas), e concorda com ela.

O JSON é a obra **itemizada**, com quantidade e tipo:

```json
[{"sigla":"RPS","tipoId":4,"tipoNome":"Fresagem e recomposição",
  "quantidades":15400.0,"intervencaoId":8,"quantidades_formatada":"15400 m²"},
 {"sigla":"REF","tipoId":3,"tipoNome":"Reforço",
  "quantidades":15400.0,"intervencaoId":7,"quantidades_formatada":"15400 m²"}]
```

É daqui que saem `Solução recomendada` (via `tipoNome`) e `Custo estimado`
(via `orcamento`) na tela de Soluções.

---

## 6. A simulação ano a ano, medida

Prova de que `a` e `b` são o mesmo ano e que a obra zera o ano seguinte — segmento
46474 da BR-364, todos os 10 anos da análise:

```
2027   A=+ Regular    B=Mau          FINAL=RPS+REF     <- obra executada
2028   A=Excelente    B=Excelente    FINAL=—           <- condição zerada
2029   A=Excelente    B=Excelente    FINAL=—
...
2034   A=Excelente    B=++ Regular   FINAL=—           <- volta a degradar
2035   A=++ Regular   B=++ Regular   FINAL=—
```

O salto de "+ Regular" para "Excelente" entre 2027 e 2028 só se explica pela obra de
2027. Logo `iapa` **não** é uma medição de campo fixa: é o estado do segmento no
início do ano selecionado, dentro da simulação.

Dentro de um mesmo ano, `B` nunca é melhor que `A`. Amostra da BR-364
(499 segmentos, ano 2027):

```
 93 seg   A: Excelente / OK        B: Excelente / OK        FINAL: —
 90 seg   A: Excelente / OK        B: Bom / RL              FINAL: —
 85 seg   A: - Regular / RPS       B: - Regular / RPS       FINAL: RPS
 43 seg   A: ++ Regular / RL+RS    B: - Regular / RPS       FINAL: RPS
 41 seg   A: ++ Regular / RL+RS    B: ++ Regular / RL+RS    FINAL: RL+RS
 29 seg   A: ++ Regular / RL+RS    B: ++ Regular / RL+RS    FINAL: —
 19 seg   A: Bom / RL              B: ++ Regular / RL+RS    FINAL: RL+RS
 16 seg   A: Péssimo / REC         B: Péssimo / REC         FINAL: REC
 16 seg   A: Condição Anômala / CA B: Péssimo / REC         FINAL: REC
```

Comparando a solução da matriz de `iapa` (início do ano) com a que a tela exibe:

```
BR-364:  iguais=433   a exibida é mais severa = 65   menos severa = 0
BR-425:  iguais=136   a exibida é mais severa = 25   menos severa = 0
```

**Zero casos na direção contrária, em 90 divergências.** Isso prova que não é erro
de dado: a obra é dimensionada para a condição do fim do ano, que é sempre igual ou
pior que a do início. Uma base corrompida erraria para os dois lados.

---

## 7. Os problemas concretos no dashboard

### 7.1 O mapa e a tabela leem fotografias diferentes — CORRIGIDO

O mapa coloria por `intervencao_iap` (derivado de `iapa`, foto A) e a tabela/filtro
usam `Solução recomendada` (do JSON, obra programada). Filtrar
"Fresagem e recomposição + Reforço" selecionava o segmento certo e o pintava como
`RL+REF`.

Corrigido por `_align_map_solution_to_table()` em `app.py`, que reescreve o código
do mapa a partir do nome da tabela.

> **Correção de uma versão anterior deste documento:** havia aqui um item afirmando
> que dois gráficos mostravam km diferentes para a mesma solução (composição por
> intervenção x distribuição da tela Soluções). Está errado: a `composition` por
> solução é calculada mas **nunca exibida** (ver §9-A). Os dois números eram cálculos
> válidos, mas só o do JSON chega à tela.

### 7.2 A tela mostra solução em segmento sem obra programada

`_solution_name(codigo, solucoes)` cai no rótulo da **matriz de A** quando o JSON
está vazio. Como o JSON só existe onde há obra programada, segmentos sem obra
aparecem na tela com a solução que a condição do início do ano pediria:

| rodovia | segmentos | com obra programada | exibidos com solução **sem** obra |
|---|---|---|---|
| BR-364 | 499 | 250 | **47** (34,14 km) |
| BR-319 | 169 | 58 | **20** (16,40 km) |
| BR-425 | 163 | 73 | **7** (8,64 km) |

Eles entram no `intervention_table`, no mapa, na distribuição e na contagem de
"com obra". O custo desses segmentos é R$ 0 — verificado, não há custo fantasma.

**E "sem obra programada" não significa "sem necessidade".** Quando `FINAL` é NULL,
o que `solucao_corretiva_b` pedia (BR-364, todos os anos):

```
corretiva_b = OK         -> 3151   nada a fazer mesmo
corretiva_b = RL+RS      ->  706   pedia obra, nada programado
corretiva_b = RL         ->  198   idem
corretiva_b = RL+REF     ->   23   idem
corretiva_b = RPS+REF    ->    1
corretiva_b = REC / RPS  ->    0   nunca ficam sem programação
```

Só as intervenções **leves** ficam sem programação, e as pesadas nunca. Isso tem cara
de regra (manutenção rotineira fora do plano de obras), não de falha — mas precisa de
confirmação de engenharia.

Há ainda uma terceira situação: `FINAL` pode vir com o valor explícito `'OK'` em vez
de NULL. Aparece só a partir de 2029 e cresce ao longo dos anos (2 em 2029, 31 em
2036). A diferença entre NULL e `'OK'` não está clara.

### 7.3 O KPI de km críticos usa o início do ano, não a obra programada

A regra é `SUM(extensao) where solução in ('RPS+REF','REC')` sobre o código de
`iapa` — a condição com que o segmento **entra** no ano selecionado. Pela obra
programada o número é outro:

```
BR-319   início do ano:  6,62 km (4,8%)    obra programada: 11,36 km (8,3%)
BR-364   início do ano: 32,18 km (8,5%)    obra programada: 39,24 km (10,4%)
BR-425   início do ano: 12,90 km (9,9%)    obra programada: 15,46 km (11,9%)
```

O card mostra o menor dos dois. Não é "ignorar o ano" — `iapa` respeita o ano
selecionado —, é escolher o início do ano em vez da obra. Corrigir o bug de 541/551
(item 4) empurra o número para **baixo** ainda mais, porque tira segmentos do balde
`REC`.

### 7.4 A mesma linha da tabela mistura A e B

A query de `_get_solution_table_from_database` seleciona `i.iapa` (início do ano) mas
`i.d0b`, `i.icdsb`, `i.icdpb` (fim do ano). Então a coluna IAP e as colunas
DEF/ICDS/ICDP da **mesma linha** descrevem momentos diferentes do mesmo ano.

### 7.5 `solucao_corretiva_a` e `conceito_iapa` são ignoradas

O banco já entrega a classe e a solução prontas nessas colunas. O dashboard
recalcula as duas a partir de uma transcrição manual da matriz — que é onde o erro
de 541/551 entrou. `solucao_corretiva_final` só é lida como *fallback* de
`_iap_solution_from_code`, e medi que esse fallback nunca é acionado: nenhuma linha
tem `iapa` fora da tabela de códigos.

---

## 8. O que fazer, em ordem de risco

1. **Corrigir 541 e 551 para CA** em `_IAP_CODE_GROUPS`. É erro de transcrição
   contra a matriz do banco, não decisão de produto. Muda a classe de ~16 segmentos
   na BR-364 e reduz o km crítico.
2. **Ler a matriz do banco** em vez de manter a cópia — `matriz_paragon_iap` tem as
   125 combinações, é versionada por `matriz_paragon_id` e cada segmento aponta para
   a linha que o gerou. Elimina a classe de bug do item 1 de vez.
3. **Decidir o que cada tela deve mostrar**, agora que os nomes existem: condição no
   início do ano (A), no fim do ano (B), ou obra programada (FINAL). Hoje as telas
   misturam as três sem dizer qual está exibindo. Rotular no título ou no subtítulo
   resolve metade do problema sem tocar em número nenhum.
4. **Separar "sem obra programada" de "sem necessidade"** (item 7.2). São coisas
   diferentes e hoje aparecem juntas.

Os itens 1 e 2 são correções. Os itens 3 e 4 mudam números de relatório e precisam
de decisão consciente.

---

## 9-A. Qual coluna cada visual usa hoje

Levantado percorrendo cada função de render até a query que a alimenta.

**Atenção a uma armadilha:** existem **três colunas chamadas `solucoes`**, em três
tabelas diferentes, e o dashboard chama todas de "Solução recomendada" no DataFrame.
A tela de Soluções e o Cenário econômico leem **tabelas distintas**.

| onde está | quem lê |
|---|---|
| `analise_gerencial_intervencoes_iap.solucoes` | tela Soluções, PDF, IAGON |
| `analise_gerencial_orcamentos.solucoes` | Cenário econômico |
| `analise_gerencial_intervencoes_dnit.solucoes` | telas da matriz DNIT |

Onde aparece "busca na matriz", o dashboard **não** consulta `matriz_paragon_iap` —
usa a transcrição manual `_IAP_CODE_GROUPS` em `services/overview_service.py`.

### Soluções

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Mapa — cor das linhas | `solucoes` → `tipoNome` *(antes da correção: `iapa` + busca na matriz)* | `analise_gerencial_intervencoes_iap` |
| Filtro "Tipo de solução" | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Tabela — "Solução recomendada" | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Tabela — "Custo estimado" | `solucoes` → `orcamento` | `analise_gerencial_intervencoes_iap` |
| Tabela — "IAP" | `iapa` + busca na matriz (valor) | `analise_gerencial_intervencoes_iap` |
| Tabela — cor e classe da linha | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Tabela — "DEF" | `d0b` | `analise_gerencial_intervencoes_iap` |
| Tabela — "ICDS" / "ICDP" | `icdsb`, `icdpb` | `analise_gerencial_intervencoes_iap` |
| Tabela — "IRI" | `iria` | `analise_gerencial_roughness` |
| Tabela — "IGG" | `igga` | `analise_gerencial_igg` |
| Tabela — "VMDA" | `vmda` | `analise_gerencial_desempenho_pavimento` |
| Tabela — "SNV" | `codigo` | `pista_shape` |
| Tabela — km e extensão | `km_inicial`, `km_final`, `extensao` | `analise_gerencial_segmento_pistas` |
| Distribuição por solução | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Distribuição por sentido | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Exportação Excel | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Mapa — geometria das linhas | geometria do trecho | `pista_shape` |

### Cenário econômico — **duas tabelas diferentes na mesma tela**

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Mapa do cenário — cor das linhas | `iapa` + busca na matriz | `analise_gerencial_intervencoes_iap` |
| Mapa por solução dominante | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Tabela de obras — coluna de solução | `iapa` + busca na matriz | `analise_gerencial_intervencoes_iap` |
| Alerta de custo faltante | `iapa` + busca na matriz | `analise_gerencial_intervencoes_iap` |
| "Solução recomendada" do orçamento | `solucoes` → `tipoNome` (ou `sigla`) | **`analise_gerencial_orcamentos`** |
| "Custo econômico" | `solucoes` → `orcamento` | **`analise_gerencial_orcamentos`** |
| Gráfico de custo por solução | `solucoes` → `tipoNome` | **`analise_gerencial_orcamentos`** |

O mapa e o alerta leem `analise_gerencial_intervencoes_iap`; o custo e o nome da
solução leem `analise_gerencial_orcamentos`. **Não corrigido.**

### Diagnóstico

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| KPI "Km críticos" e "% trechos críticos" | `iapa` + busca na matriz (solução `RPS+REF` ou `REC`) | `analise_gerencial_intervencoes_iap` |
| Rosca "Distribuição IAP" | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Diagrama linear — cor das faixas | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Mapa | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |

### Visão geral

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| KPIs de trecho crítico | `iapa` + busca na matriz | `analise_gerencial_intervencoes_iap` |
| Ranking e textos por solução | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Mapa | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |

### Projeção do IAP

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Curva exibida | `iapa` + busca na matriz (valor) | `analise_gerencial_intervencoes_iap` |
| Faixas de conceito | `iapa` + busca na matriz (classe); `conceito_iapa` como fallback | `analise_gerencial_intervencoes_iap` |
| Curva calculada e **não exibida** | `iapb` | `analise_gerencial_intervencoes_iap` |

### PDF do plano de trabalho

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Mapa e legenda | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Tabela e agrupamento por solução | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |

### IAGON

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Textos e plano de obra | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Mapa — filtro dos segmentos | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_iap` |
| Mapa — cor das linhas | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |

### Comparativo entre cenários

Não exibe solução corretiva como categoria, mas **todo o dinheiro que compara sai de
`analise_gerencial_orcamentos.solucoes` → `orcamento`**.

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Mapa técnico, lado Paragon — "Conceito IAP" | `iapa` + busca na matriz (classe) | `analise_gerencial_intervencoes_iap` |
| Mapa técnico, lado Matriz Cadastrada — "Classe do IRI" | `iria` | `analise_gerencial_roughness` |
| Mapa financeiro — "Custo total por SRE" | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |
| KPI "Necessidade total" | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |
| KPI "Orçamento faltante" | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |
| KPI "Cobertura financeira" | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |
| KPI "Trechos atendidos" | `extensao` + cobertura do orçamento | `analise_gerencial_segmento_pistas` + `analise_gerencial_orcamentos` |
| Barras de custo anual | `solucoes` → `orcamento` por `ano` | `analise_gerencial_orcamentos` |
| Tabela "Custo por trecho (SRE)" | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |
| Gráfico "IRI" | `iri_antes_intervencao` | view `vw_desempenho_pavimento_com_trecho` |
| Gráfico "Afundamento nas trilhas de roda" | `flechas_antes_intervencao` | view `vw_desempenho_pavimento_com_trecho` |
| Gráfico "FC2 + FC3" | `fc2_fc3_antes_intervencao` | view `vw_desempenho_pavimento_com_trecho` |
| Gráfico "Panelas" | `n_panelas_antes_intervencao` | view `vw_desempenho_pavimento_com_trecho` |

Duas observações sobre essa tela:

- As quatro colunas de métrica da view têm sufixo **`_antes_intervencao`** — são o
  estado do segmento antes de intervir, coerente com a família `intervencao_*` da
  tabela de intervenções.
- Os nomes dessas colunas são resolvidos **em tempo de execução** por `_pick_column`,
  lendo o `SHOW COLUMNS` da view. Se uma delas for renomeada ou sumir, o gráfico
  correspondente **desaparece silenciosamente**, sem erro na tela.

### Telas da matriz DNIT

| visual | coluna(s) lidas | tabela de origem |
|---|---|---|
| Solução recomendada e tabela | `solucoes` → `tipoNome` | `analise_gerencial_intervencoes_dnit` |
| Custo | `solucoes` → `orcamento` | `analise_gerencial_orcamentos` |

### Colunas que nenhum visual lê

`solucao_corretiva_a`, `solucao_corretiva_b`, `conceito_iapb`, `intervencao_iapb`,
`intervencao_conceito_iapb`, `intervencao_solucao_corretiva_b` e todas as demais
`intervencao_*`; `icdsa`, `icdpa`, `icdea`, `d0a`, `icdeb`, `z_dea`, `z_deb`;
`matriz_paragon_iap_id`; e a tabela `matriz_paragon_iap` inteira.

### `solucao_corretiva_final` — caso especial

Aparece no código como segundo argumento de
`_iap_solution_from_code(iapa, solucao_corretiva_final)`, mas só é usada quando `iapa`
não existe na matriz. Medido na BR-364 e BR-425: **zero linhas** caem nesse caso. Na
prática, **nenhum visual usa `solucao_corretiva_final`**.

### Quando `solucoes` vem vazio

"Solução recomendada" não fica em branco: cai no rótulo derivado de `iapa` + busca na
matriz. Então as linhas marcadas como `solucoes` acima leem `iapa` nesses casos — 47
segmentos na BR-364 em 2027, 20 na BR-319, 7 na BR-425.

### Calculado e nunca exibido

- `composition` de `_get_iap_extraction_from_database` (agrupamento por solução a
  partir de `iapa`): computado, devolvido e não consumido por nenhum render.
- `avg_before` da projeção (derivado de `iapb`): computado e não exibido.

### Pavimentação, Tráfego, Geotecnia

Não exibem solução corretiva. As roscas "Composição IRI / ATR / IGG" e a de tráfego
são de classe de condição e de veículo. (O Comparativo tem seção própria acima: também
não exibe solução, mas o dinheiro que compara vem de uma coluna `solucoes`.)

---

## 10. Perguntas para o engenheiro

Nenhuma destas se responde pelo código ou pelo banco — todas são de domínio.

1. **`CA` / "Condição Anômala".** A combinação é ICDS 4–5 (superfície boa a ótima)
   com ICDE 1–2 (estrutura ruim a péssima) — superfície nova sobre estrutura
   arruinada. O que o relatório deve mostrar num segmento CA: `CA`, ou a obra
   programada, que nesses casos é `REC`? E **CA entra no km crítico?**
2. **Qual coluna representa "a solução" em cada tela** — `solucao_corretiva_a`
   (início do ano), `solucao_corretiva_b` (fim do ano) ou `solucao_corretiva_final`
   + `solucoes` (obra programada)? Vale a pena responder por tela: mapa, tabela,
   distribuição, KPI de km crítico e cenário econômico.
3. **`FINAL` NULL com `corretiva_b` pedindo RL ou RL+RS** (~928 casos na BR-364).
   Manutenção rotineira fica fora do plano de obras de propósito, ou é corte de
   orçamento? Isso define se esses segmentos devem aparecer na tela de Soluções.
4. **`FINAL` NULL x `FINAL = 'OK'`** — qual a diferença? O `'OK'` explícito só
   aparece a partir de 2029.
5. **Km crítico** hoje é `RPS+REF` ou `REC` pela condição do início do ano. É essa a
   definição correta, ou deveria ser pela obra programada?
6. **A tabela mistura o IAP do início do ano com DEF/ICDS/ICDP do fim** (item 7.4).
   Isso é intencional ou é bug? O sintoma é verificável na tela: arredondando os
   índices exibidos na linha, o código IAP que sai é o do fim do ano, não o exibido.
7. **O IAP exibido não é contínuo.** É o valor tabelado da matriz, com apenas 7
   valores possíveis (1,0 · 2,0 · 2,5 · 2,75 · 3,0 · 4,0 · 5,0). O "IAP médio" é a
   média ponderada desses degraus. É isso que se espera do indicador, ou deveria ser
   um IAP contínuo?
8. **IRI e IGG vêm de outras tabelas** (`roughness.iria`, `igg.igga`) e o sufixo `a`
   aparece lá também. Essas tabelas seguem o mesmo padrão `a`/`b` de início e fim de
   ano? (Não verificado.)

---

## 9. Como reproduzir as medições

Os scripts usados estão fora do repositório (foram de investigação), mas as
consultas centrais são:

```sql
-- a matriz oficial
SELECT icds, icdp, icde, solucao_corretiva_sigla, solucao_corretiva
FROM matriz_paragon_iap WHERE deleted_at IS NULL ORDER BY icds, icdp, icde;

-- as três descrições de solução, lado a lado, para uma análise
SELECT i.iapa, i.conceito_iapa, i.solucao_corretiva_a,
       i.iapb, i.conceito_iapb, i.solucao_corretiva_b,
       i.solucao_corretiva_final, i.solucoes
FROM analise_gerencial_intervencoes_iap i
JOIN analise_gerencial_segmento_pistas sp ON sp.id = i.segmento_pista_id
WHERE sp.analise_gerencial_id = ? AND i.gerencial_ciclo_id = ? AND i.ano = ?;
```

Os `analise_gerencial_id` / `gerencial_ciclo_id` / `ano` de cada rodovia saem de
`get_iap_extraction(rodovia, year=..., scenario_key=...)`.
