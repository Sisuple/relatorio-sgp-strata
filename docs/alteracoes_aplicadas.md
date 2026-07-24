# Alterações aplicadas

Este arquivo é meu resumo simples do que foi sendo corrigido no dashboard.

Não é para ser um relatório técnico engessado. A ideia é deixar registrado, com uma linguagem fácil de explicar, o que estava estranho no painel, o que foi ajustado e por que isso importava.

Uma regra que passou a guiar praticamente tudo: o dashboard precisa continuar funcionando quando a base de dados mudar. Então evitei soluções presas em uma rodovia, ano ou cenário específico. Sempre que possível, rodovias, anos, cenários e pistas passam a vir do próprio banco.

## Regras que passei a seguir

- Nada de ano fixo na tela ou no cálculo.
- Nada de correção exclusiva para uma rodovia.
- Cenários, anos e pistas precisam vir dos dados.
- Paragon e Matriz Cadastrada não podem ser tratados como se fossem a mesma coisa.
- Quando um filtro puder gerar soma duplicada, a tela precisa impedir ou organizar melhor a seleção.
- Mudança de lógica precisa ficar documentada, não só mudança visual.

## Velocidade e estabilidade

A troca de telas estava lenta em alguns momentos.

Parte disso vinha de tentativas repetidas de conexão com Redis quando ele não estava disponível. Foi criado um tempo de espera entre essas tentativas e também uma forma de desligar o Redis em ambiente local.

Na prática, o painel consegue seguir usando cache local sem ficar tentando reconectar o tempo todo.

## Visão geral

A `Visão geral` foi uma das telas mais mexidas.

Ela recebeu filtros de `Rodovia`, `Tipo de Matriz`, `Cenário` e `Ano`. Antes a leitura ficava aberta demais e, em alguns casos, não dava para saber exatamente qual recorte estava sendo mostrado.

Também ajustei a tela para ela não abrir vazia. Quando existem dados, ela já inicia com uma rodovia, um cenário e um ano selecionados.

Os filtros de `Rodovia` e `Ano` continuam aceitando mais de uma opção, mas tirei os botões extras de `Todas` e `Todos`, porque deixaram a barra superior visualmente ruim.

No filtro de cenário, o nome foi encurtado. O texto original do banco repetia rodovia, matriz e outras informações que já apareciam em outros filtros. Agora o painel tenta mostrar só o que ajuda a diferenciar o cenário, como `SH`, `Fixa`, `Crescente`, `Decrescente`, `Todos` e o gatilho.

Também foi corrigida a regra do custo total. O custo agora respeita o ano selecionado. Sem isso, a tela podia mostrar dados técnicos de um ano e custo de um escopo maior, o que deixava a leitura confusa.

Outra regra importante foi a seleção por pista:

- cenário com pista `Todos` fica sozinho;
- cenário `Crescente` pode combinar com `Decrescente`;
- cenário `Decrescente` pode combinar com `Crescente`;
- se aparecer outro tipo de pista desconhecida, a tela segura a seleção para evitar duplicação.

Isso evita somar a rodovia inteira com uma pista específica e acabar dobrando extensão ou custo.

No mapa da `Visão geral`, quando dois sentidos são selecionados, as linhas agora aparecem afastadas. Antes uma pista podia ficar em cima da outra, parecendo que só existia um traçado.

O gráfico de extensão das rodovias também foi ajustado. Quando a mesma rodovia tem dois cenários selecionados, ela aparece em uma única caixa, com uma barra para cada cenário. Antes parecia que eram duas rodovias diferentes.

## Diagnóstico

Na tela `Diagnóstico`, passei a permitir mais de um cenário.

Quando isso acontece, o mapa também usa afastamento entre pistas, igual na `Visão geral` e em `Soluções`.

No Paragon, a distribuição de `IAP` passa a conversar com o mapa. A regra ficou mais coerente: o valor numérico define a classe, e a classe orienta a solução. Antes havia mistura entre conceito de condição e solução corretiva, o que gerava leituras diferentes entre mapa e gráfico.

Na Matriz Cadastrada, apliquei a mesma ideia para `IRI` e `IGG`. Quando há dois cenários, os gráficos são separados de um jeito mais legível:

- `IRI` ao lado de `IRI`;
- `IGG` ao lado de `IGG`.

O diagrama linear também ganhou um seletor de cenário próximo dele. Isso é importante porque, com dois cenários selecionados, não faz sentido misturar os dados no mesmo diagrama como se fosse uma média.

Também foi ajustada a interação entre filtros:

- faixa de km no diagrama filtra mapa e distribuição;
- classe de IAP filtra mapa e distribuição no Paragon;
- faixa de IRI filtra mapa e distribuição na Matriz Cadastrada.

O objetivo foi simples: mapa e gráfico precisam falar da mesma coisa.

## Soluções

A tela `Soluções` foi direcionada para o que realmente interessa ali: trechos com intervenção.

Os filtros de cenário foram padronizados e a tela passou a aceitar mais de um cenário, tanto no Paragon quanto na Matriz Cadastrada.

Quando dois cenários/sentidos são escolhidos, o mapa mostra as pistas separadas.

Os filtros internos também passaram a se ajustar conforme a seleção:

- primeiro o usuário escolhe `SRE`;
- depois aparecem só os conceitos/faixas que existem naquele SRE;
- depois aparecem só os tipos de solução disponíveis naquele recorte.

Se uma opção deixa de existir depois de trocar outro filtro, ela é removida automaticamente.

Também foi melhorado o caso em que não existe intervenção prevista. Em vez de parecer erro ou mapa vazio, a tela mostra uma mensagem mais clara e mantém o mapa disponível.

## Comparativo entre cenários

O comparativo saiu de dentro de `Cenário econômico` e virou uma tela própria.

A ordem do menu ficou:

- `Visão geral`;
- `Diagnóstico`;
- `Soluções`;
- `Comparativo entre cenários`;
- `Cenário econômico`;
- `IAGON`.

Essa separação fez sentido porque comparar cenários é uma análise própria, com dois lados e regras diferentes da tela econômica comum.

Depois, removi a tela `Projeção` do menu. A análise de evolução técnica que fazia mais sentido foi levada para o modo `Técnico` do `Comparativo entre cenários`, onde dá para comparar os cenários lado a lado.

O comparativo deixou de ser preso em `Paragon x Matriz`. Agora é possível comparar:

- Paragon contra Matriz Cadastrada;
- Paragon contra Paragon;
- Matriz contra Matriz;
- um conjunto de cenários contra outro conjunto.

Também foi criada uma trava para evitar comparar exatamente o mesmo recorte com ele mesmo.

Visualmente, a tela foi reorganizada porque os filtros estavam muito poluídos. Agora a comparação A e a comparação B ficam separadas, e os parâmetros da simulação ficam em outra área.

Depois, o modo da página passou a ser um filtro geral ao lado da rodovia: `Técnico` ou `Econômico`.

Quando está em `Técnico`, a página mostra a comparação técnica dos mapas.

Quando está em `Econômico`, a página mostra os mapas por custo e os blocos financeiros: resumo comparativo, custo por ano e custo por trecho/SRE.

A tela também ganhou dois mapas lado a lado:

- no Paragon, o mapa técnico mostra o conceito do `IAP`;
- na Matriz Cadastrada, o mapa técnico mostra a classe do `IRI`;
- no modo econômico, os trechos são coloridos pelo custo;
- o que fica fora do orçamento aparece em vermelho.

Também foi corrigido o caso em que o mapa ficava vazio em alguns recortes. A solução foi usar a geometria técnica completa e aplicar os dados econômicos por cima dela.

## Cenário econômico

A tela `Cenário econômico` ficou dedicada à análise econômica de uma metodologia por vez: `Paragon` ou `Matriz Cadastrada`.

O filtro de cenário foi padronizado e a tela passou a usar `Horizonte` como controle principal de tempo.

O usuário agora escolhe o ano final e decide como quer calcular:

- `Período acumulado`: soma do primeiro ano disponível até o ano escolhido;
- `Somente ano selecionado`: mostra apenas o ano marcado.

Isso resolve uma confusão importante. Às vezes a pessoa quer ver o planejamento acumulado até um ano; em outras, quer olhar só aquele ano específico.

O resumo econômico também foi reorganizado. O card de necessidade total mostra o total geral. Quando há mais de um cenário selecionado, a divisão por cenário aparece em pílulas pequenas logo abaixo dos cards, sem criar um card grande duplicado.

Depois do custo por solução, foi criado um cronograma por segmento, parecido com um Gantt.

Nesse cronograma:

- os segmentos ficam na vertical;
- os anos ficam na horizontal;
- cada célula mostra a intervenção prevista naquele segmento e ano;
- no modo `Técnico`, aparece o tipo de intervenção;
- no modo `Econômico`, aparece o valor.

Quando mais de um cenário está selecionado, o próprio cronograma permite alternar entre eles. Isso evita misturar tudo no mesmo quadro.

Também foi removido o cálculo automático de custo aproximado. Antes, quando um trecho tinha intervenção, mas o banco não trazia custo, o painel podia estimar um valor por km. Isso foi retirado para evitar que custo inventado apareça como se fosse dado real.

Agora, se existir intervenção prevista e não houver custo real para o recorte, a tela mostra `Sem dados de custo para este recorte`.

## Comparativo entre cenários

No modo `Técnico` da tela `Comparativo entre cenários`, comecei a montar um bloco mais parecido com o visual que eu tinha feito no Power BI.

Esse bloco usa a view `vw_desempenho_pavimento_com_trecho` e tenta mostrar quatro indicadores ao longo dos anos:

- `IRI`;
- `Afundamento nas trilhas de roda`, vindo de `flechas_antes_intervencao`;
- `FC2 + FC3`, vindo de `fc2_fc3_antes_intervencao`;
- `Panelas`, vindo de `n_panelas_antes_intervencao`.

Depois de avaliar a leitura, voltei a usar os campos antes da intervenção. Assim o gráfico mostra a condição prevista do segmento antes da obra daquele ano, e o ponto continua indicando onde existe intervenção programada.

A ideia é comparar cenários no mesmo gráfico. Então, quando eu seleciono mais de um cenário no comparativo, cada cenário vira uma linha de cor diferente.

Também troquei a ideia de barra de intervenção por ponto na linha. O ponto maior indica que naquele ano existe intervenção prevista, e o detalhe do ponto mostra qual solução está ligada àquele ano.

Depois corrigi a origem desses pontos no Paragon. O marcador de intervenção passou a usar somente a coluna `solucao_corretiva_final`, porque usar o código `iapa` fazia o gráfico marcar anos demais como se tivessem obra.

O bloco usa os cenários já escolhidos no comparativo. Ele não tem um filtro separado só para ele.

Depois ajustei essa leitura para ser por segmento. Faz mais sentido avaliar esses indicadores em um trecho específico, porque uma média da rodovia inteira pode esconder o que acontece em cada parte da malha.

Por isso, foi adicionado um filtro de `Segmento` logo acima dos gráficos. O segmento é mostrado pelo intervalo de km, por exemplo `km 0.00-0.80`, e os cenários selecionados são comparados nesse mesmo trecho.

Não foi criado dado falso. Se a view não tiver uma coluna ou se o recorte não trouxer informação, o painel mostra ausência de dados para aquele indicador.

## Mapas

Foi corrigido um problema importante no traçado dos mapas.

Antes, alguns mapas desenhavam a rodovia usando pontos de levantamento. Esses pontos são úteis para cálculo, mas não são bons para desenhar a linha da rodovia. Em alguns lugares isso criava zigue-zagues e linhas cruzadas.

Agora os mapas usam a geometria limpa de `pista_shape`. O painel recorta essa linha pelo km inicial e final de cada segmento, mantendo as mesmas cores, classes e filtros.

Também foi tratado o caso de linhas duplicadas ou sobrepostas no banco. Quando a mesma geometria aparece mais de uma vez cobrindo o mesmo trecho, o painel mantém a linha mais completa e evita desenhar várias linhas paralelas para um cenário só.

Se for necessário comparar com o comportamento antigo, existe um caminho de retorno usando `MAP_GEOMETRY_SOURCE=iri`.

O zoom do satélite também foi limitado ao ponto em que a imagem ainda tem qualidade real. Antes dava para aproximar além da resolução disponível, e o mapa ficava só embaçado.

## Visual dos gráficos

Foram feitos vários ajustes pequenos de apresentação:

- melhor contraste nas barras;
- legendas menos emboladas;
- rótulos menos colados nos gráficos;
- roscas com mais espaço;
- filtros múltiplos com aparência mais padronizada;
- organização melhor das caixas e controles.

Essas mudanças não foram só “beleza”. Elas ajudam a evitar interpretação errada dos dados.

## Tema claro e escuro

Foi adicionado um botão para alternar o painel entre tema escuro e tema claro.

Esse botão ficou no rodapé do menu lateral esquerdo, para não ocupar espaço no topo das telas.

Depois que o tema é escolhido, ele continua aplicado ao trocar de tela.

Para isso, o tema também fica salvo na URL da página. Assim, os links do menu lateral carregam a próxima tela já com o mesmo tema.

O tema escuro continua sendo o padrão, porque é o visual que já vinha sendo montado.

O tema claro muda apenas a “casca” do dashboard: fundo, cards, bordas, textos e controles.

As cores dos dados técnicos não foram alteradas. Ou seja, cores de IAP, IRI, intervenções, mapas e demais classificações continuam seguindo a mesma lógica de antes.

Também foi feita uma passada nos rótulos, legendas, filtros e opções selecionadas para melhorar a leitura no tema claro.

Na tela `Visão geral`, no visual `Extensão das rodovias e recortes`, removi o preenchimento cinza forte da caixa interna no tema claro. A área continua organizada por borda, mas sem aquele fundo pesado que destoava do card branco.

Também ajustei os rótulos no tema claro para não ficarem brancos em fundo branco. Isso vale para valores laterais e textos dentro dos gráficos.

Depois corrigi também o rótulo do gráfico `Custo por recorte`, que era um gráfico HTML próprio e ainda mantinha o texto branco acima da barra.

No gráfico `Distribuição IAP`, ajustei o tema claro para o centro da rosca deixar de ficar escuro. O miolo passou a acompanhar o fundo claro do card, e o rótulo central ficou escuro.

## Observação importante sobre Paragon e Matriz Cadastrada

Durante as correções ficou claro que o painel tratava `Paragon` e `Matriz Cadastrada` como se fossem quase a mesma coisa em vários pontos.

Mas não são.

O Paragon trabalha principalmente com IAP e regras próprias de solução.

A Matriz Cadastrada trabalha com IRI, IGG, deflexão e soluções cadastradas.

Então cada tela precisa respeitar a metodologia escolhida. Parte do retrabalho foi justamente separar essas lógicas para evitar resultado falso, mapa vazio ou filtro com opção que não pertence ao recorte.

## Correção da lógica do IAP

Foi corrigida uma regra importante do Paragon.

O painel estava tratando a coluna `iapa` como se fosse o valor do IAP multiplicado por 100. Na prática, essa coluna é um código.

Agora o código é convertido por uma tabela de referência:

- o código indica o valor real do IAP;
- o valor indica a classe;
- a classe indica a solução;
- as cores que já existiam no painel foram mantidas.

Exemplo simples: antes um código como `125` podia virar `1,25`. Agora ele entra na tabela e vira o valor correto definido para aquele código.

Essa correção afeta os pontos do dashboard que usam IAP no Paragon, como mapa, distribuição, diagrama linear, tabela de soluções e projeção.

Ponto para validar: abrir alguns trechos conhecidos no banco e conferir se valor, classe, solução e cor estão contando a mesma história.

Também removi os dados demonstrativos antigos dessa tela. Antes, quando não havia extração real de IAP, o painel podia preencher a tela com valores fixos só para não ficar vazia. Isso era perigoso porque parecia dado real.

Agora, quando não existe dado real para o recorte escolhido, a tela mostra: `Sem dados para este recorte`.

Também deixei o texto do card `IAP médio` mais claro. Ele continua existindo porque ajuda a resumir a condição geral, mas agora fica indicado que é uma média ponderada pela extensão. Ou seja, ele serve como resumo, não como decisão única.

## Cuidados daqui para frente

- Conferir se os números batem quando muda ano, cenário e matriz.
- Não prender regra em rodovia específica.
- Não usar ano fixo.
- Validar visualmente os mapas depois de qualquer alteração de geometria.
- Sempre pensar se a tela continua funcionando quando a base de dados for trocada.

## Ajustes visuais pequenos

Nos gráficos técnicos do `Comparativo entre cenários`, deixei a legenda mais clara: os cenários aparecem como linhas coloridas e a intervenção aparece como uma bolinha cinza na mesma legenda.

Também padronizei o título desses gráficos para ficar com a mesma cara dos outros cards do painel.

No `Diagnóstico`, corrigi o primeiro diagrama linear no tema claro para ele ficar com fundo branco, igual aos outros visuais.

## Troca da prioridade Paragon para IPI

Comecei a troca da prioridade antiga (`IPT`) pela nova regra de `IPI`.

O tráfego passou a vir da `view_vmda_67`.

A regra usada foi:

- `VMDL` = veículos de passeio;
- `VMDP` = soma dos veículos de 2 a 9 eixos;
- `VMDeq` = `VMDL + 4 * VMDP`.

O trecho de tráfego é ligado ao segmento da rodovia pelo intervalo de km. Se um segmento está dentro do trecho de tráfego, ele usa aquele volume.

Exemplo: se o tráfego vai do km 0 ao 12, os segmentos de pavimento entre 0 e 12 usam o mesmo tráfego.

Também deixei uma proteção para valores de `ICDS/ICDP` abaixo de 1. Nesses casos o dano fica limitado em 100%, para não gerar resultado quebrado na fórmula.

Ponto para validar no banco: alguns segmentos ainda ficaram sem tráfego casado. Esses trechos não devem receber prioridade inventada.

## Ajuste da fila de prioridade Paragon

Hoje fechei a lógica da fila de prioridade do Paragon.

Antes o painel pegava o IPI calculado e ainda transformava em uma nota de 1 a 10. Isso deixava a tela confusa, porque parecia existir uma segunda prioridade além do IPI.

Agora a tela usa o próprio IPI:

- a tabela mostra a coluna `IPI`;
- o ranking começa pelo trecho com maior IPI;
- o filtro `IPI mínimo` foi removido depois, para a tela sempre considerar todos os segmentos do recorte;
- a coluna `Priorização` 1 a 10 saiu da tabela Paragon.

Ou seja: no Paragon, quanto maior o IPI, mais prioritário é o trecho.

## Limpeza depois da revisão geral

Depois de revisar o dashboard inteiro, fiz uma limpeza para evitar mensagens confusas.

O que foi ajustado:

- o IAGON deixou de falar em prioridade Paragon como nota de 1 a 10;
- exportações e PDF passaram a mostrar `IPI` no lugar de `IPT`/`Priorização` para Paragon;
- gráficos internos do IAGON deixaram de limitar custo em 8 anos e passaram a usar os anos cadastrados;
- removi rodovias fictícias de fallback, para não parecer que existe dado real quando o banco não retorna nada;
- código IAP desconhecido não vira mais valor numérico por tentativa. Se não estiver mapeado, deve ser tratado como dado ausente.

A regra final fica: no Paragon, o ranking é pelo maior `IPI`. Na Matriz Cadastrada, a fila econômica usa o índice escolhido no seletor: `Técnica`, `Econômica` ou `Combinada`.

## Remoção do IPE da tabela Paragon

Removi a coluna `IPE` da tabela Paragon do cenário econômico.

Motivo: ela era um cálculo auxiliar econômico, mas não estava sendo usada para ordenar a fila. Como a prioridade agora é pelo `IPI`, manter `IPE` na tabela podia dar a impressão de que ele também participava do ranking.

A tabela Paragon fica mais direta:

- rank;
- SRE;
- km inicial e final;
- extensão;
- IAP;
- IPI;
- custo;
- soluções.

## Matriz Cadastrada aberta por segmento

Ajustei a tabela econômica da Matriz Cadastrada.

Antes ela juntava os dados por `SRE`. Isso fazia vários trechos virarem uma única linha, com km inicial, km final, custo e indicadores consolidados.

Agora a leitura fica por segmento, igual no Paragon:

- cada linha representa um segmento da rodovia;
- a mesma SRE pode aparecer mais de uma vez, porque ela pode ter vários segmentos;
- o orçamento atende segmento por segmento, seguindo a ordem de prioridade;
- o mapa também passa a respeitar os segmentos que entraram no filtro de prioridade.

Essa mudança deixa a tela mais fácil de conferir no banco, porque o usuário consegue comparar o intervalo de km da tabela com o trecho real que aparece no mapa.

## Priorização da Matriz Cadastrada

Atualizei a forma de priorizar os segmentos da Matriz Cadastrada.

Antes o painel estava usando uma regra simplificada, baseada em `IRI` e `IGG`.

Agora a tela segue a lógica adaptada do dashboard antigo:

- `IPT` olha a parte técnica;
- `IPE` olha a eficiência econômica;
- `Combinada` junta os dois, usando 60% técnico e 40% econômico.

Na prática, a tela ganhou um seletor de priorização:

- `Técnica`: ordena pelo `IPT`;
- `Econômica`: ordena pelo `IPE`;
- `Combinada`: ordena por `0,60 * IPT + 0,40 * IPE`.

O `IPT` usa `VMDA`, `IRI` e `DEF`. O `IPE` usa a eficiência, calculada como `IPT / custo por km * 1000`.

Depois ajustei a escala da Matriz Cadastrada para ficar igual ao Paragon.

Antes `IPT`, `IPE` e `Combinada` iam de `0 a 10`. Agora vão de `0 a 100`.

A ordem dos trechos não muda por causa disso. O que muda é só a escala exibida, para ficar mais fácil comparar com o `IPI` do Paragon.

O filtro `Índice mínimo` da Matriz chegou a ser criado, mas depois foi removido para simplificar a tela. Agora a Matriz mostra todos os segmentos do recorte e a prioridade é controlada pela ordenação e pelo tipo de índice escolhido.

Na tabela da Matriz, removi `IGG` dessa visão de priorização para não parecer que ele entra no cálculo do índice. Ele continua existindo em outras telas técnicas, como diagnóstico, mas não participa dessa fila econômica.

Depois movi o seletor de `Combinada`, `Técnica` e `Econômica` para perto da própria tabela. No topo da tela ele parecia um filtro geral; perto da tabela fica mais claro que ele muda a ordenação daquele visual.

Também deixei a coluna de soluções da Matriz no mesmo estilo da tabela Paragon. Em vez de mostrar o texto completo ocupando muito espaço na linha, agora aparece o botão `Ver soluções`. Ao abrir, o usuário vê o detalhe do segmento, com programação por ano, solução e custo.

Adicionei também o filtro `Ordenar por` na tabela da Matriz, igual ao Paragon. Agora dá para alternar entre ordenar pela prioridade ou pelo km inicial.

Depois padronizei a posição dos filtros da tabela da Matriz.

Agora eles ficam à esquerda, como na tabela Paragon, na ordem:

- `Visualização`;
- `Ordenar por`;
- `Índice de priorização`.

Também adicionei o filtro `Visualização` na Matriz, para alternar entre `Segmentos atendidos pelo orçamento` e `Todos os segmentos`.

Depois removi os filtros de corte mínimo que existiam no cenário econômico:

- `IPI mínimo`, no Paragon;
- `Índice mínimo`, na Matriz Cadastrada.

A tela ficou mais direta: o usuário escolhe orçamento, horizonte, visualização, ordenação e, no caso da Matriz, o tipo de índice de priorização.

## Filtro para remover trechos da análise econômica

Na tela `Cenário econômico`, adicionei uma caixa chamada `Remover trechos da análise`.

Ela fica logo abaixo do filtro de cenário e serve para tirar trechos apenas da visualização.

A ideia é simples: se um trecho já teve obra executada, ou se por algum motivo não deve entrar naquela simulação, dá para remover esse trecho da análise sem apagar nada do banco.

Quando um trecho é removido por esse filtro, ele sai dos cálculos e visuais da tela:

- cards de necessidade, cobertura e orçamento;
- mapa;
- gráficos de custo;
- cronograma por segmento;
- tabela de segmentos atendidos.

Essa regra foi aplicada tanto para `Paragon` quanto para `Matriz Cadastrada`.

Importante: essa remoção é temporária e visual. Ao limpar o filtro, o trecho volta normalmente para a análise.

Depois melhorei esse mesmo filtro para aceitar intervalo de km digitado.

Exemplo: ao digitar `0 a 59`, o painel já seleciona os trechos que cruzam esse intervalo. A seleção manual continua existindo, então dá para usar o intervalo como atalho e depois ajustar trecho por trecho, se precisar.
## Fundo dos diagramas lineares

Padronizei o fundo dos diagramas lineares da tela de Diagnóstico.

O diagrama que já aparece aberto agora usa o mesmo quadro de fundo, borda e espaçamento do visual que aparece em `Mostrar detalhes técnicos`.

O ajuste vale para os diagramas de Paragon e Matriz Cadastrada. Não alterei dados, cores, filtros ou cálculos.
## Cor dos itens selecionados nos filtros

Troquei o vermelho dos itens selecionados nos filtros por azul-marinho no tema escuro.

O texto e o botão de remover continuam claros para manter a leitura. A mudança vale para todas as telas e altera somente a aparência dos filtros.
## Altura dos filtros com várias seleções

Os filtros que aceitam várias opções agora mantêm a mesma altura mesmo quando mais itens são selecionados.

As seleções ficam em uma única linha e podem ser percorridas horizontalmente dentro do campo. Assim, os filtros não crescem para baixo nem desalinham o restante da tela.
## Título separado dos filtros

Separei o título dos filtros nas telas `Visão geral`, `Diagnóstico`, `Soluções`, `Comparativo entre cenários` e `Cenário econômico`.

O nome da tela fica na primeira linha. Os filtros começam na linha seguinte, alinhados pela esquerda. A mudança é somente visual e não altera o funcionamento das seleções.
## Menos contornos nos visuais

Retirei as bordas decorativas que contornavam mapas, gráficos e blocos de conteúdo.

Os fundos e os espaços entre as seções continuam separando cada visual. As sombras ficaram mais leves e as bordas foram mantidas apenas onde ajudam a indicar interação ou atenção, como filtros, botões, avisos e cards de indicadores.

No visual de extensão das rodovias, também removi a borda da caixa interna de cada rodovia.
# Ajuste de cores no gráfico de extensão

- O nome da rodovia passou a aparecer em branco no tema escuro.
- Foi corrigida a regra do link para impedir que o Streamlit volte a pintar esse nome de azul.
- A parte que precisa de intervenção passou a usar um laranja mais suave.
- A parte considerada OK passou a usar cinza/azul escuro, como fundo da barra, para deixar a intervenção mais evidente.
- As cores da legenda foram ajustadas para acompanhar as barras.
- A caixa de cada rodovia voltou a ter uma borda discreta e o cenário fica logo acima da barra, no mesmo padrão do exemplo escolhido.
- Nenhum cálculo ou tamanho das barras foi alterado.
# Filtros com várias escolhas

- Quando há somente uma opção marcada, o filtro continua mostrando o nome normalmente.
- Quando há duas ou mais opções, o filtro fechado mostra a quantidade selecionada e não aumenta de altura.
- Ao abrir ou editar o filtro, as escolhas continuam disponíveis no componente normal.
- As opções já escolhidas recebem um destaque azul discreto na lista.
- Clicar novamente em uma opção marcada continua removendo essa escolha.
- Na Visão Geral, Rodovia, Cenário e Ano passaram a usar uma lista vertical com caixas de seleção.
- A contagem continua visível mesmo enquanto essa lista está aberta.
- As opções marcadas continuam aparecendo na lista e podem ser desmarcadas no mesmo lugar.
- O mesmo padrão compacto foi aplicado aos demais filtros múltiplos do dashboard.
- O fundo azul forte e a sombra grande foram removidos para manter o mesmo visual dos filtros de escolha única.
- A aparência anterior foi recuperada: campo escuro, seleção em azul-marinho e texto branco.
- Reforcei a regra visual para o seletor não voltar ao azul vivo do botão e ficar mais parecido com o filtro antigo.
- Removi o detalhe azul interno dos filtros compactos para eles ficarem mais parecidos com o seletor `Tipo de Matriz`.
- Padronizei a fonte dos filtros compactos para usar o mesmo tamanho e peso do filtro `Tipo de Matriz`.
- Padronizei o alinhamento dos textos dos filtros compactos para começar à esquerda.
- A nova forma de selecionar e desmarcar opções pela lista vertical foi mantida.
- O filtro de remoção de trechos continua no formato original porque pode conter muitas opções e precisa da busca por texto.

## Títulos das páginas

- Os títulos principais das telas passaram a aparecer em caixa alta, como `VISÃO GERAL`.
- O texto pequeno `RELATÓRIOS`, que aparecia acima dos títulos, foi removido para limpar o topo das telas.
- A mudança é apenas visual e não altera navegação, filtros ou nomes usados nos cálculos.

## Cenário Econômico

- O filtro de `Cenários` foi movido para a mesma linha dos filtros `Rodovias` e `Tipo de Matriz`.
- A seleção de um ou mais cenários continua funcionando igual; a mudança foi apenas na organização do topo.

## Cards de indicadores

- Reduzi o espaço interno dos cards para evitar áreas vazias grandes.
- Mantive título, valor e descrição mais próximos, sem alterar nenhum cálculo.
- Melhorei o destaque dos ícones usando a cor de cada indicador de forma mais clara.
- O mesmo ajuste vale para tema escuro e tema claro.
- No card `TRECHOS PRIORITÁRIOS`, mantive o total no valor principal e passei a mostrar no subtítulo quantos são `Alta` e quantos são `Crítica`.
- A regra exibida no card ficou como `IPI ≥ 50`, que representa Alta ou Crítica.
- Na Visão Geral, a separação entre `Alta` e `Crítica` passou a aparecer como marcadores discretos dentro do card, facilitando a leitura rápida.
- Adicionei um cabeçalho simples antes do mapa da Visão Geral para indicar que o mapa mostra a malha filtrada e a extensão total do recorte.

## Ajustes visuais na Visão Geral

- Padronizei a fonte e o peso dos textos nos filtros do topo, incluindo o Tipo de Matriz.
- Deixei os dois cards com a mesma altura e alinhei melhor seus conteúdos.
- Aproximei o título e a descrição do mapa.
- Retirei o azul do nome dos cenários no gráfico de extensão e usei branco.
- Troquei o trecho OK por um cinza-azulado mais discreto. O laranja da intervenção e os cálculos das barras não mudaram.
- Na Visão Geral, o Tipo de Matriz passou a usar o mesmo formato visual dos outros filtros. Ele continua permitindo somente uma escolha.
- Ao abrir o Tipo de Matriz, as opções agora usam as mesmas caixas dos outros slicers. Ao marcar uma opção, a anterior é desmarcada automaticamente.
