# Registro de alterações

Este é o registro mais detalhado das correções feitas no dashboard.

Eu não quero que este arquivo pareça um texto automático ou um relatório feito só para cumprir tabela. A ideia é ser um diário de trabalho: o que eu encontrei, o que eu corrigi, por que mexi e quais cuidados ficaram para validar depois.

O dashboard precisa funcionar com outras bases no futuro. Por isso, sempre que possível, as regras foram ajustadas para depender dos dados do banco, e não de uma rodovia, ano ou cenário específico.

## Como estou registrando

Quando a mudança altera cálculo, filtro, mapa, gráfico, tela ou regra de negócio, ela entra aqui.

Quando aparece um erro temporário durante uma correção, eu só registro se ele explicar alguma decisão importante. Não faz sentido transformar cada erro intermediário em uma alteração separada, porque isso deixa a documentação mais confusa do que útil.

## Regras gerais que guiaram as correções

- Não usar ano fixo.
- Não criar regra exclusiva para uma rodovia.
- Não misturar lógica Paragon com lógica da Matriz Cadastrada.
- Não somar cenários que representam a mesma pista/rodovia de forma duplicada.
- Manter mapa, gráfico e card falando do mesmo recorte.
- Documentar toda mudança de comportamento.
- Explicar mudanças técnicas em linguagem simples.

---

## 1. Velocidade, cache e Redis

No começo, a troca de telas estava lenta.

A investigação mostrou que parte da lentidão vinha das tentativas de conexão com Redis. Quando o Redis não estava disponível, o painel tentava reconectar várias vezes e isso deixava a navegação pesada.

O que foi feito:

- incluí um tempo de espera depois de uma falha no Redis;
- durante esse intervalo, o painel usa cache local em memória;
- também foi criada a opção de desligar o Redis via ambiente, usando `REDIS_ENABLED=false`.

Arquivos envolvidos:

- `services/cache.py`;
- `docs/registro_alteracoes.md`.

O que precisa ficar claro:

- isso não removeu o Redis do projeto;
- apenas evitou que um Redis indisponível travasse a experiência local;
- em produção, o Redis pode continuar sendo usado normalmente, se estiver configurado.

Como validar:

- abrir o app com Redis indisponível;
- trocar de telas;
- conferir se a navegação não fica presa em várias tentativas seguidas de conexão.

---

## 2. Organização da documentação

Foi criada uma documentação contínua para acompanhar o retrabalho.

O objetivo é registrar não só “o que foi feito”, mas também por que aquilo foi necessário. Isso é importante porque várias partes do painel pareciam protótipo: funcionavam em alguns cenários, mas quebravam ou confundiam quando a base mudava.

Arquivos usados para documentação:

- `docs/alteracoes_aplicadas.md`;
- `docs/registro_alteracoes.md`;
- `docs/relatorio_sgp_dashboards.md`;
- `docs/Relatorio_SGP_Dashboards.docx`;
- `docs/Relatorio_SGP_Dashboards.rtf`.

O registro em `.md` passou a ser a fonte mais prática para acompanhar o dia a dia. O arquivo Word continua sendo útil para envio, mas o conteúdo vivo está nos documentos em Markdown.

---

## 3. Visão geral

A `Visão geral` recebeu vários ajustes porque era uma tela central e estava deixando margem para interpretação errada.

### Filtros principais

Foram adicionados e padronizados os filtros:

- `Rodovia`;
- `Tipo de Matriz`;
- `Cenário`;
- `Ano`.

Antes, a tela ficava muito agregada. Em alguns casos não estava claro se o usuário olhava uma rodovia, uma malha inteira, um ano específico ou um conjunto maior.

Agora a tela já abre com uma seleção válida quando existem dados disponíveis. Ela não deve nascer zerada.

Também foram retirados os botões extras de `Todas` e `Todos` que tinham sido testados nos filtros de rodovia e ano. Eles deixaram a barra superior ruim visualmente. O multiselect já permite escolher mais de uma opção, então os botões não eram necessários.

Arquivos envolvidos:

- `app.py`;
- `services/overview_service.py`;
- `docs/alteracoes_aplicadas.md`;
- `docs/registro_alteracoes.md`.

### Nome dos cenários

O nome do cenário vinha muito comprido do banco.

Exemplo do problema:

`BR-364 (SH) - DECRESCENTE - MATRIZ PARAGON - GATILHO IQO`

Esse texto repetia informações que o usuário já tinha escolhido nos filtros, como rodovia e matriz.

Foi criada uma regra para encurtar o rótulo do cenário sem apagar o que realmente diferencia um cenário do outro.

Informações preservadas:

- `SH`;
- `Fixa`;
- `Crescente`;
- `Decrescente`;
- `Todos`;
- gatilho.

O valor real do cenário não muda. Só muda o texto exibido no filtro.

### Custo total por ano

O card de custo total precisava respeitar o filtro de ano.

Antes, o painel podia mostrar um valor que não batia com a leitura ano a ano. Isso acontecia porque parte do custo vinha da programação completa, e não necessariamente do ano escolhido.

Foi ajustado para o custo respeitar o ano selecionado. Também foi definido que a tela deve sempre ter um ano inicial selecionado quando houver anos disponíveis.

### Regra de pista no filtro de cenário

Foi adicionada uma trava para evitar combinações que duplicam extensão ou custo.

A regra é:

- se o cenário for pista `Todos`, ele fica sozinho;
- se for `Crescente`, pode combinar com `Decrescente`;
- se for `Decrescente`, pode combinar com `Crescente`;
- se a pista vier em um formato desconhecido, o painel prefere manter uma seleção mais segura.

Motivo:

`Todos` já representa a rodovia inteira. Se o usuário somar `Todos` com `Crescente` ou `Decrescente`, a mesma extensão pode entrar duas vezes.

### Mapa da Visão geral

Quando dois sentidos são selecionados, o mapa passou a desenhar as pistas com afastamento visual.

Isso ajuda porque, quando as linhas ficam uma sobre a outra, parece que só existe um sentido.

Também foi evitado redesenhar a mesma geometria várias vezes quando mais de um ano é selecionado.

### Gráfico de extensão das rodovias

Quando uma rodovia tinha dois cenários selecionados, ela aparecia duplicada no gráfico.

A solução foi agrupar melhor: a rodovia aparece uma vez, e os cenários ficam dentro da mesma caixa, cada um com sua barra.

Isso deixa claro que não são duas rodovias diferentes, e sim dois recortes da mesma rodovia.

---

## 4. Diagnóstico

A tela `Diagnóstico` também precisou ser reorganizada para não misturar recortes.

### Mais de um cenário

A tela passou a aceitar mais de um cenário selecionado.

Quando isso acontece:

- o mapa mostra os cenários/sentidos com afastamento;
- as distribuições são separadas por cenário;
- os diagramas lineares não misturam tudo automaticamente.

### IAP no Paragon

Foi identificada uma confusão importante: mapa e distribuição de IAP não estavam necessariamente contando a mesma história.

O ideal definido foi:

- o valor numérico manda;
- a classe vem do valor;
- a solução depende da classe.

Antes, parte da visualização podia parecer baseada no IAP, mas na prática refletia solução corretiva. Isso confundia a leitura, por exemplo quando havia trecho excelente no mapa, mas a rosca não mostrava excelente.

O ajuste foi alinhar mapa e distribuição para usarem a mesma lógica.

Depois foi identificado mais um ponto: a coluna `iapa` não deve ser lida como valor dividido por 100. Ela é um código.

Foi criado um mapa de conversão com base na tabela enviada:

- código `iapa` -> valor real do IAP;
- valor do IAP -> classe;
- classe -> solução;
- cores existentes continuam iguais.

Com isso, o Paragon deixa de usar a conta antiga `iapa / 100` e passa a usar a referência correta. Essa regra foi aplicada nos lugares que usam IAP: mapa, distribuição, diagrama linear, tabela de soluções e projeção.

Esse ajuste é importante porque muda a leitura técnica do trecho. Um código alto no banco não significa necessariamente IAP alto. Ele precisa ser interpretado pela tabela.

Também foi removido o preenchimento demonstrativo antigo. Antes, se não houvesse dado real de IAP para um recorte, o painel ainda podia mostrar números fixos de exemplo. Isso não é bom para produção, porque a tela parece ter dado real.

Agora, sem dado real, a tela informa `Sem dados para este recorte`.

### Matriz Cadastrada

Na Matriz Cadastrada, a leitura é outra.

Ela trabalha principalmente com:

- `IRI`;
- `IGG`;
- deflexão;
- soluções cadastradas.

Foi aplicado o mesmo cuidado de coerência:

- filtro de faixa por km afeta mapa e distribuição;
- gráfico de `IRI` conversa com o mapa;
- gráfico de `IGG` acompanha o recorte visível;
- quando há dois cenários, `IRI` fica lado a lado com `IRI` e `IGG` fica lado a lado com `IGG`.

### Diagramas lineares

Quando há mais de um cenário, os diagramas lineares ganharam um seletor próximo deles.

Isso evita o usuário olhar para um diagrama achando que ele representa os dois cenários, quando na verdade precisa escolher qual cenário está sendo visto.

No Paragon, isso afeta:

- `IAP`;
- `ICDS`;
- `ICDP`;
- `ICDE`.

Na Matriz Cadastrada, isso afeta:

- `IRI`;
- `IGG`;
- deflexão.

Arquivos envolvidos principalmente:

- `app.py`;
- `services/overview_service.py`;
- `components/maps/overview_map.py`;
- `components/maps/dnit_map.py`.

---

## 5. Soluções

A tela `Soluções` foi ajustada para focar nos trechos que têm intervenção prevista.

### Filtros dependentes

Os filtros internos passaram a se comportar em cascata.

A ordem prática ficou:

- selecionar `SRE`;
- depois ver só os conceitos/faixas existentes naquele SRE;
- depois ver só os tipos de solução daquele recorte.

Se uma opção escolhida deixa de existir depois de mudar outro filtro, ela é removida.

Isso evita o usuário montar uma combinação impossível.

### Mais de um cenário

A tela passou a aceitar dois cenários/sentidos, tanto no Paragon quanto na Matriz Cadastrada.

Quando isso acontece, o mapa usa o mesmo afastamento visual das outras telas.

### Sem intervenção prevista

Quando não há intervenção para o recorte, a tela agora informa isso de forma clara.

O mapa não desaparece mais sem explicação. A tela mostra o trecho e deixa claro que não existe intervenção prevista para aquela combinação.

---

## 6. Comparativo entre cenários

O comparativo saiu de dentro de `Cenário econômico` e virou uma tela própria.

Essa mudança foi importante porque comparar cenários não é a mesma coisa que analisar economicamente uma metodologia.

A ordem do menu ficou:

- `Visão geral`;
- `Diagnóstico`;
- `Soluções`;
- `Comparativo entre cenários`;
- `Cenário econômico`;
- `IAGON`.

A tela `Projeção` foi removida do menu depois. A leitura de evolução técnica passou a fazer mais sentido dentro do `Comparativo entre cenários`, no modo `Técnico`, porque ali o usuário consegue comparar cenários e segmentos no mesmo contexto.

### Comparação A e Comparação B

A tela passou a trabalhar com dois lados:

- `Comparação A`;
- `Comparação B`.

Em cada lado é possível escolher:

- tipo de matriz;
- um ou mais cenários.

Isso permite comparar Paragon com Matriz, Paragon com Paragon, Matriz com Matriz, ou um conjunto de cenários contra outro.

Também foi adicionada uma trava para impedir comparar exatamente o mesmo recorte com ele mesmo.

### Organização visual

A área de filtros estava muito poluída.

Ela foi reorganizada em duas partes:

- escolha dos cenários de cada lado;
- parâmetros da simulação.

Depois, os parâmetros foram arrumados em linhas para respirar melhor:

- `Horizonte` junto com `Orçamento`;
- `Cálculo` em uma linha própria;

Depois essa regra foi melhorada: o modo deixou de ser só do mapa e virou uma visualização geral da página.

Agora existe um filtro ao lado da rodovia com duas opções:

- `Técnico`;
- `Econômico`.

No modo `Técnico`, a tela mostra a comparação técnica dos mapas.

No modo `Econômico`, a tela mostra os mapas por custo e também os blocos financeiros: resumo comparativo, custo por ano e custo por trecho/SRE.

### Mapas lado a lado

Foram adicionados mapas para comparar os dois lados.

No modo técnico:

- Paragon usa conceito do `IAP`;
- Matriz Cadastrada usa classe do `IRI`.

No modo econômico:

- os trechos são coloridos pelo custo;
- tons de azul mostram custo dentro do orçamento;
- vermelho mostra o que ficou fora do orçamento;
- a escala é feita para comparar os dois lados sem enganar.

Também foi corrigido o caso em que o mapa de um lado aparecia vazio. A geometria passou a vir da base técnica completa, e o custo é aplicado por cima dela.

---

## 7. Cenário econômico

A tela `Cenário econômico` ficou dedicada a uma metodologia por vez.

Ela não tem mais o comparativo embutido. Para comparar cenários, a tela correta agora é `Comparativo entre cenários`.

### Horizonte e cálculo

O filtro de ano foi substituído pela lógica de horizonte.

O usuário escolhe até qual ano quer olhar e decide o tipo de cálculo:

- `Período acumulado`;
- `Somente ano selecionado`.

No período acumulado, o painel soma do primeiro ano disponível até o ano escolhido.

No ano selecionado, o painel olha apenas aquele ano.

Isso evita ano fixo e deixa a tela pronta para bases diferentes.

### Cards econômicos

Os cards principais foram mantidos:

- necessidade total;
- cobertura;
- trechos atendidos;
- orçamento faltante.

Quando há mais de um cenário, a necessidade total mostra o total combinado no card principal.

A divisão por cenário aparece em pílulas pequenas logo abaixo dos cards. Isso substituiu um card separado que repetia a informação e deixava a tela mais pesada.

### Custo por ano e por solução

Os gráficos continuam mostrando a programação econômica.

Na Matriz Cadastrada, as cores das soluções são baseadas na faixa de IRI dominante dos segmentos ligados àquela solução. Ou seja, a cor representa a condição técnica que orienta a intervenção.

Foi removido o custo aproximado por km que existia como fallback.

Antes, quando um trecho tinha intervenção prevista, mas vinha sem custo no banco, o painel podia calcular um valor estimado usando uma tabela fixa no código.

Isso foi retirado porque poderia parecer custo real.

A regra agora é:

- `OK` ou `Sem intervenção` podem ter custo zero;
- intervenção com custo vazio/zerado não deve ser estimada automaticamente;
- nesses casos, o painel mostra `Sem dados de custo para este recorte`.

Essa regra também vale para o comparativo quando ele precisa calcular custo.

### Cronograma por segmento

Foi criado um cronograma por segmento, parecido com um gráfico de Gantt.

Ele aparece depois do custo por solução.

Funcionamento:

- linhas = segmentos/SRE;
- colunas = anos;
- célula preenchida = existe intervenção naquele segmento e naquele ano.

O cronograma tem dois modos:

- `Técnico`: mostra o tipo de intervenção;
- `Econômico`: mostra o valor.

Quando mais de um cenário está selecionado, o cronograma permite alternar o cenário dentro da própria caixa. Isso evita misturar os dois cenários no mesmo quadro.

Depois do primeiro teste visual, o cronograma foi limpo:

- textos auxiliares foram removidos;
- a primeira coluna foi encurtada;
- modo e cenário ficaram dentro do próprio visual;
- a divisão por cenário ficou mais clara.

---

## 8. Mapas e geometria

Essa foi uma das correções mais importantes.

Alguns mapas estavam desenhando a rodovia usando pontos de levantamento. Esses pontos servem para cálculo, mas não são bons para desenhar uma linha contínua.

O resultado eram zigue-zagues, linhas cruzadas e trechos visualmente estranhos.

### Uso de `pista_shape`

Os mapas passaram a usar a geometria limpa de `pista_shape`.

O painel recorta essa geometria pelo km inicial e final de cada segmento.

Isso mantém:

- mesma classe;
- mesma cor;
- mesmo custo;
- mesmo filtro;
- mesmo resultado analítico.

O que muda é o desenho: a linha fica mais próxima da rodovia real.

### Duplicidade de geometria

Também foi tratado o caso em que o banco tem geometrias repetidas ou sobrepostas.

Quando há mais de uma linha cobrindo o mesmo intervalo, o painel mantém a mais completa.

Quando os trechos são vizinhos e fazem parte da cobertura da rodovia, eles continuam sendo mantidos.

### Caminho de retorno

Foi deixado um caminho de retorno para comparação:

`MAP_GEOMETRY_SOURCE=iri`

Com isso, dá para voltar temporariamente ao traçado antigo por pontos de IRI, caso seja necessário comparar.

### Zoom do satélite

O zoom foi limitado ao nível em que o provedor de satélite ainda entrega imagem nativa.

Antes, ao passar desse ponto, o mapa não ganhava detalhe. Ele só ampliava a mesma imagem e ficava embaçado.

---

## 9. Ajustes visuais

Vários ajustes foram visuais, mas não foram apenas “estética”.

Eles foram feitos porque a forma antiga podia atrapalhar a interpretação.

Exemplos:

- barras com contraste melhor;
- legenda menos embolada;
- rótulos de rosca com mais espaço;
- filtros com tamanho mais estável;
- seleção de cenário menos comprida;
- mapas com legendas mostrando só o que aparece no recorte;
- controles movidos para perto do visual que eles afetam.

### Tema claro e escuro

Foi adicionado um botão global para trocar o painel entre tema escuro e tema claro.

Esse botão foi colocado no rodapé do menu lateral esquerdo.

Assim ele fica disponível em todas as telas, mas sem disputar espaço com os filtros principais.

O tema escolhido fica guardado durante a navegação. Então, se eu trocar para o tema claro e mudar de tela, o painel continua claro.

Para garantir isso, o tema também é levado na URL como `theme=light` ou `theme=dark`. Os links do menu lateral preservam esse valor quando abrem outra tela.

O tema escuro continua sendo o padrão.

O tema claro foi feito só para a estrutura do dashboard:

- fundo da página;
- cards;
- bordas;
- textos;
- controles e filtros.

Não alterei as cores técnicas dos dados.

Isso quer dizer que as cores de classe, intervenção, IAP, IRI, soluções e mapas continuam seguindo a mesma regra. A troca de tema não muda cálculo, classificação nem resultado.

Também revisei a leitura do tema claro em pontos que poderiam ficar ruins:

- rótulos;
- legendas;
- filtros;
- opções selecionadas;
- textos auxiliares;
- menus abertos.

Depois, ajustei a `Visão geral` no tema claro. No visual `Extensão das rodovias e recortes`, a caixa interna de cada rodovia/recorte estava ficando com um fundo cinza muito pesado. Removi esse preenchimento no tema claro e mantive só uma borda leve para separar o conteúdo.

Também corrigi rótulos que ainda ficavam brancos no tema claro. Em fundo branco, isso deixava valores e textos de gráfico quase invisíveis. A regra passou a ser: no tema claro, rótulos e textos auxiliares devem usar tons escuros ou cinza legível.

Um caso específico foi o gráfico `Custo por recorte`, que não usa Plotly. Ele é montado em HTML/CSS, então precisei ajustar a classe própria da barra para o valor acima dela não ficar branco no tema claro.

Também ajustei a rosca de `Distribuição IAP`. O centro ainda estava usando o fundo escuro do tema original, então no tema claro ele passou a usar fundo branco. O número central, o texto `IAP médio` e os percentuais ao redor também foram ajustados para tons escuros/cinza.

---

## 10. Comparativo técnico

Na tela `Comparativo entre cenários`, no modo `Técnico`, adicionei um bloco de gráficos para acompanhar indicadores técnicos ao longo dos anos.

A referência veio do visual que eu tinha montado no Power BI.

A fonte usada é a view `vw_desempenho_pavimento_com_trecho`.

Campos usados:

- `IRI`: `iri_antes_intervencao`;
- `Afundamento nas trilhas de roda`: `flechas_antes_intervencao`;
- `FC2 + FC3`: `fc2_fc3_antes_intervencao`;
- `Panelas`: `n_panelas_antes_intervencao`.

Depois de testar a leitura com os campos pós-intervenção, voltei para os campos antes da intervenção. A interpretação ficou: a linha mostra a condição prevista antes da obra daquele ano, e o ponto mostra onde existe intervenção programada.

O comportamento ficou assim:

- posso selecionar um ou mais cenários no comparativo;
- cada cenário aparece como uma linha de cor diferente;
- quando existe intervenção em um ano, aparece um ponto maior sobre a linha;
- o ponto mostra no detalhe qual solução está prevista para aquele ano;
- se a view não tiver o campo ou se o recorte não trouxer dados, não é criado valor inventado.

Corrigi também a regra dos pontos de intervenção no Paragon. O marcador passou a considerar somente `solucao_corretiva_final` preenchida e diferente de `OK`. Antes ele também olhava o código `iapa`, e isso fazia aparecer bolinha de intervenção em anos que não tinham obra programada.

Esse bloco usa os cenários que já estão selecionados em `Comparação A` e `Comparação B`. Não criei outro filtro separado para não deixar a tela mais confusa.

Depois ficou claro que a leitura precisava ser por segmento, não pela média geral da rodovia.

Adicionei um filtro de `Segmento` logo acima do primeiro gráfico. Ele usa o intervalo de km como referência, por exemplo `km 0.00-0.80`.

Com isso, quando dois cenários têm o mesmo recorte de km, as linhas aparecem juntas no mesmo gráfico. Se algum cenário não tiver aquele segmento, ele simplesmente não entra naquele gráfico.

Essa mudança ajuda a comparar cenários sem depender de um gráfico separado para cada um.

Também mantém a regra que venho tentando seguir no painel: se o dado não existe no banco, a tela deve avisar ou ficar sem aquele visual, e não preencher com número falso.

---

## 11. Pontos de atenção que ficaram claros

### Paragon e Matriz Cadastrada são metodologias diferentes

O painel tinha trechos em que parecia bastar trocar o nome do filtro.

Na prática, não basta.

Paragon usa principalmente IAP e regras próprias.

Matriz Cadastrada usa IRI, IGG, deflexão e soluções cadastradas.

Cada tela precisa respeitar essa diferença.

### Ano e horizonte não podem ser fixos

Como o dashboard pode receber outras bases, qualquer ano fixo vira risco.

O painel precisa sempre descobrir os anos disponíveis a partir dos dados.

### Mapas precisam representar a rodovia, não o ruído dos pontos

Os pontos de levantamento são importantes para cálculo.

Mas para desenhar o traçado, a fonte mais adequada é a geometria da pista.

### Documentação precisa continuar simples

Esse arquivo não deve virar uma documentação bonita demais e inútil.

Ele precisa servir para responder perguntas práticas:

- por que isso foi feito?
- qual tela foi afetada?
- que regra mudou?
- como eu valido?
- existe algum risco?

---

## Arquivos mais alterados durante esse ciclo

- `app.py`;
- `services/overview_service.py`;
- `components/maps/overview_map.py`;
- `components/maps/dnit_map.py`;
- `components/cards/metric_card.py`;
- `components/layout/sidebar.py`;
- `core/constants.py`;
- `docs/alteracoes_aplicadas.md`;
- `docs/registro_alteracoes.md`;

Alguns arquivos aparecem em praticamente todas as mudanças porque o projeto ainda concentra muita coisa dentro de `app.py`.

Isso também ficou como um ponto de atenção para evolução futura: aos poucos, a lógica deveria sair de `app.py` e ir para serviços/componentes menores.

---

## Como validar depois de novas mudanças

Sempre que mexer no painel, eu devo conferir pelo menos:

- se `streamlit run app.py` abre sem erro;
- se `app.py` compila;
- se `Visão geral` abre com rodovia, cenário e ano selecionados;
- se `Diagnóstico` não mistura cenários no diagrama;
- se `Soluções` mostra apenas opções existentes no recorte;
- se `Comparativo entre cenários` compara os dois lados corretamente;
- se `Cenário econômico` respeita horizonte, cálculo e orçamento;
- se mapas continuam sem zigue-zague;
- se as legendas mostram só o que aparece no mapa;
- se os números mudam quando ano, cenário e matriz mudam.

Comando simples de validação técnica usado várias vezes:

```powershell
.\venv\Scripts\python.exe -m py_compile app.py
```

Esse comando não substitui validação visual, mas ajuda a pegar erro de sintaxe antes de abrir o Streamlit.

---

## Ajuste visual dos diagramas e gráficos técnicos

Depois dos gráficos técnicos entrarem no `Comparativo entre cenários`, ajustei a apresentação para não parecer um visual separado do resto do painel.

O que foi feito:

- a legenda passou a mostrar a bolinha cinza `Intervenção` junto dos cenários;
- os títulos dos gráficos técnicos voltaram para o padrão visual dos outros cards;
- no tema claro, o primeiro diagrama linear do `Diagnóstico` recebeu fundo branco para ficar consistente com os demais blocos.

Não mudei a regra de cálculo nessa etapa.

---

## Troca do IPT antigo pelo IPI

Comecei a substituir a prioridade antiga do Paragon pela nova metodologia de `IPI`.

A fórmula foi separada em um módulo próprio (`services/ipi.py`) para ficar fácil de testar e revisar.

O que mudou:

- o cálculo antigo usava `VMDA`, `ICDS` e `ICDP` normalizados;
- o novo cálculo usa `ICDS`, `ICDP`, `VMDL` e `VMDP`;
- `VMDL` vem do campo `passeio` da `view_vmda_67`;
- `VMDP` é a soma de `2eixos` até `9eixos`;
- `VMDeq` é calculado como `VMDL + 4 * VMDP`;
- o `IPI` final usa `DQO`, `FT` e os expoentes definidos na metodologia.

Como o tráfego foi ligado:

- a `view_vmda_67` tem rodovia, km inicial e km final;
- o segmento de pavimento usa o trecho de tráfego que contém seu intervalo de km;
- se o segmento termina exatamente na borda, ele continua pertencendo ao trecho anterior;
- se o segmento começa na borda, ele entra no próximo trecho.

Exemplo:

- tráfego km 0 a 12;
- segmento km 0,80 a 1,60;
- esse segmento usa o tráfego do km 0 a 12.

Ponto importante encontrado durante o teste:

- a base tem alguns valores de `ICDS` menores que 1;
- pela fórmula `(5 - ICDS) / 4`, isso faria o dano passar de 100%;
- para não gerar resultado inválido, o dano foi limitado a no máximo 1.

Também encontrei segmentos sem tráfego casado. Esses casos não devem receber prioridade inventada. Precisam ser validados no banco ou tratados como dado faltante.

Observação sobre os nomes:

- a tabela Paragon agora mostra `IPI`, não a prioridade antiga de 1 a 10;
- a ordem da fila usa o maior IPI primeiro;
- o filtro antigo de `Nível de prioridade` foi removido; depois também removi o `IPI mínimo`;
- ainda existe um apelido interno chamado `IPT` em algumas funções antigas, mas ele recebe o mesmo valor do `IPI` para não quebrar o restante do painel.

---

## Limpeza feita depois da revisão geral

Depois da revisão geral do painel, ajustei alguns pontos que ainda podiam confundir a leitura.

O que foi limpo:

- textos do IAGON que ainda falavam em prioridade Paragon de 1 a 10;
- exportações e PDF que ainda mostravam `IPT` ou `Priorização` para Paragon;
- atalhos internos do IAGON que cortavam custo em 8 anos;
- rodovias de exemplo que apareciam como fallback quando o banco não trazia rodovia;
- fallback que tentava tratar código IAP desconhecido como valor real.

Com isso, fica mais claro:

- Paragon usa `IPI`, e maior IPI vem primeiro;
- Matriz Cadastrada continua com uma lógica própria, separada do Paragon;
- se faltar dado real, o painel deve avisar falta de dado, não inventar valor.

---

## Remoção do IPE da tabela Paragon

Removi o `IPE` da tabela Paragon no cenário econômico.

Ele continuou existindo como cálculo auxiliar interno, mas não aparece mais para o usuário nessa tabela.

O motivo é simples: a fila Paragon é ordenada pelo `IPI`. Mostrar `IPE` junto podia confundir e fazer parecer que ele também participava da prioridade final.

A tabela agora fica focada no que interessa para leitura:

- posição na fila;
- trecho/SRE;
- intervalo de km;
- extensão;
- IAP;
- IPI;
- custo;
- soluções.

---

## Matriz Cadastrada no cenário econômico por segmento

Na tela `Cenário econômico`, a Matriz Cadastrada estava mostrando a carteira por `SRE`.

Isso deixava a leitura meio enganosa, porque uma SRE pode ter mais de um segmento. Quando o painel juntava tudo, ele misturava trechos diferentes em uma única linha.

Corrigi para abrir a carteira por segmento.

O que muda na prática:

- a tabela deixa de ser uma lista resumida por SRE;
- cada linha passa a ser um segmento, com seu km inicial, km final, extensão, custo e solução;
- a prioridade da Matriz também passa a ser calculada na chave do segmento;
- o orçamento vai atendendo segmento por segmento;
- quando o filtro de prioridade muda, o mapa acompanha os segmentos filtrados.

Com isso, a Matriz fica mais parecida com a leitura do Paragon, mas sem misturar as metodologias. Paragon continua usando `IPI`; Matriz usa a regra escolhida no seletor de priorização.

---

## Nova priorização da Matriz Cadastrada

Depois revisei a lógica de prioridade da Matriz Cadastrada.

A regra que estava no painel era simplificada demais. Ela usava basicamente `IRI` e `IGG`, mas o dashboard antigo tinha uma lógica mais completa.

Atualizei para uma adaptação dessa lógica antiga.

Agora existem três formas de ordenar a carteira:

- `Técnica`: usa só o `IPT`;
- `Econômica`: usa só o `IPE`;
- `Combinada`: usa `60% IPT + 40% IPE`.

O `IPT` considera:

- `VMDA`;
- `IRI`;
- `DEF`.

O `IPE` considera a eficiência econômica:

- eficiência = `IPT / custo por km * 1000`;
- depois essa eficiência é normalizada para virar um índice.

Depois mudei a escala da Matriz para `0 a 100`, igual ao Paragon.

Antes `IPT`, `IPE` e `Combinada` iam de `0 a 10`. Isso funcionava, mas ficava estranho comparar com o Paragon, que usa `IPI` de `0 a 100`.

Agora os três índices da Matriz também aparecem de `0 a 100`.

A lógica de ordem não mudou. Um trecho que era mais prioritário antes continua sendo mais prioritário agora. A mudança foi só de escala.

A normalização segue a ideia do dashboard antigo, usando logaritmo. Isso evita que valores muito altos distorçam demais a comparação.

Também ajustei a leitura do filtro:

Antes existia um filtro de prioridade com escala invertida. Depois ele virou `Índice mínimo`, mas esse filtro também foi removido para deixar a tela mais simples.

Hoje a prioridade da Matriz é lida pela ordem da tabela e pelo tipo de índice escolhido.

Com isso, fica mais claro para escolher o critério de análise: olhar só a condição técnica, olhar só a eficiência econômica ou usar uma combinação dos dois.

Também removi `IGG` da tabela de priorização da Matriz. Ele continua sendo usado nas telas de diagnóstico, mas saiu dessa tabela para não dar a impressão de que entra no cálculo novo.

O seletor entre `Combinada`, `Técnica` e `Econômica` também foi movido para perto da tabela. A decisão afeta a leitura daquela carteira de segmentos, então ficou mais natural deixar o controle junto do visual.

Depois ajustei a coluna de soluções da Matriz para seguir o mesmo padrão do Paragon. A linha principal ficou mais limpa, com um botão `Ver soluções`. O detalhe abre a programação daquele segmento, separando solução, ano e custo.

Também adicionei o `Ordenar por` nessa tabela da Matriz. Assim a leitura pode ser feita pela fila de prioridade ou pela sequência de km da rodovia, como já acontecia no Paragon.

Depois alinhei os filtros da tabela da Matriz com o padrão do Paragon.

Agora os filtros aparecem no lado esquerdo e seguem esta ordem:

- `Visualização`;
- `Ordenar por`;
- `Índice de priorização`.

O filtro `Visualização` permite alternar entre os segmentos atendidos pelo orçamento e todos os segmentos priorizados.

Depois removi os filtros mínimos do cenário econômico:

- `IPI mínimo`, no Paragon;
- `Índice mínimo`, na Matriz Cadastrada.

Com isso, a tela fica menos carregada e não esconde trechos por um corte extra. A análise passa a depender do orçamento, horizonte, visualização, ordenação e tipo de índice.

---

## Filtro visual para remover trechos no cenário econômico

Adicionei na tela `Cenário econômico` uma caixa expansível para remover trechos da análise.

Ela aparece abaixo do filtro de cenário.

Esse filtro não mexe no banco. Ele só tira o trecho do recorte que está sendo analisado naquele momento.

Usei essa lógica pensando em casos como:

- trecho que já recebeu obra;
- trecho que ainda está na base, mas não deve entrar na simulação atual;
- análise rápida para ver quanto muda a necessidade tirando alguns segmentos.

Quando um trecho é removido, a tela recalcula os números sem ele:

- necessidade total;
- cobertura;
- orçamento faltante;
- trechos atendidos;
- mapa;
- gráficos;
- cronograma;
- tabela final.

Também apliquei isso nas duas metodologias da tela:

- Paragon;
- Matriz Cadastrada.

O trecho só fica fora enquanto estiver selecionado nessa caixa. Se limpar o filtro, ele volta para a análise normalmente.

Também adicionei um atalho por intervalo de km.

Agora dá para digitar algo como `0 a 59`, e o painel seleciona automaticamente os trechos que passam por esse intervalo. A lista manual continua disponível, então o usuário pode conferir e ajustar a seleção depois.
