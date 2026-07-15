# Registro de Alterações

Este arquivo registra, em linguagem simples, todas as mudanças feitas no projeto.

Objetivo:
- explicar o que foi alterado;
- explicar por que a mudança foi feita;
- mostrar quais arquivos foram afetados;
- deixar claro como validar o resultado;
- facilitar a revisão antes de publicar em produção.

## Como este registro será usado

Para cada alteração no código, este documento deve ser atualizado com:

1. Data
2. Problema encontrado
3. Causa identificada
4. Arquivos alterados
5. O que foi adicionado
6. O que foi removido
7. O que foi ajustado
8. Impacto esperado
9. Como validar
10. Pendências, se existirem

## Modelo de registro

### Alteração 001

- Data: preencher
- Problema encontrado: descrever em linguagem simples
- Causa identificada: descrever em linguagem simples
- Arquivos alterados: listar caminhos
- O que foi adicionado: descrever
- O que foi removido: descrever
- O que foi ajustado: descrever
- Impacto esperado: descrever
- Como validar: descrever passo a passo curto
- Pendências: descrever ou informar "nenhuma"

---

## Regras deste documento

- Toda adição de código deve ser registrada.
- Toda remoção de código deve ser registrada.
- Toda alteração de comportamento deve ser registrada.
- Toda mudança deve ser escrita de forma simples, direta e clara.
- Se uma mudança for apenas técnica, ela também deve ser explicada em termos práticos.

---

### Alteração 002

- Data: 2026-07-13
- Problema encontrado: a troca de telas estava lenta, mesmo quando o banco não parecia estar pesado.
- Causa identificada: o sistema tentava se conectar ao Redis repetidas vezes quando o Redis estava indisponível. Cada tentativa falha esperava timeout e isso somava vários segundos na navegação.
- Arquivos alterados: `services/cache.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma janela de espera após falha de conexão com Redis (`REDIS_RETRY_COOLDOWN_SECONDS`, padrão de 30 segundos).
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado: depois que o Redis falha, o sistema para de tentar reconectar imediatamente a cada uso do cache. Durante alguns segundos, ele usa direto o fallback em memória local. Depois desse período, tenta reconectar novamente.
- Impacto esperado: reduzir bastante a lentidão na troca de telas quando o Redis estiver fora do ar, lento ou inacessível.
- Como validar:
  1. abrir o app com o Redis indisponível;
  2. trocar entre telas diferentes;
  3. confirmar que a navegação fica mais rápida do que antes;
  4. observar nos logs que a falha de Redis não aparece em sequência a cada chamada do cache.
- Pendências: medir novamente os tempos para confirmar o ganho e verificar se ainda existe outro gargalo relevante depois dessa correção.

### Alteração 003

- Data: 2026-07-13
- Problema encontrado: mesmo com o cooldown após falha, ainda existe uma primeira tentativa de conexão com Redis quando o ambiente não usa Redis.
- Causa identificada: o código assumia que o Redis deveria ser tentado sempre, mesmo em ambientes locais ou temporários onde esse serviço não está instalado.
- Arquivos alterados: `services/cache.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: a configuração `REDIS_ENABLED`, que permite desligar explicitamente o uso de Redis no ambiente.
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado: quando `REDIS_ENABLED=false`, o sistema não tenta conectar ao Redis e usa diretamente o cache local em memória.
- Impacto esperado: evitar a primeira tentativa de conexão com Redis em ambientes onde ele não será usado.
- Como validar:
  1. definir `REDIS_ENABLED=false` no ambiente;
  2. iniciar o app;
  3. confirmar que não há tentativa de conexão com Redis;
  4. confirmar que o app continua funcionando normalmente com cache local.
- Pendências: decidir se o ambiente local de desenvolvimento deve deixar essa variável desligada por padrão ou apenas documentada para uso manual.

### Alteração 004

- Data: 2026-07-13
- Problema encontrado: a tela `Visão geral` não tinha os filtros de `Rodovia`, `Ano` e `Cenário`.
- Causa identificada: a `Visão geral` usava uma barra superior simplificada, com apenas o filtro de matriz, e tratava a tela sempre como panorama agregado da rede inteira.
- Arquivos alterados: `app.py`, `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - uma barra superior própria da `Visão geral`, com os filtros `Rodovia`, `Tipo de Matriz`, `Cenário` e `Ano`;
  - uma função para listar os anos disponíveis por rodovia, matriz e cenário;
  - suporte de ano explícito nas cargas usadas pela `Visão geral`.
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado:
  - a `Visão geral` continua podendo mostrar a rede inteira;
  - foi adicionada a opção `Todas as rodovias`;
  - quando uma rodovia específica é escolhida, a tela passa a habilitar os filtros de `Cenário` e `Ano`;
  - o filtro de cenário usa o nome vindo de `analise_gerencial_dados_trechos.nome`, ligado ao ciclo selecionado;
  - o filtro de ano passa a usar os anos disponíveis no ciclo selecionado.
- Impacto esperado:
  - permitir análise mais controlada na `Visão geral`;
  - reduzir confusão sobre o que é cenário;
  - aproximar a tela do comportamento esperado no relatório funcional.
- Como validar:
  1. abrir a tela `Visão geral`;
  2. confirmar que agora existem os filtros `Rodovia`, `Tipo de Matriz`, `Cenário` e `Ano`;
  3. deixar `Todas as rodovias` e confirmar que a tela continua mostrando a rede agregada;
  4. escolher uma rodovia específica e confirmar que os filtros de cenário e ano ficam ativos;
  5. trocar cenário e ano e confirmar que os dados da tela respondem ao recorte escolhido.
- Pendências:
  - validar com o usuário se, no modo `Todas as rodovias`, o filtro de `Ano` também deverá funcionar globalmente no futuro;
  - validar se a leitura de `Visão geral` em matriz DNIT deve ter regra própria para todos os indicadores, além do mapa.

### Alteração 005

- Data: 2026-07-13
- Problema encontrado: o nome exibido no filtro de `Cenário` da `Visão geral` estava repetindo informações que já aparecem nos filtros de `Rodovia` e `Tipo de Matriz`.
- Causa identificada: o seletor mostrava o texto completo vindo do banco, incluindo rodovia, segmentação e tipo de matriz.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma formatação específica para o rótulo de cenário na `Visão geral`.
- O que foi removido: do texto exibido ao usuário, foram ocultadas as partes repetidas, como `BR-... (...)` e `MATRIZ PARAGON` ou `MATRIZ REVITALIZA`.
- O que foi ajustado: o valor real do cenário no sistema continua o mesmo, mas o texto mostrado no filtro ficou mais curto e mais claro.
- Impacto esperado: facilitar a leitura do seletor e reduzir poluição visual.
- Como validar:
  1. abrir a tela `Visão geral`;
  2. escolher uma rodovia;
  3. abrir o filtro `Cenário`;
  4. confirmar que um nome como `BR-364 (SH) - DECRESCENTE - MATRIZ PARAGON - GATILHO IQO` aparece apenas como `DECRESCENTE - GATILHO IQO`.
- Pendências: validar se a mesma simplificação também deve ser aplicada em outras telas além da `Visão geral`.

### Alteração 006

- Data: 2026-07-13
- Problema encontrado: a simplificação inicial do nome do cenário removia informação importante de segmentação, como `SH` e `Fixa`.
- Causa identificada: a primeira regra de limpeza priorizava remover repetição visual, mas ainda não preservava de forma inteligente os elementos mais úteis para distinguir cenários em bases diferentes.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma lógica mais inteligente para montar o rótulo do cenário na `Visão geral`.
- O que foi removido: foi deixado de usar o texto bruto completo como única base do rótulo.
- O que foi ajustado:
  - o rótulo agora tenta preservar, nesta ordem, a segmentação (`SH`, `Fixa`, `1 km` etc.), o sentido (`CRESCENTE`, `DECRESCENTE`, `TODOS`, `CR e DE`) e o gatilho (`GATILHO IQO`, `GATILHO REGULAR`, `GATILHO BOM`);
  - partes repetidas como rodovia, `MATRIZ PARAGON`, `MATRIZ REVITALIZA` e `Método de Análise` deixam de aparecer no filtro;
  - a regra também tenta funcionar em nomes mais verbosos, como os que começam com `Rodovia:`.
- Impacto esperado: o filtro de cenário fica mais curto, mas sem perder as informações que realmente diferenciam um cenário do outro.
- Como validar:
  1. abrir a tela `Visão geral`;
  2. escolher uma rodovia com mais de um cenário;
  3. abrir o seletor `Cenário`;
  4. confirmar exemplos como:
     - `BR-364 (SH) - DECRESCENTE - MATRIZ PARAGON - GATILHO IQO` -> `SH - DECRESCENTE - GATILHO IQO`
     - `BR-174 (Fixa) - TODOS - MATRIZ REVITALIZA - GATILHO REGULAR` -> `Fixa - TODOS - GATILHO REGULAR`
     - nomes mais verbosos com `Rodovia:` e `Método de Análise:` -> rótulo curto com a informação realmente útil.
- Pendências: validar em produção se existem outros padrões de nome de cenário que merecem entrar nessa mesma lógica.

### Alteração 007

- Data: 2026-07-13
- Problema encontrado: o card `CUSTO TOTAL` da `Visão geral` não mudava quando o filtro de `Ano` era alterado.
- Causa identificada: o custo da `Visão geral` estava sendo calculado com a programação orçamentária completa do cenário, sem recortar o ano selecionado.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: um recorte de `budget_items` pelo ano selecionado antes do cálculo do custo na `Visão geral`.
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado:
  - o `CUSTO TOTAL` da `Visão geral` agora considera apenas o ano escolhido no filtro, quando esse filtro estiver preenchido;
  - o subtítulo do card passou a deixar isso explícito, mostrando `Necessidade do ano XXXX`.
- Impacto esperado: o custo exibido fica coerente com o recorte de `Ano` aplicado na tela.
- Como validar:
  1. abrir a tela `Visão geral`;
  2. escolher uma rodovia, um cenário e um ano;
  3. anotar o valor do card `CUSTO TOTAL`;
  4. trocar apenas o ano;
  5. confirmar que o valor do custo muda conforme a programação daquele ano.
- Pendências: validar se outros elementos da `Visão geral` também devem passar a refletir o ano com o mesmo rigor do card de custo.

### Alteração 008

- Data: 2026-07-13
- Problema encontrado: em algumas combinações específicas de `Rodovia`, `Cenário` e `Ano`, a tela `Visão geral` mostrava `Sem dados para a malha`, mesmo quando havia dados reais no banco.
- Causa identificada: após uma falha transitória de leitura, o resultado vazio podia ser reaproveitado na `Visão geral`, fazendo a tela parecer sem dados mesmo quando a combinação era válida.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma nova etapa de conferência para a `Visão geral` quando a busca específica por rodovia volta vazia.
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado:
  - a `Visão geral` continua usando cache para desempenho;
  - quando uma combinação específica de filtros por rodovia volta vazia, a tela faz uma nova leitura direta antes de assumir que realmente não há dados;
  - se essa segunda leitura encontrar dados, o vazio antigo deixa de prevalecer.
- Impacto esperado:
  - reduzir falsos casos de `Sem dados para a malha`;
  - melhorar a confiança no uso dos filtros de `Rodovia`, `Cenário` e `Ano`;
  - evitar que uma falha momentânea do banco pareça ausência real de informação.
- Como validar:
  1. abrir a `Visão geral`;
  2. selecionar uma rodovia, cenário e ano que tenham dados;
  3. confirmar que a tela não fica presa em `Sem dados para a malha`;
  4. repetir a seleção após uma troca de filtros e verificar se os dados continuam aparecendo normalmente.
- Pendências: continuar observando se ainda existe algum ponto de falha transitória em consultas específicas do banco.

### Alteração 009

- Data: 2026-07-13
- Problema encontrado: ao trocar o filtro `Tipo de Matriz` para `Matriz Cadastrada`, os filtros de `Cenário` e `Ano` até se ajustavam, mas a `Visão geral` podia ficar sem dados mesmo existindo informação válida no banco.
- Causa identificada: a tela `Visão geral` ainda começava sua montagem pelo fluxo Paragon, mesmo quando a matriz escolhida era DNIT. Ou seja, os filtros mudavam, mas a lógica interna da tela continuava consultando parte da fonte errada.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/relatorio_sgp_dashboards.md`
- O que foi adicionado: separação mais clara entre o caminho `Paragon` e o caminho `Matriz Cadastrada` dentro da montagem da `Visão geral`.
- O que foi removido: foi deixado de usar o começo do fluxo Paragon como base para montar a `Visão geral` quando a matriz escolhida é DNIT.
- O que foi ajustado:
  - quando a tela estiver em `Paragon`, ela continua usando as cargas próprias do Paragon;
  - quando a tela estiver em `Matriz Cadastrada`, ela passa a usar desde o início as cargas próprias do DNIT;
  - os indicadores e textos de contexto da `Visão geral` DNIT também passaram a respeitar melhor essa separação.
- Impacto esperado:
  - evitar falsos casos de `Sem dados` ao usar `Matriz Cadastrada`;
  - reduzir mistura de regras entre duas metodologias diferentes;
  - tornar a tela mais coerente com os filtros exibidos ao usuário.
- Como validar:
  1. abrir a `Visão geral`;
  2. escolher uma rodovia que tenha dados nas duas matrizes;
  3. selecionar `Paragon` e observar os dados;
  4. trocar para `Matriz Cadastrada`;
  5. confirmar que cenário, ano e conteúdo da tela continuam coerentes e que a tela não some indevidamente.
- Pendências: revisar outros trechos do dashboard para localizar pontos onde ainda exista mistura entre fluxo Paragon e fluxo DNIT.

### Alteração 010

- Data: 2026-07-13
- Problema encontrado: ao usar `Visão geral` com `Tipo de Matriz = Matriz Cadastrada` e `Todas as rodovias`, o painel podia disparar erro de conexão com MySQL durante a consulta.
- Causa identificada: a tela estava percorrendo todas as rodovias da base, inclusive rodovias sem dados DNIT, em vez de limitar a leitura às rodovias que realmente têm `Matriz Cadastrada`.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma separação da lista de rodovias usada na `Visão geral` DNIT.
- O que foi removido: foi deixado de usar a lista completa de rodovias quando a tela estiver em `Matriz Cadastrada` com escopo de rede inteira.
- O que foi ajustado:
  - `Paragon` continua usando a lista geral de rodovias;
  - `Matriz Cadastrada` agora usa apenas as rodovias que realmente possuem dados DNIT.
- Impacto esperado:
  - reduzir carga desnecessária no banco;
  - diminuir risco de erro de conexão ao abrir a rede inteira em `Matriz Cadastrada`;
  - deixar a leitura da tela mais coerente com a metodologia escolhida.
- Como validar:
  1. abrir a `Visão geral`;
  2. escolher `Tipo de Matriz = Matriz Cadastrada`;
  3. manter `Todas as rodovias`;
  4. confirmar que a tela carrega sem disparar erro de banco e sem tentar montar rodovias fora do escopo DNIT.
- Pendências: continuar observando se ainda há consultas pesadas demais na rede inteira DNIT, mesmo após limitar o escopo às rodovias corretas.

### Alteração 011

- Data: 2026-07-13
- Problema encontrado: o gráfico horizontal `Extensão das rodovias` estava funcional, mas com contraste baixo entre a barra de fundo e o card, pouca separação entre linhas e leitura visual cansativa.
- Causa identificada: o componente usava uma apresentação muito simples para o estado `OK`, com pouca diferença visual em relação ao fundo do painel, além de espaçamento curto entre itens.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - maior contraste na parte `OK` da barra;
  - cantos mais arredondados;
  - altura consistente da barra;
  - espaçamento vertical mais respirável;
  - tooltip nativo pelo atributo `title`;
  - rótulo curto dentro da parte laranja quando houver espaço suficiente;
  - destaque visual para a linha ativa no contexto da seleção atual;
  - regras de responsividade para telas menores.
- O que foi removido: nenhuma regra de cálculo de largura foi alterada ou removida.
- O que foi ajustado:
  - a lógica das larguras foi mantida exatamente como já estava;
  - a mudança foi apenas de apresentação visual e interação simples.
- Impacto esperado:
  - leitura mais clara;
  - melhor contraste no tema escuro;
  - menos repetição visual;
  - comportamento mais estável em telas menores.
- Como validar:
  1. abrir a `Visão geral`;
  2. localizar o bloco `Extensão das rodovias`;
  3. confirmar que a barra de fundo aparece com contraste maior;
  4. confirmar que a parte laranja mostra um rótulo interno quando houver espaço;
  5. passar o mouse sobre a linha para ver o tooltip;
  6. reduzir a largura da tela e confirmar que o layout continua legível.
- Pendências: avaliar mais adiante se esse gráfico deve permanecer em HTML/CSS nativo ou migrar para Plotly/Altair caso a necessidade de interação fique maior.

### Alteração 012

- Data: 2026-07-13
- Problema encontrado: a parte `OK` da barra ainda estava muito parecida com a cor de fundo do trilho, dificultando distinguir visualmente o que é extensão total e o que é trecho sem intervenção.
- Causa identificada: o azul da barra `OK` estava escuro demais e muito próximo do tom usado no fundo do trilho.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: maior contraste entre trilho e barra `OK`.
- O que foi removido: nenhuma regra de cálculo foi removida.
- O que foi ajustado:
  - o trilho ficou mais escuro;
  - a barra `OK` ficou em um azul mais evidente;
  - o contraste entre fundo, barra total e parte laranja ficou mais fácil de perceber.
- Impacto esperado: leitura visual mais clara do que é `extensão total`, `trecho OK` e `trecho com intervenção`.
- Como validar:
  1. abrir a `Visão geral`;
  2. localizar o gráfico `Extensão das rodovias`;
  3. confirmar que o azul da parte `OK` aparece separado visualmente do fundo escuro do trilho.
- Pendências: nenhuma no momento.

### Alteração 013

- Data: 2026-07-13
- Problema encontrado: a legenda do gráfico `Extensão das rodovias` estava visualmente embolada e difícil de ler.
- Causa identificada: o texto estava todo concentrado em uma única linha corrida, misturando explicação, cores e instrução de clique.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: uma legenda mais organizada, com itens separados e marcadores visuais para cada cor.
- O que foi removido: a legenda em formato de frase corrida deixou de ser usada.
- O que foi ajustado:
  - a explicação geral ficou mais curta;
  - `Precisa de intervenção` e `Trecho OK` passaram a aparecer como itens separados;
  - a instrução de clique ficou isolada em uma nota própria.
- Impacto esperado: leitura mais limpa e mais rápida do bloco.
- Como validar:
  1. abrir a `Visão geral`;
  2. localizar o gráfico `Extensão das rodovias`;
  3. confirmar que a legenda aparece separada em itens, sem ficar embolada.
- Pendências: nenhuma no momento.

### Alteração 014

- Data: 2026-07-13
- Problema encontrado: quando `Cenário` e `Ano` ainda não tinham valor selecionado, os campos ficavam visualmente menores do que os demais filtros.
- Causa identificada: o estado sem seleção usava um bloco visual diferente do selectbox real, com presença visual menor.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: um placeholder visual próprio para filtros ainda não habilitados ou sem seleção.
- O que foi removido: o bloco visual menor usado anteriormente deixou de ser usado nesses casos.
- O que foi ajustado:
  - `Cenário` e `Ano` agora mantêm a mesma altura visual dos outros filtros;
  - o tamanho fica consistente com ou sem valor selecionado;
  - a leitura da faixa de filtros fica mais alinhada;
  - o placeholder também passou a imitar melhor a aparência do select, inclusive com indicador visual à direita.
- Impacto esperado: aparência mais estável e mais profissional na barra de filtros.
- Como validar:
  1. abrir a `Visão geral`;
  2. deixar `Rodovia` em `Todas as rodovias`;
  3. confirmar que `Cenário` e `Ano` continuam com o mesmo tamanho visual dos outros filtros;
  4. escolher uma rodovia e confirmar que a troca para o select ativo não altera a altura do campo.
- Pendências: nenhuma no momento.

### Alteração 015

- Data: 2026-07-13
- Problema encontrado: o bloco `Extensão das rodovias` mudava visualmente demais quando havia apenas uma rodovia em foco, em comparação com o modo de lista com várias rodovias.
- Causa identificada: a linha ativa estava recebendo um destaque forte demais, o que fazia o componente parecer de outro estilo quando só havia um item.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: um destaque mais discreto para a linha ativa.
- O que foi removido: o realce mais pesado da linha selecionada deixou de ser usado.
- O que foi ajustado:
  - a linha ativa continua identificável;
  - mas o visual geral do bloco permanece mais próximo do estado com várias rodovias.
- Impacto esperado: mais consistência visual entre o modo com uma rodovia e o modo com várias rodovias.
- Como validar:
  1. abrir a `Visão geral` com `Todas as rodovias`;
  2. observar o bloco `Extensão das rodovias`;
  3. depois selecionar apenas uma rodovia;
  4. confirmar que o bloco mantém a mesma linguagem visual, sem parecer outro componente.
- Pendências: nenhuma no momento.

### Alteração 016

- Data: 2026-07-13
- Problema encontrado: ao selecionar uma rodovia na `Visão geral` e depois navegar para `Diagnóstico`, a tela seguinte podia abrir com outra rodovia ainda guardada no estado antigo.
- Causa identificada: a `Visão geral` usava um controle próprio para rodovia, mas não sincronizava essa escolha com o estado compartilhado das demais telas.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado: sincronização da rodovia escolhida na `Visão geral` com o estado geral de navegação do dashboard.
- O que foi removido: nenhuma funcionalidade foi removida.
- O que foi ajustado:
  - quando uma rodovia é escolhida na `Visão geral`, ela passa a alimentar também o estado usado por `Diagnóstico` e pelas outras telas;
  - o contexto entre telas fica mais consistente.
- Impacto esperado: ao sair da `Visão geral` para `Diagnóstico`, a rodovia selecionada permanece a mesma.
- Como validar:
  1. abrir a `Visão geral`;
  2. selecionar uma rodovia específica;
  3. navegar para `Diagnóstico`;
  4. confirmar que a mesma rodovia continua selecionada.
- Pendências: nenhuma no momento.

### Alteração 017

- Data: 2026-07-13
- Problema encontrado: o filtro de `Cenário` da tela `Diagnóstico Paragon` seguia uma lógica diferente da `Visão geral`, e a tela ainda não tinha filtro de `Ano`.
- Causa identificada: o `Diagnóstico` ainda estava usando a barra antiga, feita para comparar vários cenários ao mesmo tempo, enquanto a `Visão geral` já tinha uma lógica mais consistente com `Rodovia`, `Tipo de Matriz`, `Cenário` e `Ano`.
- Arquivos alterados: `app.py`, `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - filtro de `Ano` na tela `Diagnóstico`;
  - reaproveitamento da mesma lógica de cenário usada na `Visão geral`.
- O que foi removido:
  - a forma antiga de selecionar vários cenários ao mesmo tempo na barra principal do `Diagnóstico Paragon`.
- O que foi ajustado:
  - `Cenário` passou a usar o mesmo conjunto de opções e o mesmo nome reduzido já adotado na `Visão geral`;
  - a consulta dos dados do `Diagnóstico` passou a respeitar também o `Ano` selecionado;
  - a tela `Diagnóstico DNIT` também passou a receber esse filtro de `Ano`, para manter consistência visual e de navegação;
  - o contexto do `IAGON` nessa tela passou a mostrar também o ano escolhido.
- Impacto esperado: a tela `Diagnóstico` fica coerente com a `Visão geral`, com menos confusão no uso dos filtros e com leitura mais clara do cenário selecionado.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. confirmar que aparecem os filtros `Rodovia`, `Tipo de Matriz`, `Cenário` e `Ano`;
  3. escolher uma rodovia no modo `Paragon`;
  4. verificar que o filtro de `Cenário` mostra os mesmos nomes tratados da `Visão geral`;
  5. trocar o `Ano` e confirmar que os dados da tela respondem a essa mudança.
- Pendências: nenhuma no momento.

### Alteração 018

- Data: 2026-07-14
- Problema encontrado: na tela `Visão geral`, os filtros de `Rodovia`, `Cenário` e `Ano` só permitiam escolher um item por vez.
- Causa identificada: a barra superior dessa tela tinha sido construída com seleção simples, enquanto a necessidade real passou a ser comparar mais de um recorte dentro da mesma tela.
- Arquivos alterados: `app.py`, `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - seleção múltipla para `Rodovia`, `Cenário` e `Ano` na `Visão geral`;
  - montagem automática das opções de cenário conforme as rodovias escolhidas;
  - leitura dos anos disponíveis considerando os recortes selecionados.
- O que foi removido:
  - a limitação antiga de uma única escolha por filtro na `Visão geral`.
- O que foi ajustado:
  - quando há mais de uma rodovia, o nome do cenário passa a mostrar também a rodovia para evitar confusão;
  - quando há mais de um cenário ou mais de um ano, a tela passa a tratar cada combinação selecionada como um recorte próprio;
  - os blocos visuais de extensão e custo passaram a deixar isso mais claro no texto exibido;
  - a montagem dos dados da rede foi adaptada para respeitar múltiplas combinações sem travar a tela.
- Impacto esperado: a `Visão geral` fica mais flexível para análise, permitindo comparar 1, 2 ou mais opções no mesmo painel.
- Como validar:
  1. abrir a `Visão geral`;
  2. selecionar duas ou mais `Rodovias`;
  3. selecionar um ou mais `Cenários`;
  4. selecionar um ou mais `Anos`;
  5. confirmar que os gráficos e cards continuam carregando e que os nomes exibidos deixam claro qual recorte está sendo mostrado.
- Pendências: acompanhar visualmente se o volume de itens selecionados deixa a barra superior carregada demais em telas menores.

### Alteração 019

- Data: 2026-07-14
- Problema encontrado: no bloco `Extensão das rodovias`, o nome completo do recorte ficou grande demais quando a `Visão geral` passou a aceitar múltiplos cenários e anos.
- Causa identificada: a linha estava exibindo diretamente o nome completo do recorte, juntando rodovia, cenário e ano no mesmo espaço visual.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - uso do tooltip para manter o detalhe completo do recorte ao passar o mouse.
- O que foi removido:
  - a exibição direta do nome completo do recorte dentro da linha do gráfico.
- O que foi ajustado:
  - o texto visível na linha passou a mostrar só o nome da rodovia;
  - o detalhe completo continua disponível no `hover`, junto com extensão e percentual de intervenção.
- Impacto esperado: o bloco fica mais limpo, mais legível e menos apertado visualmente.
- Como validar:
  1. abrir a `Visão geral`;
  2. aplicar múltiplos filtros de cenário e/ou ano;
  3. observar o bloco `Extensão das rodovias`;
  4. confirmar que a linha mostra apenas a rodovia;
  5. passar o mouse sobre a linha e confirmar que o tooltip traz o detalhe completo do recorte.
- Pendências: nenhuma no momento.

### Alteração 020

- Data: 2026-07-14
- Problema encontrado: ao selecionar um filtro sem segmentos disponíveis, o mapa sumia da tela `Diagnóstico`.
- Causa identificada: os componentes de mapa encerravam a renderização logo no início quando o conjunto de segmentos vinha vazio.
- Arquivos alterados: `components/maps/overview_map.py`, `components/maps/dnit_map.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - um estado visual vazio para os mapas, mantendo o card renderizado mesmo sem trechos desenhados.
- O que foi removido:
  - a resposta anterior que trocava o mapa por uma mensagem simples fora do card.
- O que foi ajustado:
  - o mapa continua aparecendo com base carregada;
  - uma mensagem discreta informa que não há segmentos para aquele filtro;
  - isso vale tanto para o mapa Paragon quanto para o mapa DNIT.
- Impacto esperado: a tela fica mais estável visualmente e não parece quebrada quando um filtro não retorna segmentos.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. escolher uma rodovia ou combinação de filtros sem segmentos no mapa;
  3. confirmar que o card do mapa continua visível;
  4. confirmar que aparece apenas o aviso de ausência de trechos, sem sumir com o componente.
- Pendências: nenhuma no momento.

### Alteração 021

- Data: 2026-07-14
- Problema encontrado: o card `% TRECHOS CRÍTICOS` podia ser lido como percentual sobre a `Extensão total`, mas a conta interna estava usando apenas a base dos trechos com intervenção.
- Causa identificada: a fórmula antiga dividia os `km críticos` pelo total de km com alguma intervenção, o que gerava uma leitura diferente da esperada ao bater o olho no painel.
- Arquivos alterados: `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - regra mais intuitiva para o indicador de percentual crítico.
- O que foi removido:
  - a base anterior do cálculo, que considerava somente os trechos com intervenção.
- O que foi ajustado:
  - `% TRECHOS CRÍTICOS` passou a ser calculado sobre a `Extensão total` do recorte;
  - o texto interno que documenta essa regra também foi atualizado no serviço.
- Impacto esperado: a conta entre `% TRECHOS CRÍTICOS`, `KM CRÍTICOS` e `EXTENSÃO TOTAL` passa a fazer sentido de forma imediata para quem lê a tela.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. comparar os cards `% TRECHOS CRÍTICOS`, `KM CRÍTICOS` e `EXTENSÃO TOTAL`;
  3. conferir se o percentual agora bate com a divisão de `KM CRÍTICOS` pela `EXTENSÃO TOTAL`.
- Pendências: nenhuma no momento.

### Alteração 022

- Data: 2026-07-14
- Problema encontrado: mesmo após corrigir a conta do percentual crítico, o texto do card ainda podia deixar dúvida sobre o que exatamente estava sendo medido.
- Causa identificada: a legenda curta `Mau + Péssimo` não explicava que o percentual era calculado sobre a extensão total.
- Arquivos alterados: `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - uma explicação mais clara no subtítulo do card.
- O que foi removido:
  - a legenda curta anterior, que era mais ambígua.
- O que foi ajustado:
  - o card `% TRECHOS CRÍTICOS` agora mostra o subtítulo `Percentual da extensão total em Mau + Péssimo`.
- Impacto esperado: o usuário entende mais rápido a lógica do indicador sem precisar conferir a conta por fora.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. localizar o card `% TRECHOS CRÍTICOS`;
  3. confirmar que o subtítulo explica que se trata do percentual da extensão total em `Mau + Péssimo`.
- Pendências: nenhuma no momento.

### Alteração 023

- Data: 2026-07-14
- Problema encontrado: o mapa e o gráfico `Distribuição IAP` não estavam conversando entre si.
- Causa identificada: o mapa ainda aceitava uma lógica visual baseada na solução recomendada, enquanto o gráfico com nome de `Distribuição IAP` estava sendo alimentado por composição de soluções, e não pela classe do IAP.
- Arquivos alterados: `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - alinhamento da lógica para usar o valor numérico do IAP como origem da classe visual.
- O que foi removido:
  - a dependência da solução recomendada para definir a classe do mapa;
  - o uso da composição por solução dentro do gráfico chamado `Distribuição IAP`.
- O que foi ajustado:
  - o mapa passou a usar a classe derivada diretamente do valor numérico do IAP;
  - o gráfico `Distribuição IAP` passou a usar a distribuição por classes (`Excelente`, `Bom`, `Regular`, `Mau`, `Péssimo`);
  - a composição por solução continua existindo no serviço, mas deixou de alimentar esse gráfico específico.
- Impacto esperado: a leitura fica coerente com a regra de negócio definida: `o número manda`, `a classe vem dele`, `a solução depende da classe`.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. comparar o mapa com o gráfico `Distribuição IAP`;
  3. confirmar que as classes mostradas no donut agora fazem sentido com as cores e classes usadas no mapa.
- Pendências: revisar depois se a composição por solução deve ganhar um bloco próprio em outra parte da tela, já que ela continua útil como informação separada.

### Alteração 024

- Data: 2026-07-14
- Problema encontrado: na BR-364, o mapa estava usando apenas um dos arquivos de IRI, mesmo existindo outros arquivos complementares da mesma rodovia.
- Causa identificada: a busca de geometria estava escolhendo só uma importação de IRI, em vez de considerar todas as importações da mesma rodovia que ajudam a compor o traçado.
- Arquivos alterados: `services/overview_service.py`, `docs/registro_alteracoes.md`
- O que foi adicionado:
  - leitura conjunta de todas as importações de IRI da mesma rodovia na montagem da geometria do mapa.
- O que foi removido:
  - a limitação anterior que prendia o mapa a apenas uma importação de IRI.
- O que foi ajustado:
  - a BR-364 passa a aproveitar os arquivos complementares disponíveis para formar o traçado;
  - o mesmo ajuste foi aplicado também no caminho de geometria usado pelo DNIT, para manter consistência.
- Impacto esperado: o mapa deixa de perder trechos quando a cobertura da rodovia está dividida em mais de um arquivo de IRI.
- Como validar:
  1. abrir a tela `Diagnóstico` da BR-364;
  2. observar o mapa;
  3. confirmar que o traçado passa a aproveitar os vários arquivos de IRI disponíveis para a rodovia.
- Pendências: nenhuma no momento.

### Alteração 025

- Data: 2026-07-14
- Problema encontrado: o filtro de faixa por km do bloco de IAP não conversava com o restante da tela, e a distribuição por classe não conseguia refinar junto com o mapa.
- Causa identificada: o intervalo escolhido no diagrama linear ficava restrito ao próprio gráfico, sem ser reaproveitado na montagem do mapa e da distribuição.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - reaproveitamento da faixa de km escolhida no diagrama para também filtrar o mapa e a distribuição IAP;
  - um seletor de faixa IAP no mesmo bloco da distribuição para mostrar somente a classe desejada também no mapa.
- O que foi removido:
  - a separação anterior em que cada bloco respondia sozinho, sem refletir o recorte aplicado no outro.
- O que foi ajustado:
  - o mapa passa a seguir a mesma faixa de km escolhida no controle do diagrama;
  - a distribuição IAP passa a ser recalculada com base nesse mesmo recorte;
  - ao escolher uma faixa como `Bom`, `Mau` ou `Péssimo`, o mapa e a distribuição passam a mostrar apenas aquela classe;
  - foi removida uma duplicidade de renderização do mapa que havia ficado no encaixe inicial dessa melhoria.
- Impacto esperado: a leitura da tela fica mais coerente, porque o usuário consegue afunilar a análise por trecho e por classe sem comparar blocos falando de universos diferentes.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. mover o filtro de faixa por km no bloco `Índice de Aptidão do Pavimento e Soluções Conceptivas`;
  3. confirmar que o mapa e o gráfico `Distribuição IAP` acompanham o mesmo recorte;
  4. usar o seletor de classe IAP;
  5. confirmar que mapa e distribuição passam a mostrar apenas a faixa escolhida.
- Pendências: o clique direto na fatia da rosca ainda não existe, porque o gráfico atual é renderizado em HTML/CSS. Hoje o filtro de classe acontece pelo seletor do próprio bloco.

### Alteração 026

- Data: 2026-07-14
- Problema encontrado: a tela `Soluções` ainda deixava o cenário em um comportamento diferente das outras telas e os filtros internos nasciam de uma base que também incluía trechos sem intervenção.
- Causa identificada: a página ainda usava seleção múltipla de cenário no topo e só descartava `Sem intervenção` depois, já no meio do fluxo.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - barra superior própria para a tela `Soluções`, com cenário em seleção única e nome no mesmo padrão das outras telas;
  - uso da base já filtrada para intervenção antes de montar os filtros internos da página.
- O que foi removido:
  - a mistura de vários cenários ao mesmo tempo dentro da tela `Soluções`;
  - a chance de os filtros internos mostrarem opções vindas de trechos sem intervenção.
- O que foi ajustado:
  - a tela agora trabalha primeiro com `Rodovia` e `Cenário` como filtros mestres;
  - `SRE`, `Conceito IAP` e `Tipo de solução` passam a mostrar só opções que realmente existem dentro daquele recorte mestre;
  - mapa, distribuição e tabela passam a considerar apenas trechos que terão intervenção.
- Impacto esperado: a tela fica mais coerente com o objetivo dela, que é analisar somente o que será feito, sem poluir os filtros com trechos que não entram em obra.
- Como validar:
  1. abrir a tela `Soluções`;
  2. trocar a `Rodovia`;
  3. confirmar que o filtro `Cenário` acompanha apenas os cenários daquela rodovia;
  4. escolher um cenário;
  5. conferir que os filtros internos mostram apenas opções existentes naquele cenário;
  6. confirmar que mapa, gráfico e tabela exibem somente trechos com intervenção.
- Pendências: se depois você quiser, eu posso aplicar o mesmo princípio de filtros mestres também em outras telas derivadas da página de soluções.

### Alteração 027

- Data: 2026-07-14
- Problema encontrado: quando um cenário não tinha intervenção prevista, a tela `Soluções` ficava parecendo quebrada, com vazio genérico no mapa e sem uma explicação clara para o usuário. Além disso, ainda faltava o filtro `Ano`.
- Causa identificada: a tela estava preparada para esconder tudo que não fosse intervenção, mas não tinha um tratamento amigável para o caso em que o recorte inteiro viesse sem obra recomendada.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - filtro `Ano` no topo da tela `Soluções`;
  - aviso claro informando quando não existe intervenção prevista para `Rodovia + Cenário + Ano`;
  - exibição do mapa completo do trecho nesse caso, usando a leitura de condição do pavimento.
- O que foi removido:
  - a sensação de tela vazia sem explicação quando o cenário não tinha obra prevista.
- O que foi ajustado:
  - a tela `Soluções` agora aceita `Rodovia`, `Cenário` e `Ano` como filtros mestres;
  - quando não houver intervenção prevista no recorte mestre, o mapa continua aparecendo;
  - nesse caso, o usuário passa a ver a mensagem `Sem intervenção prevista` em vez de um vazio genérico.
- Impacto esperado: a tela fica mais confiável para leitura, porque o usuário entende se está diante de falta de obra prevista ou de erro/falta de dado.
- Como validar:
  1. abrir a tela `Soluções`;
  2. escolher um caso sem intervenção prevista, como a combinação usada na `BR-174`;
  3. confirmar que aparece um aviso claro;
  4. confirmar que o mapa continua visível com o trecho completo;
  5. confirmar que o filtro `Ano` aparece no topo da tela.
- Pendências: se você quiser depois, eu também posso trocar o texto dos estados vazios secundários para ficarem todos padronizados com essa mesma linguagem.

### Alteração 028

- Data: 2026-07-14
- Problema encontrado: na tela `Diagnóstico` com `Tipo de Matriz = Matriz Cadastrada`, a rosca de `IRI` e o filtro de faixa por km ainda não interagiam com o mapa como já acontece no fluxo do `Paragon`.
- Causa identificada: o mapa DNIT, os donuts e o diagrama linear estavam sendo renderizados a partir da mesma base, mas sem compartilhar o recorte visível escolhido pelo usuário.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - reaproveitamento da faixa de km escolhida no diagrama linear DNIT para filtrar o mapa e os donuts;
  - seletor de faixa da rosca de `IRI` no mesmo padrão já usado no `Paragon`.
- O que foi removido:
  - a separação anterior em que mapa, rosca de `IRI` e faixa por km funcionavam como blocos independentes.
- O que foi ajustado:
  - o mapa DNIT agora acompanha a faixa por km escolhida no diagrama;
  - a distribuição de `IRI` passa a responder ao mesmo recorte e também filtra o mapa pela faixa escolhida;
  - a distribuição de `IGG` passa a refletir o mesmo recorte visível que está no mapa;
  - o seletor da rosca foi adaptado para respeitar a ordem correta das classes DNIT (`Ótimo`, `Bom`, `Regular`, `Ruim`, `Péssimo`).
- Impacto esperado: a leitura da `Matriz Cadastrada` fica consistente com o `Paragon`, permitindo analisar exatamente o mesmo trecho e a mesma faixa visual em todos os blocos principais.
- Como validar:
  1. abrir a tela `Diagnóstico`;
  2. trocar o `Tipo de Matriz` para `Matriz Cadastrada`;
  3. mover o filtro de faixa por km no diagrama linear;
  4. confirmar que mapa e donuts acompanham o mesmo recorte;
  5. usar o seletor de faixa da rosca de `IRI`;
  6. confirmar que o mapa passa a mostrar apenas a faixa de `IRI` escolhida.
- Pendências: o clique direto na fatia da rosca continua não existindo, porque o gráfico atual segue sendo renderizado em HTML/CSS. O filtro por faixa ainda acontece pelo seletor do próprio bloco.

### Alteração 029

- Data: 2026-07-14
- Problema encontrado: em algumas distribuições com fatias muito pequenas, os rótulos de percentual da rosca ficavam sobrepostos e atrapalhavam a leitura.
- Causa identificada: o componente tentava desenhar o percentual para todas as fatias, inclusive as muito pequenas, concentrando vários textos quase no mesmo ponto.
- Arquivos alterados: `components/charts/iap_distribution.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - uma regra visual para esconder os rótulos muito pequenos diretamente na rosca.
- O que foi removido:
  - a tentativa de mostrar percentual em fatias minúsculas, que acabava piorando a leitura.
- O que foi ajustado:
  - os percentuais agora ficam um pouco mais próximos do anel;
  - fatias muito pequenas continuam existindo no gráfico e na legenda, mas deixam de receber rótulo sobreposto na própria rosca.
- Impacto esperado: o gráfico fica mais limpo e legível, principalmente quando há várias classes com participação muito pequena.
- Como validar:
  1. abrir uma distribuição com fatias pequenas, como o caso mostrado da `Matriz Cadastrada`;
  2. observar a parte de cima da rosca;
  3. confirmar que os percentuais deixam de ficar embolados.
- Pendências: se depois você quiser, eu também posso ajustar o componente para mostrar esses percentuais pequenos apenas em tooltip, sem poluir o gráfico.

### Alteração 030

- Data: 2026-07-15
- Problema encontrado: em vários cards visuais, os rótulos e elementos do gráfico estavam começando muito perto dos subtítulos, deixando o espaço visual apertado.
- Causa identificada: os estilos base dos cabeçalhos e corpos dos gráficos usavam espaçamentos curtos e irregulares entre título, subtítulo e área de conteúdo.
- Arquivos alterados: `app.py`, `docs/registro_alteracoes.md`, `docs/alteracoes_aplicadas.md`
- O que foi adicionado:
  - um padrão mais espaçado para os cabeçalhos e subtítulos dos cards visuais.
- O que foi removido:
  - a proximidade excessiva entre subtítulo e área do gráfico em vários blocos.
- O que foi ajustado:
  - os cards com cabeçalho de gráfico passaram a ter uma distância mais uniforme antes do conteúdo visual;
  - subtítulos de gráficos, distribuições, painéis e blocos econômicos passaram a usar a mesma lógica de respiro e altura de linha;
  - a rosca ganhou um pequeno espaço extra antes da área desenhada.
- Impacto esperado: a interface fica mais limpa, organizada e consistente entre os diferentes tipos de visual.
- Como validar:
  1. abrir os principais gráficos do painel;
  2. comparar a distância entre subtítulo e conteúdo visual;
  3. confirmar que os elementos já não ficam colados no texto acima.
- Pendências: se você quiser depois, eu também posso fazer uma segunda passada fina só de ritmo vertical entre cards da página inteira.
