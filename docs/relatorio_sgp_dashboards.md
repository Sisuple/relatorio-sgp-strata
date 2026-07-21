# Relatório SGP - Dashboards

**Data:** 10/07/2026  
**Uso:** diagnóstico inicial e guia de correções  
**Público:** gestão, operação e equipe técnica

## 1. Objetivo

Este documento registra minha leitura inicial do dashboard SGP.

A ideia é separar o que já existe, o que está funcionando como protótipo e o que precisa ser corrigido para o painel virar uma ferramenta confiável de análise.

O dashboard tem uma proposta boa: juntar diagnóstico técnico, soluções, projeção, risco, cenário econômico e apoio do IAGON em uma jornada só.

Mas, olhando com calma, ficou claro que algumas partes ainda estavam frágeis. Não era só questão visual. Em vários pontos, filtros, cálculos e mapas não estavam totalmente alinhados.

## 2. Leitura geral

O painel já tem bastante coisa pronta:

- conexão com banco;
- filtros;
- mapas;
- gráficos;
- cards;
- simulação econômica;
- telas para Paragon e Matriz Cadastrada;
- módulo IAGON.

O problema é que algumas regras importantes estavam misturadas ou concentradas em poucos arquivos.

Também encontrei situações em que a tela parecia permitir uma análise, mas a lógica por trás ainda não acompanhava completamente. O exemplo mais claro foi a separação entre `Paragon` e `Matriz Cadastrada`: visualmente parecia só trocar o tipo de matriz, mas internamente parte da tela ainda seguia o caminho errado.

Por isso, o trabalho de correção precisa ser tratado como revisão de lógica do produto, não só como melhoria de interface.

## 3. Prioridades

Usei três níveis simples:

| Prioridade | Como estou entendendo |
| --- | --- |
| Alta | Pode gerar leitura errada, tela sem dado falso, cálculo inconsistente ou problema para produção. |
| Média | Melhora clareza, uso e manutenção, mas não bloqueia tudo sozinha. |
| Baixa | Melhoria desejável, mas que pode esperar. |

## 4. Visão geral

A `Visão geral` deveria ser a tela de entrada para entender rapidamente a situação da malha.

O principal problema encontrado foi que ela não tinha todos os filtros necessários e, em alguns casos, misturava regras de metodologias diferentes.

Pontos que precisavam de atenção:

- filtro de rodovia;
- filtro de cenário;
- filtro de ano;
- filtro de tipo de matriz;
- custo coerente com o ano selecionado;
- mapa coerente com cenário e pista;
- nomes de cenário mais curtos;
- cuidado para não somar pista `Todos` junto com `Crescente` ou `Decrescente`.

Também ficou claro que a tela precisava abrir com um recorte válido. Quando ela abre sem ano ou sem cenário, a leitura fica estranha e alguns números podem não bater com a expectativa.

### Priorização

A regra de priorização também merece cuidado.

O dashboard atual e a referência anterior do Power BI não usam exatamente a mesma lógica.

Diferenças observadas:

| Ponto | Power BI | Streamlit atual |
| --- | --- | --- |
| Índice técnico | usa VMDA, IRI e DEF | usa VMDA, ICDS e ICDP |
| Índice econômico | usa normalização logarítmica | usa normalização linear |
| Priorização final | combina IPT e IPE | usa principalmente IPT reescalado |
| Unidade | código/SNV | segmento, com SNV herdando pior trecho |

Essa diferença precisa ser validada antes de alguém tratar o ranking como “igual ao Power BI”.

## 5. Diagnóstico

A tela `Diagnóstico` deve explicar a condição do pavimento.

O que precisava ser corrigido era a coerência entre mapa, gráficos e filtros.

No Paragon, a lógica correta é:

- o valor numérico do IAP define a classe;
- a classe ajuda a indicar a solução;
- mapa e distribuição precisam usar a mesma leitura.

Antes, havia mistura entre conceito de condição e solução corretiva. Isso fazia a rosca de distribuição não conversar bem com o mapa.

Na Matriz Cadastrada, a leitura muda:

- IRI;
- IGG;
- deflexão;
- soluções cadastradas.

Então a tela precisa respeitar essa metodologia e não reaproveitar regra do Paragon como se fosse igual.

Também foi identificado que, ao selecionar mais de um cenário, os diagramas lineares não deveriam misturar os dados. O ideal é escolher qual cenário alimenta o diagrama.

## 6. Soluções

A tela `Soluções` precisa focar nos trechos que realmente têm intervenção.

Pontos importantes:

- filtros devem depender do recorte escolhido;
- `SRE`, conceito/faixa e tipo de solução precisam conversar entre si;
- se um SRE não tem certa solução, essa solução não deve aparecer como opção válida;
- quando não houver intervenção, a tela deve avisar claramente.

Também é importante separar Paragon e Matriz Cadastrada:

- no Paragon, a solução vem da lógica ligada ao IAP;
- na Matriz, a solução vem da matriz cadastrada, ligada a IRI/IGG/deflexão.

## 7. Comparativo entre cenários

O comparativo não deveria ficar escondido dentro de `Cenário econômico`.

Ele é uma análise própria.

O desenho mais correto é ter uma tela separada, com:

- Comparação A;
- Comparação B;
- tipo de matriz em cada lado;
- um ou mais cenários em cada lado;
- mapas lado a lado;
- resumo econômico comparativo.

Isso permite comparar:

- Paragon contra Matriz;
- Paragon contra Paragon;
- Matriz contra Matriz;
- dois conjuntos de cenários.

Também é importante impedir comparação do mesmo recorte contra ele mesmo, porque isso não agrega informação.

## 8. Cenário econômico

A tela `Cenário econômico` deve analisar uma metodologia por vez.

Ela precisa deixar claro:

- qual cenário está sendo avaliado;
- qual horizonte está sendo usado;
- se o cálculo é acumulado ou apenas do ano selecionado;
- qual orçamento foi considerado;
- o que foi atendido e o que ficou de fora.

O filtro de `Horizonte` deve trabalhar com anos reais da base, e não com um intervalo fixo.

Também faz sentido mostrar:

- custo por ano;
- custo por solução;
- cronograma por segmento;
- mapa com o que cabe ou não cabe no orçamento.

Quando houver mais de um cenário, a tela deve mostrar o total geral e a abertura por cenário sem poluir o layout.

## 9. Projeção

A tela de `Projeção` precisa ser tratada com cuidado porque ela sugere futuro.

O painel deve deixar claro:

- qual regra de evolução está sendo usada;
- se a curva é estimativa;
- qual intervenção influencia a projeção;
- quais dados estão sustentando aquela leitura.

Sem isso, o usuário pode interpretar a projeção como certeza, quando ela depende da qualidade dos dados e das premissas.

## 10. IAGON

O IAGON é útil como apoio de interpretação, mas depende de configuração externa.

Pontos importantes:

- precisa de chave da API da OpenAI;
- essa chave deve ser corporativa, não pessoal;
- precisa estar no `.env`, não no código;
- o usuário precisa entender que o IAGON apoia a análise, mas não substitui validação técnica.

Também é importante registrar quais arquivos de apoio e contexto o IAGON usa, para não quebrar quando o projeto for instalado em outro ambiente.

## 11. Google Maps e Street View

O mapa analítico principal não depende da chave do Google.

A chave do Google é usada para Street View.

Mesmo com chave preenchida, o recurso pode falhar se:

- a API correta não estiver habilitada;
- não houver faturamento ativo;
- a chave não permitir o domínio/local onde o painel está rodando;
- a restrição da chave estiver errada.

Então não basta “ter a chave”. Precisa validar a configuração no Google Cloud.

## 12. Pontos estruturais

O projeto ainda concentra muita coisa no `app.py`.

Isso funciona para protótipo, mas dificulta manutenção quando as regras crescem.

O ideal é evoluir aos poucos para:

- telas mais separadas;
- serviços cuidando de regra e consulta;
- componentes cuidando só da apresentação;
- regras de classificação centralizadas;
- testes para cálculos importantes.

Essa organização não precisa acontecer toda de uma vez, mas precisa ser considerada para produção.

## 13. Riscos se não corrigir

Os principais riscos são:

- usuário confiar em número de recorte errado;
- filtro mostrar opção que não pertence ao cenário;
- mapa e gráfico contarem histórias diferentes;
- Paragon e Matriz Cadastrada se misturarem;
- dificuldade para implantar em outro ambiente;
- dependência demais de quem conhece o código hoje;
- retrabalho sempre que a base mudar.

## 14. Próximos passos recomendados

Minha sugestão de caminho:

1. estabilizar filtros, mapas e cálculos principais;
2. validar as regras de priorização com a área responsável;
3. separar melhor Paragon e Matriz Cadastrada;
4. padronizar legenda, cores e nomes;
5. validar a tela econômica com exemplos conhecidos;
6. documentar as regras que forem aprovadas;
7. só depois pensar em refatoração maior.

## 15. Conclusão

O painel tem uma base útil, mas ainda precisava de bastante ajuste para ser confiável.

A maior parte do trabalho não é simplesmente “deixar bonito”. É fazer as telas conversarem entre si, garantir que os filtros realmente mudem os dados certos e evitar que o usuário tome decisão olhando um recorte errado.

O caminho mais seguro é corrigir por partes, validar cada regra com dados reais e manter a documentação simples o suficiente para qualquer pessoa entender o que foi feito.
