# Relatório SGP Strata

Painel **Streamlit** de gestão de pavimentos (metodologia **Paragon** e matriz **DNIT**),
que transforma os dados técnicos já processados pelo SGP (Sigma DNIT-RO) numa jornada de
decisão executiva:

```
Visão geral → Diagnóstico → Soluções → Cenário econômico → Projeção
   (rede)      (condição)   (o que fazer)  (quanto custa)   (evolução)
```

Este README concentra **(1) como colocar o sistema para funcionar** e **(2) a
especificação técnica das regras de negócio** implementadas (o que hoje está *hardcoded*
no código) e a **proposta de Versão 2** (parametrização no banco do SGP).

> **Fora de escopo deste documento:** assistente IAGON (chat de IA embutido nas telas).

---

# PARTE I — Como fazer funcionar

## 1. Pré-requisitos

| Item | Detalhe |
|---|---|
| Python | 3.10+ (usa `venv` próprio) |
| MySQL | banco **`sigma_dnitro`** (v1) / `sigma_dnitro_backup` (ambiente gestão) — **somente leitura** |
| Redis | cache (opcional; há *fallback* in-memory, mas produção usa Redis) |
| Google Maps API | opcional — chave com **Maps Embed API** habilitada, para o Street View ao clicar no mapa |
| Servidor | Linux + systemd + nginx (produção); roda como usuário **`www-data`** |

## 2. Instalação

```bash
cd /var/www/relatorio-sgp-strata

# ambiente virtual + dependências
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Configuração — `.env`

```bash
cp .env.example .env
```

Preencha as credenciais:

```env
MYSQL_HOST=127.0.0.1
MYSQL_PORT=3306
MYSQL_DB=sigma_dnitro
MYSQL_USER=seu_usuario
MYSQL_PASSWORD=sua_senha

GOOGLE_MAPS_API_KEY=chave_com_maps_embed_api   # opcional (Street View)
```

> ⚠️ **Permissão do `.env` (gotcha real):** o serviço roda como **`www-data`** e o `.env`
> tem permissão restrita (`640`). Se você **editar o `.env` como root**, o `www-data`
> deixa de conseguir lê-lo e o app quebra. Sempre faça `chown www-data:www-data .env`
> depois de editar como root.

## 4. Execução

### Desenvolvimento (manual)

```bash
source venv/bin/activate
streamlit run app.py --server.port 8501 --server.address 127.0.0.1
```

### Produção (systemd + nginx)

O serviço já está instalado como **`relatorio-sgp-strata.service`**:

```ini
# /etc/systemd/system/relatorio-sgp-strata.service (resumo)
[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/relatorio-sgp-strata
Environment="HOME=/var/www/relatorio-sgp-strata"
ExecStart=/var/www/relatorio-sgp-strata/venv/bin/streamlit run app.py \
          --server.port 8501 --server.address 127.0.0.1 --server.headless true
Restart=always
```

O **nginx** faz o proxy reverso (site `relatorio-ro.gestaovias.com.br`) para
`127.0.0.1:8501`.

Comandos de operação:

```bash
systemctl restart relatorio-sgp-strata     # reiniciar
systemctl status  relatorio-sgp-strata     # status
journalctl -u relatorio-sgp-strata -f      # logs ao vivo
curl -sS http://127.0.0.1:8501/_stcore/health   # healthcheck (espera "ok")
```

## 5. Cache (Redis) — comportamento importante

- O cache usa prefixo **`sgp:<MYSQL_DB>:`**, isolando `sigma_dnitro` de `sigma_dnitro_backup`
  (podem compartilhar o mesmo Redis).
- **Invalidação automática:** `ensure_fresh_data()` roda a cada carga e limpa o cache
  quando a assinatura dos cenários muda no banco (count + `MAX(updated_at)` + `MAX(id)` de
  `analise_gerencial_dados_trechos`). Não é preciso reiniciar quando os **dados** mudam.
- ⚠️ **Ao trocar `MYSQL_DB`** (apontar para outro banco): reiniciar **não basta** — é
  preciso **flush do cache Redis** (chaves `sgp:`), senão o app serve dados do banco antigo.

## 6. Troubleshooting

| Sintoma | Causa / correção |
|---|---|
| App não sobe após reboot / porta 80 | O **apache2** costuma tomar a `:80` antes do nginx e derrubar os sites. Mantê-lo `disabled`; conferir o proxy nginx antes do app. |
| App não lê o banco após editar `.env` | `.env` editado como root ficou ilegível para `www-data` → `chown www-data:www-data .env`. |
| Dados desatualizados após trocar de banco | Flush do Redis (prefixo `sgp:`), não só `restart`. |
| Street View não abre no mapa | `GOOGLE_MAPS_API_KEY` ausente/sem **Maps Embed API**. |

---

# PARTE II — Requisitos técnicos e regras de negócio

> Especificação do que o módulo faz e das regras que hoje estão escritas **"na mão" no
> código**. Muitas delas (troca de nome de solução, cores, priorização, custos) deveriam
> viver **no banco do SGP** como parametrização — ver a proposta de V2 na Parte III.

## 7. Arquitetura e stack

### 7.1 Stack

| Camada | Tecnologia |
|---|---|
| App | **Streamlit 1.32** (Python) |
| Dados | **Pandas 2.2 / NumPy 1.26** |
| Banco | **MySQL** via **PyMySQL 1.1** (`DictCursor`); SQLAlchemy disponível mas o acesso real é PyMySQL direto |
| Cache | **Redis** com *fallback* in-memory |
| Exportação | **XlsxWriter** (Excel), **ReportLab** (PDF do plano de trabalho) |
| Mapas | Leaflet via HTML + **Google Maps Embed API** (Street View) |
| Deploy | systemd (`relatorio-sgp-strata`) como **www-data**, atrás de **nginx** |

### 7.2 Regra de arquitetura

```
page  →  service  →  dataframe  →  component  →  layout
```

- **`app.py`** (~7.470 linhas) — monta as telas, roteia por `?page=` na URL, e concentra
  a maioria das **regras de negócio de apresentação** + todo o CSS.
- **`services/overview_service.py`** (~2.518 linhas) — toda leitura do banco, SQL e
  transformação em DataFrame. **Nenhum SQL fica nas páginas.**
- **`components/`** — `maps/`, `charts/`, `cards/`, `layout/`.
- **`core/constants.py`** — menu, rodovias-fallback, títulos.
- **`utils/colors.py`** — paleta base da UI.
- **`src/database/mysql_connection.py`** — conexão MySQL.
- **`services/cache.py`** — cache Redis com prefixo por banco.

> **Dívida técnica:** apesar da regra "não colocar regra de negócio na página", na prática
> **`app.py` concentra a maioria das constantes de negócio** (custos, pesos, cores,
> estratégias). A V2 deve extrair isso.

### 7.3 Roteamento das telas

- Navegação por **query param** `?page=<key>` (a sidebar gera `<a href="?page=...">` a
  partir de `MENU_ITEMS`; sem callbacks — clicar recarrega).
- `page` default = `overview`. Chaves: `visaogeral`, `overview`, `solucoes`, `cenario`,
  `projecao`, `risco` (IAGON — fora de escopo).

## 8. Modelo de dados — o que o relatório lê do SGP

Schema `sigma_dnitro`, **somente-leitura**.

| Tabela | Papel |
|---|---|
| `analise_gerencial_dados_trechos` | Análises/cenários; campo **`tipo_matriz`** roteia Paragon × DNIT |
| `analise_gerencial_ciclos` | Ciclos (compõem a chave de cenário `analise_id:ciclo_id`) |
| `analise_gerencial_intervencoes_iap` | **Núcleo Paragon:** `iapa`, `solucao_corretiva_final` (OK…REC), `solucoes` (JSON), ICDS/ICDP/ICDE |
| `analise_gerencial_intervencoes_dnit` | **Núcleo DNIT:** `solucoes` (JSON com `tipoNome`/`tipoId`) |
| `analise_gerencial_segmento_pistas` | Segmentos (km inicial/final, extensão, rodovia) |
| `analise_gerencial_roughness` | IRI (`iria`, `intervencao_irib`) |
| `analise_gerencial_igg` | IGG (`igga`, `situacao_igga`) |
| `analise_gerencial_desempenho_pavimento` | `vmda` (tráfego), `dadm` (deflexão admissível) |
| `analise_gerencial_parametros_iniciais` | `d0` (deflexão Dc) |
| `analise_gerencial_orcamentos` | **Custos reais** (JSON `solucoes.orcamento`) |
| `matriz_limites`, `matriz_limite_intervencao`, `intervencoes` | **Matriz de decisão DNIT** (`matriz_id = 5` = "Matriz Revitaliza DNIT/RO") |
| `pista_shape` | Código SNV/SRE por faixa de km |
| `principal_levantamentos`, `levantamento_importacoes` | Geometria real (pontos WKT do levantamento IRI) |

> **Relevante para a V2:** o SGP **já parametriza a decisão DNIT no banco**
> (`matriz_limites`). É o **lado Paragon e a camada de apresentação** que estão hardcoded.

## 9. O eixo Paragon × DNIT (Matriz Cadastrada)

Um **único seletor "Tipo de Matriz"** roteia para dois pipelines paralelos
(`app.py:428-433`, `_DIAGNOSIS_TO_MATRIX`).

| Aspecto | **Paragon** | **DNIT / "Matriz Cadastrada"** |
|---|---|---|
| `tipo_matriz` | `'Paragon'` | `'Matriz Cadastrada'` |
| Tabela de solução | `intervencoes_iap` (`solucao_corretiva_final`: OK…REC) | `intervencoes_dnit` (`solucoes` JSON) |
| Condição | IAP + ICDS/ICDP/ICDE | IRI + IGG + Dc/Dadm |
| Nome da solução | Dicionário **hardcoded** `_SOLUTION_LABELS` | Nome do banco + **heurística de string** `_dnit_solution_group` |
| Decisão | (solução já gravada) | `matriz_limites` `matriz_id=5` (**parametrizada no banco**) |

Há uma 3ª opção — **Comparativo Paragon × DNIT** — só na tela de Cenário econômico. Cada
seção decide o pipeline comparando o `diagnosis` (funções sufixadas `_dnit_*`).

> **Fallback:** hoje só a **BR-429** tem dados DNIT gravados; as demais caem no Paragon.

## 10. As 5 seções (requisitos funcionais)

Widgets de topo: **R** = Rodovia · **M** = Tipo de Matriz · **C** = Cenário.

### 10.1 Visão geral — panorama da rede (`visaogeral`)
- **Topo:** só **M**. **Dados:** itera todas as rodovias; horizonte fixo **8 anos**.
- **Componentes:** cards TRECHOS PRIORITÁRIOS (Crítica+Alta) e CUSTO TOTAL · mapa da malha · ranking de rodovias · custo por rodovia.
- **Regras:** prioritário = *Crítica*/*Alta*; km ruim IAP = `IAP < 2.5`; km ruim IRI = `IRI > 4`.

### 10.2 Diagnóstico — condição da rodovia (`overview`)
- **Topo:** **R + M + C** (C multiselect, compara sentidos/cenários).
- **Paragon:** 4 cards (IAP MÉDIO, % CRÍTICOS, KM CRÍTICOS, EXTENSÃO) · donut IAP · diagrama linear IAP (slider km) · expander ICDS/ICDP/ICDE.
- **DNIT:** 3 cards (IRI, IGG, % IRI CRÍTICO > 4) · mapa · 2 donuts · diagrama linear DNIT.
- **Regras:** IAP médio = `SUM(extensão×iapa)/SUM(extensão)/100`; **crítico = `solucao_corretiva_final IN ('RPS+REF','REC')`** (para bater com o Power BI); cor do mapa vem do conceito da solução, não do valor numérico.

### 10.3 Soluções — o que fazer e onde (`solucoes`)
- **Topo:** **R + M + C** (multiselect).
- **Componentes:** filtros · mapa por solução (esconde OK) · distribuição de soluções · tabela paginada · **Exportar Excel**.
- **Filtros Paragon:** SRE, Conceito IAP, Tipo de solução · paginação 25/50/100/Todos.
- **Regras:** aqui aparece a **troca de nome** (`_SOLUTION_LABELS` + regex *Microrrevestimento→Recarga Superficial*) e as **cores por solução** (`_solution_color`).

### 10.4 Cenário econômico — quanto custa (`cenario`)
- **Topo:** **R + M** (sentido escolhido na página). Única tela com **Comparativo Paragon × DNIT**.
- **Widgets:** sliders **Orçamento anual**, **Horizonte**, **Nível de prioridade (1–10)**.
- **Componentes:** 4 cards (NECESSIDADE, COBERTURA, ATENDIDOS, FALTANTE) · mapa · custo/ano · custo/solução · tabela de prioridade · **Plano de trabalho (PDF)**.
- **Regras (`_simulate_economic_scenario`):** ano-base **2026**, horizonte default **8**; aloca por prioridade (Executa/Backlog); IAP pós-obra **clipado ≥ 4,1**; **custo evitado = 35%** do executado; estratégia sempre **"Balanceada"**; custo = banco ou fallback paramétrico (§14).

### 10.5 Projeção — como evoluirá (`projecao`)
- **Topo:** **R + M + C**.
- **Paragon** ("Solução × Vida útil"): gráfico **ILUSTRATIVO** das 4 famílias no tempo, com a família **recomendada por trecho** destacada. Widgets: SRE + Horizonte [10/15/20].
  - ⚠️ **A recomendação por trecho é REAL** (matriz Paragon, `SNV == SRE`); **espessura, vida útil e curvas são valores típicos de engenharia, não existem no banco** (`_SOL_FAMILIES`, §14).
- **DNIT:** cronograma anual por SRE (chips) + custo/ano + projeção de IRI por SRE.

## 11. Regras hardcoded — Terminologia e Cores

### 11.1 Código de solução → nome exibido — `overview_service.py:81` `_SOLUTION_LABELS`

| Código | Nome exibido |
|---|---|
| `OK` | Sem intervenção |
| `RL` | Reparo localizado |
| `RL+RS` | Reparo localizado + Recarga Superficial |
| `RL+REF` | Reparo localizado + reforço |
| `RPS` | Fresagem e recomposição |
| `RPS+REF` | Fresagem e recomposição + reforço |
| `REC` | Reconstrução |

### 11.2 Renomeação de terminologia — `overview_service.py:169` `_normalize_solution_label`

```python
# 'Microrrevestimento' → 'Recarga Superficial' (1 ou 2 letras 'r')
re.sub(r"[Mm]icrorr?evestimento", "Recarga Superficial", name)
```

Substituição textual aplicada ao nome do dicionário **e** ao `tipoNome` do banco.
⚠️ **Só no Paragon** — no DNIT a solução mantém "Microrrevestimento" (inconsistência).

### 11.3 Código → conceito IAP (Quadro 37 DNIT) — `_IAP_INTERVENTION_TO_CLASS`

`OK→Excelente · RL→Bom · RL+RS→++ Regular · RL+REF→+ Regular · RPS→- Regular · RPS+REF→Mau · REC→Péssimo`

### 11.4 Paleta de cores (repetida em ≥4 arquivos)

**Classes IAP** (`overview_service.py:30`, `overview_map.py:12`, `linear_diagram.py:24`):

| Classe | Cor | | Classe | Cor |
|---|---|---|---|---|
| Excelente | `#00c2e8` | | - Regular | `#fff200` |
| Bom | `#00a651` | | Mau | `#f2a51a` |
| ++ Regular | `#b6d7a8` | | Péssimo | `#d71920` |
| + Regular | `#f4f1a6` | | CA | `#000000` |

`CA` não é nível da escala IAP: vem da tabela de códigos do cliente
(`_IAP_CODE_GROUPS`, sem valor numérico). Ficou sem cor própria até 08/2026 e caía
no fallback `#fff200` de quem consulta a paleta, saindo idêntica a `- Regular`.

**Cores por solução** — duas fontes que precisam concordar: `_IAP_INTERVENTION_COLORS`
(por código, `overview_service.py:50`) e `_solution_color()` (por **substring do nome**,
`app.py:699` — frágil: renomear quebra a cor).

**Classes de condição:** Excelente `#00c2e8` · Bom `#00a651` · Regular `#fff200` · Mau `#f2a51a` · Péssimo `#d71920`.

### 11.5 Cor do mapa (numérica vs. por solução)

`_classify_iap_for_map`: **se o trecho tem solução, a cor vem do conceito da solução**;
só na ausência usa a faixa numérica. (Um trecho `REC` com `iapa=2.25` seria "- Regular"
numericamente, mas no Power BI é `REC` = Péssimo — regra real, não bug.)

## 12. Regras hardcoded — Limiares de classificação

### 12.1 IAP → classe (`_classify_iap`; **também replicado em SQL**)

| Faixa (iapa/100) | Classe |
|---|---|
| ≥ 4,01 | Excelente |
| ≥ 3,01 | Bom |
| ≥ 2,51 | ++ Regular |
| ≥ 2,01 | - Regular |
| ≥ 1,01 | Mau |
| < 1,01 | Péssimo |

⚠️ **Inconsistência:** esta função numérica **não gera "+ Regular"** (embora exista na
legenda). O mesmo `CASE WHEN` está **duplicado em SQL** dentro de
`_get_iap_extraction_from_database` — dois lugares para manter em sincronia.

### 12.2 Condição (ICDS/ICDP/ICDE, escala 0–5)
≥4,5 Excelente · ≥3,5 Bom · ≥2,5 Regular · ≥1,5 Mau · <1,5 Péssimo.

### 12.3 Metas IAP
`IAP_META = 2.5` (crítico) · `IAP_ATENCAO = 3.5` (atenção).

### 12.4 Limiares DNIT
- **IRI:** ≤2,0 Ótimo · ≤2,7 Bom · ≤3,5 Regular · ≤4,6 Ruim · senão Péssimo.
- **IGG** (DNIT 006/2003): ≤20 Ótimo · ≤40 Bom · ≤80 Regular · ≤160 Ruim · senão Péssimo.
- **Zona de cor por IRI:** ≤3 · 3–4 · 4–5,5 · >5,5.
- **Estrutural:** `Dc > Dadm` ⇒ "Reforço (Dc>Dadm)".

## 13. Regras hardcoded — Priorização (`services/prioritization.py`)

### 13.1 IPT — Índice de Priorização Técnica (Paragon)

Por segmento; o SNV herda o **pior** (menor IPT = mais crítico).

```
IPT = 10 × ( 0,50·(1 − VMDA_n) + 0,30·ICDS_n + 0,20·ICDP_n )
```

| Componente | Peso | Normalização | Sentido |
|---|---|---|---|
| VMDA (tráfego) | **0,50** | Logarítmica | **Inverso** (`1 − VMDA_n`) |
| ICDS (superfície) | **0,30** | Linear | Direto |
| ICDP (profundidade) | **0,20** | Linear | Direto |

Nível final 1–10 = re-normalização min-max do IPT do pior segmento entre os SNVs.

### 13.2 Faixas de classificação (escala invertida, ≤ valor)
≤3 **Prioridade Crítica** · ≤5 **Alta** · ≤7 **Média** · >7 **Baixa**.

### 13.3 Versão DNIT
Sem VMDA/IAP: **IRI (0,60) + IGG (0,40)**; blend técnico/econômico **0,60/0,40**.

> Todos os pesos, normalizações, sentidos e cortes de faixa são **constantes Python**.

## 14. Regras hardcoded — Custos, econômico e famílias

### 14.1 Custo paramétrico por km (fallback) — `app.py:1232` `_ECONOMIC_SOLUTION_COST_KM`

| Código | R$/km | | Código | R$/km |
|---|---|---|---|---|
| OK | 0 | | RPS | 680.000 |
| RL | 180.000 | | RPS+REF | 920.000 |
| RL+RS | 280.000 | | REC | 1.250.000 |
| RL+REF | 420.000 | | | |

Usado só quando não há orçamento no banco; marca origem `Banco`/`Paramétrico`/`Sem custo`.

### 14.2 Constantes econômicas — `app.py:1243-1252`, `:1476`
Ano-base **2026** · horizonte default **8** · **custo evitado = 35%** · IAP pós-obra **clip 4,1** · estratégia usada = **"Balanceada"** (existem Corretiva/Preventiva, não expostas).

### 14.3 Catálogo ilustrativo de famílias (Projeção) — `app.py:4236` `_SOL_FAMILIES`
**Valores típicos de engenharia, NÃO vêm do banco:**

| Família | Cor | Espessura | Vida | R$/km |
|---|---|---|---|---|
| Microrrevestimento | `#00a651` | 2,0 cm | 5 anos | 95.000 |
| Fresagem + recomposição | `#fff200` | 6,5 cm | 8 anos | 285.000 |
| Reforço estrutural | `#f2a51a` | 12,0 cm | 11 anos | 740.000 |
| Reconstrução | `#d71920` | 30,0 cm | 18 anos | 2.500.000 |

⚠️ **Dois catálogos de custo/km incoerentes:** §14.1 (cenário) vs. §14.3 (projeção) —
ex.: Reconstrução 1,25 mi vs. 2,5 mi. A V2 deve ter **um único catálogo**.

### 14.4 Severidade de solução — `app.py:3875` `_SOLUTION_SEVERITY`
Reconstrução > Fresagem e recomposição > Reforço > Microrrevestimento > Reparo localizado
(define qual solução "ganha" a cor do ano).

### 14.5 Valores *fake* / demonstração (remover na V2)
`plan_cost_mi = 51.8`, `last_update_minutes = 12`, distribuição fallback (RL+RS 38,2% /
RPS 60,7% / REC 1,1%) quando não há composição real.

## 15. Diagnóstico da dívida técnica

1. **Acoplamento a código** — renomear solução, trocar cor, ajustar peso/custo exige
   editar `.py`, reiniciar (`www-data`) e limpar cache, em vez de um `UPDATE`.
2. **Duplicação** — paleta em ≥4 arquivos; **dois** catálogos de custo incoerentes;
   limiares de IAP em Python **e** SQL.
3. **Fragilidade por string** — `_solution_color`/`_dnit_solution_group` casam por
   substring; renomear quebra silenciosamente.
4. **Inconsistência entre trilhas** — Paragon renomeia Microrrevestimento, DNIT não.
5. **Sem multi-tenant** — outro órgão/contrato não tem como ter config própria sem fork.
6. **Regra de negócio na camada de apresentação** — contra o próprio `AGENTS.md`.
7. **Valores fake** misturados com dados reais.

**O que já está certo (manter):** custo real vem do banco (`analise_gerencial_orcamentos`);
decisão DNIT já parametrizada (`matriz_limites`); cache invalida sozinho por assinatura.

---

# PARTE III — Proposta de Versão 2 (parametrização no SGP)

## 16. Princípio

> **Toda regra que varia por cliente/órgão/contrato ou por metodologia sai do código e
> vira linha de tabela no banco do SGP.** O relatório passa a ser um **renderizador** de
> configuração + dados, sem conhecer nomes, cores, pesos ou custos.

Três camadas a mover: **A. Catálogo de soluções** · **B. Escalas de classificação** ·
**C. Parâmetros de método** — todas escopadas por **tenant** (órgão/contrato) e
**metodologia**, com *default* herdado (`tenant_id = 0`).

## 17. Modelo de dados proposto (DDL de referência)

```sql
-- A. Catálogo de soluções
-- (substitui _SOLUTION_LABELS, _IAP_INTERVENTION_*, _solution_color,
--  _ECONOMIC_SOLUTION_COST_KM, _SOL_FAMILIES, _SOLUTION_SEVERITY)
CREATE TABLE rel_catalogo_solucao (
  id             INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id      INT NOT NULL DEFAULT 0,
  metodologia    ENUM('Paragon','DNIT') NOT NULL,
  codigo         VARCHAR(16)  NOT NULL,   -- OK, RL, RL+RS, ... / tipoId DNIT
  nome_exibicao  VARCHAR(120) NOT NULL,   -- "Reparo localizado + Recarga Superficial"
  familia        VARCHAR(40)  NULL,       -- micro/fresagem/reforco/recon
  conceito_iap   VARCHAR(20)  NULL,       -- Excelente..Péssimo (mapa)
  cor_hex        CHAR(7)      NOT NULL,   -- #d71920
  ordem_severidade SMALLINT   NOT NULL,   -- 0 = mais severa
  intensidade    SMALLINT     NOT NULL,   -- 0..6
  custo_km_param DECIMAL(14,2) NULL,      -- fallback sem orçamento
  espessura_cm   DECIMAL(6,2) NULL,       -- ilustrativo (projeção)
  vida_util_anos SMALLINT     NULL,
  ativo          TINYINT(1) NOT NULL DEFAULT 1,
  UNIQUE KEY (tenant_id, metodologia, codigo)
);

-- B. Faixas de classificação
-- (substitui _classify_iap/_condition/_iri/_igg + o CASE em SQL)
CREATE TABLE rel_classe_condicao (
  id          INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id   INT NOT NULL DEFAULT 0,
  indicador   ENUM('IAP','CONDICAO','IRI','IGG','ZONA_IRI') NOT NULL,
  ordem       SMALLINT NOT NULL,
  rotulo      VARCHAR(20) NOT NULL,       -- "++ Regular", "Ótimo"...
  limite_inf  DECIMAL(8,3) NULL,          -- inclusivo
  limite_sup  DECIMAL(8,3) NULL,
  cor_hex     CHAR(7) NOT NULL,
  UNIQUE KEY (tenant_id, indicador, ordem)
);

-- C1. Parâmetros da priorização (substitui os PESO_* de prioritization.py)
CREATE TABLE rel_param_priorizacao (
  id           INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id    INT NOT NULL DEFAULT 0,
  metodologia  ENUM('Paragon','DNIT') NOT NULL,
  indicador    VARCHAR(16) NOT NULL,      -- VMDA, ICDS, ICDP, IRI, IGG
  peso         DECIMAL(5,3) NOT NULL,     -- soma 1.0 por metodologia
  normalizacao ENUM('log','linear') NOT NULL,
  sentido      ENUM('direto','inverso') NOT NULL,
  UNIQUE KEY (tenant_id, metodologia, indicador)
);

-- C2. Faixas do nível de prioridade (substitui _FAIXAS_PRIORIDADE)
CREATE TABLE rel_faixa_prioridade (
  id          INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id   INT NOT NULL DEFAULT 0,
  metodologia ENUM('Paragon','DNIT') NOT NULL,
  nivel_ate   SMALLINT NOT NULL,          -- 3,5,7
  rotulo      VARCHAR(30) NOT NULL        -- "Prioridade Crítica"...
);

-- C3. Parâmetros econômicos e de método (chave/valor tipado)
CREATE TABLE rel_param_config (
  id         INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id  INT NOT NULL DEFAULT 0,
  chave      VARCHAR(60) NOT NULL,        -- ano_base, horizonte_default,
                                          -- pct_custo_evitado, iap_meta,
                                          -- iap_atencao, iap_pos_intervencao,
                                          -- estrategia_padrao, critico_solucoes
  valor      VARCHAR(255) NOT NULL,
  tipo       ENUM('int','decimal','string','json') NOT NULL,
  UNIQUE KEY (tenant_id, chave)
);

-- D. De/para de terminologia (substitui _normalize_solution_label)
CREATE TABLE rel_terminologia (
  id         INT PRIMARY KEY AUTO_INCREMENT,
  tenant_id  INT NOT NULL DEFAULT 0,
  de         VARCHAR(120) NOT NULL,       -- "Microrrevestimento"
  para       VARCHAR(120) NOT NULL,       -- "Recarga Superficial"
  aplica_em  ENUM('solucao','indicador','geral') NOT NULL DEFAULT 'solucao'
);
```

> **Reaproveitamento:** o DNIT já tem `intervencoes` + `matriz_limites`. Recomendo
> **unificar** as duas trilhas sob `rel_catalogo_solucao` (matando a inconsistência
> Paragon×DNIT) — ou, no mínimo, adicionar colunas de apresentação a `intervencoes`.

## 18. Camada de acesso no relatório

Criar `services/config_service.py` (funções cacheadas com o `@cached` já existente) que
**substitui as constantes 1-para-1**:

```python
solucao = get_catalogo(tenant, "Paragon")   # code -> {nome, cor, custo_km, familia...}
nome    = solucao[cod]["nome_exibicao"]      # era _SOLUTION_LABELS[cod] + regex
cor     = solucao[cod]["cor_hex"]            # era _solution_color()
faixa   = classificar(tenant, "IAP", valor)  # era _classify_iap() (Python + SQL)
pesos   = get_pesos(tenant, "Paragon")       # era PESO_VMDA/ICDS/ICDP
econ    = get_config(tenant)                  # ano_base, horizonte, pct_custo_evitado...
```

Regras de ouro:
- **Uma fonte da verdade** — eliminar as cópias de paleta e o `CASE WHEN` de IAP em SQL.
- **Fallback para `tenant_id=0`** quando o tenant não sobrescreve.
- **Seed = valores atuais** (§11–14) → virada sem mudança visual.
- **Cache invalida no `UPDATE`** — estender `ensure_fresh_data()` para incluir
  `MAX(updated_at)` das tabelas `rel_*`.

## 19. UI de configuração no SGP

Adicionar menu **"Parametrização do Relatório"** com abas **Soluções** (A + D),
**Escalas** (B), **Priorização** (C1/C2) e **Econômico** (C3), escopadas por
órgão/contrato — o próprio gestor troca nome/cor/peso/custo sem acionar o desenvolvimento.

## 20. Roadmap incremental

1. **Catálogo de soluções (A + D)** — mata troca de nome/cor, unifica Paragon/DNIT. *(maior valor, menor risco)*
2. **Escalas de classificação (B)** — remove duplicação Python/SQL.
3. **Custos e econômico (§14 → A/C3)** — unifica os dois catálogos de custo.
4. **Priorização (§13 → C1/C2)** — metodologia por cliente.
5. **Remover valores fake (§14.5)** + UI de parametrização.
6. **Projeção** — decidir o que vira real (recomendação já é) vs. ilustrativo (espessura/vida).

## 21. Anexo — mapa "onde está cada regra hoje"

| Regra | Arquivo : referência | Vai para (V2) |
|---|---|---|
| Nome da solução | `overview_service.py:81` `_SOLUTION_LABELS` | `rel_catalogo_solucao.nome_exibicao` |
| Microrrevestimento→Recarga Superficial | `overview_service.py:169` | `rel_terminologia` |
| Código → conceito IAP | `overview_service.py:60` | `rel_catalogo_solucao.conceito_iap` |
| Cores classes IAP | `overview_service.py:30`, `overview_map.py:12`, `linear_diagram.py:24` | `rel_classe_condicao.cor_hex` |
| Cor por solução | `app.py:699`; `overview_service.py:50` | `rel_catalogo_solucao.cor_hex` |
| Limiares IAP | `overview_service.py:134` + SQL `:441` | `rel_classe_condicao` |
| Limiares condição/IRI/IGG | `overview_service.py:156/1166/1179` | `rel_classe_condicao` |
| Meta IAP (2,5/3,5) | `overview_service.py:1143` | `rel_param_config` |
| Pesos de priorização | `prioritization.py:49-55, 365` | `rel_param_priorizacao` |
| Faixas de prioridade (3/5/7) | `prioritization.py:60` | `rel_faixa_prioridade` |
| Custo paramétrico/km | `app.py:1232` | `rel_catalogo_solucao.custo_km_param` |
| Ano-base/horizonte/35%/estratégia | `app.py:1243-1252, :1476` | `rel_param_config` |
| Famílias (espessura/vida/custo) | `app.py:4236` | `rel_catalogo_solucao` |
| Severidade de solução | `app.py:3875` | `rel_catalogo_solucao.ordem_severidade` |
| Regra de crítico (RPS+REF/REC) | `overview_service.py:378` (SQL) | `rel_param_config.critico_solucoes` |
| Agrupamento DNIT por string | `overview_service.py:1474` | `rel_catalogo_solucao` (DNIT) |
| Valores fake | `overview_service.py:1021, 1088` | remover |

---

*A Parte II descreve o estado atual (v1) tal como implementado; a Parte III é recomendação
de engenharia para a v2, não implementação existente.*
