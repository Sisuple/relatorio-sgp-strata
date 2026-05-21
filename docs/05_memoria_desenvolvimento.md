# Memória de Desenvolvimento — Diagnóstico Paragon

Data: 2026-05-19

## Contexto

Estamos desenvolvendo um relatório Streamlit para diagnóstico de pavimentos, seguindo a orientação do `AGENTS.md`:

```txt
page -> service -> dataframe -> component -> layout
```

A tela atual é o **Diagnóstico Paragon**. Também foi criado um seletor para futura tela **Diagnóstico DNIT**, ainda sem implementação de indicadores próprios.

## Arquivos principais alterados/criados

- `app.py`
  - Layout principal.
  - CSS global.
  - Topo com filtros.
  - Renderização dos cards, mapa, distribuição IAP e diagramas lineares.

- `services/overview_service.py`
  - Consulta de rodovias no banco.
  - Consulta de cenários Paragon.
  - Extração de métricas de IAP.
  - Extração de composição IAP por solução final.
  - Extração de segmentos para mapa.
  - Extração de dados para diagrama linear.

- `components/maps/overview_map.py`
  - Mapa Leaflet.
  - Geometrias reais do banco.
  - Cores por conceito IAP.
  - Zoom funcional.

- `components/charts/iap_distribution.py`
  - Donut de composição IAP.
  - Percentuais visíveis ao redor do gráfico.

- `components/charts/linear_diagram.py`
  - Diagrama Linear de Condição: ICDS, ICDP, ICDE.
  - Diagrama de IAP separado.
  - Legenda de conceitos e legenda de solução corretiva.

- `components/cards/metric_card.py`
  - Cards de métricas.

- `components/layout/sidebar.py`
  - Menu lateral conforme protótipo.

## Banco e tabelas usadas

Principais tabelas identificadas:

- `analise_gerencial_dados_trechos`
- `analise_gerencial_ciclos`
- `analise_gerencial_intervencoes_iap`
- `analise_gerencial_segmento_pistas`
- `segmento_view_mapa_base`
- `analise_segmentos_homogeneos`
- `segmento_homogeneos`

O app usa principalmente:

- `analise_gerencial_dados_trechos`
- `analise_gerencial_ciclos`
- `analise_gerencial_intervencoes_iap`
- `analise_gerencial_segmento_pistas`
- `segmento_view_mapa_base`

## Rodovias e cenários

Rodovias disponíveis no banco:

- `BR-364/RO`
- `BR-421/RO`
- `BR-429/RO`
- `BR-435/RO`

Para `BR-435/RO`, existem os dois cenários:

- `BR-435/RO (sh) Paragon`
- `BR-435/RO (1km) Paragon`

No seletor de cenários, o rótulo foi simplificado:

- `Segmento Homogêneo`
- `1km`

Internamente, o app continua usando a chave real do cenário:

```txt
analise_id:ciclo_id
```

Exemplo para BR-435/RO:

- `150:143` -> `BR-435/RO (sh) Paragon`
- `149:142` -> `BR-435/RO (1km) Paragon`

Para `BR-364/RO`, só existe cenário Paragon ativo de `1km`.

## Métricas dos cards

Cards atuais:

- `IAP MÉDIO`
- `% TRECHOS CRÍTICOS`
- `KM CRÍTICOS`
- `EXTENSÃO TOTAL`

Para BR-435/RO no cenário `Segmento Homogêneo`:

- IAP médio: `3.9739`, exibido como `3.97`
- Extensão total: `160.8 km`
- Crítico: `REC = 1.5 km`
- Percentual crítico: `1.1%`

### Regra atual de crítico

A regra foi ajustada para bater com a composição do Power BI:

```sql
solucao_corretiva_final IN ('RPS+REF', 'REC')
```

O percentual é calculado sobre a extensão dos trechos com `solucao_corretiva_final IS NOT NULL`, para alinhar com o gráfico de distribuição IAP.

## IAP médio

O IAP médio é ponderado por extensão:

```sql
SUM(sp.extensao * i.iapa) / SUM(sp.extensao) / 100
```

O campo `iapa` vem multiplicado por 100 no banco.

## Composição IAP / Donut

O gráfico **Distribuição IAP** replica a composição do Power BI por solução final:

```sql
solucao_corretiva_final
```

Para BR-435/RO `(sh)`:

- `RL+RS`: `51.16 km`, `38.2%`
- `RPS`: `81.18 km`, `60.7%`
- `REC`: `1.50 km`, `1.1%`

Observação importante:

O Power BI chama o bloco de **Composição IAP**, mas a composição usada é por solução/intervenção final, não por classe numérica direta do IAP.

## Mapa

O mapa usa geometrias reais de:

```txt
segmento_view_mapa_base
```

Foi corrigido um problema de zigue-zague filtrando linhas com salto grande de coordenadas.

Constante usada:

```python
_MAX_MAP_LINE_DEGREES = 0.03
```

### Cor do mapa

O mapa usa conceitos derivados da solução final para pintar igual ao quadro do IAP:

```txt
OK      -> Excelente
RL      -> Bom
RL+RS   -> ++ Regular
RL+REF  -> + Regular
RPS     -> - Regular
RPS+REF -> Mau
REC     -> Péssimo
```

Isso foi necessário porque o trecho `REC` da BR-435/RO tem `iapa = 2.25`, que numericamente cairia em `- Regular`, mas no relatório Power BI aparece como solução `REC`, equivalente a `Péssimo` no quadro.

## Diagrama Linear

Foram criados dois cards:

1. **Diagrama Linear de Condição**
   - `ICDS`
   - `ICDP`
   - `ICDE`

2. **Índice de Aptidão do Pavimento e Soluções Conceptivas**
   - `IAP`
   - Legenda de solução corretiva:
     - `OK`
     - `RL`
     - `RL+RS`
     - `RL+REF`
     - `RPS`
     - `RPS+REF`
     - `REC`

Campos usados:

- `icdsa`
- `icdpa`
- `icdea`
- `iapa`
- `solucao_corretiva_final`

Os campos `ICDS`, `ICDP` e `ICDE` já vêm na escala 0-5.
O campo `iapa` vem em escala 0-500 e é dividido por 100.

## Filtros no topo

Filtros atuais:

- `Diagnóstico`
  - `Diagnóstico Paragon`
  - `Diagnóstico DNIT`

- `Rodovias`
  - Carregado do banco.

- `Cenários`
  - Carregado do banco conforme a rodovia.
  - Exibe rótulos simplificados: `Segmento Homogêneo`, `1km`.

A tela `Diagnóstico DNIT` por enquanto mostra uma mensagem reservada.

## Git/GitHub

Foi criado repositório local:

```txt
/var/www/streamlit-app
```

Estado local:

```txt
branch: main
commit: 97e98dd first commit
remote: https://github.com/Sisuple/relatorio-sgp-strata.git
```

Problema encontrado:

O `git push` via terminal falhou por falta de autenticação GitHub no servidor:

```txt
fatal: could not read Username for 'https://github.com': No such device or address
```

Também foi verificado:

- `gh` não está instalado.
- Não há SSH key GitHub configurada.
- Não há credential helper/token configurado.

Pelo conector GitHub foi criado um commit remoto apenas com `README.md`, mas o push completo local ainda precisa de autenticação.

Próximo passo recomendado:

Configurar PAT ou SSH key no servidor e executar:

```bash
git push -u origin main --force
```

O `--force` é necessário porque o remoto tem um commit inicial criado via conector, diferente do commit local completo.

## Comandos úteis

Reiniciar Streamlit:

```bash
systemctl restart streamlit
```

Healthcheck:

```bash
curl -sS http://127.0.0.1:8501/_stcore/health
```

Compilar arquivos principais:

```bash
venv/bin/python -m py_compile app.py services/overview_service.py components/charts/iap_distribution.py components/charts/linear_diagram.py components/maps/overview_map.py
```

## Próximos passos

1. Validar visual final da tela Diagnóstico Paragon com o usuário.
2. Ajustar responsividade e espaçamentos finos conforme prints.
3. Implementar a tela **Diagnóstico DNIT** com dados próprios.
4. Configurar autenticação GitHub no servidor e subir o commit completo.
5. Depois avançar para o próximo módulo do menu lateral.
