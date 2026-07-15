# Alterações Aplicadas

Este documento foi feito em linguagem simples, para registrar o que já foi ajustado no painel até agora.

### Como este resumo deve ser usado

Este arquivo deve destacar principalmente:
- correções relevantes do dashboard;
- melhorias percebidas na lógica, nos filtros e na leitura das telas;
- pontos que ajudam a demonstrar o retrabalho real do produto.

Erros técnicos intermediários surgidos durante a implementação não precisam virar itens separados aqui, a menos que expliquem uma fragilidade importante do próprio dashboard.

## 13/07/2026

### 1. Melhoria de velocidade na troca de telas

O que foi feito:
- foi corrigido um problema que deixava a navegação entre telas mais lenta do que deveria;
- o sistema estava tentando acessar um serviço de apoio várias vezes seguidas, mesmo quando ele não estava disponível;
- isso foi ajustado para evitar esperas desnecessárias;
- também foi criada uma opção para o sistema funcionar sem depender desse serviço em ambientes onde ele não estiver sendo usado.

Resultado esperado:
- telas abrindo mais rápido;
- menos travamentos ou sensação de demora ao trocar de página;
- funcionamento mais estável em ambientes locais e de teste.

### 2. Criação de registro contínuo das mudanças

O que foi feito:
- foi criado um documento interno para registrar cada alteração realizada no projeto;
- esse registro guarda o que foi feito, por que foi feito e como validar depois.

Resultado esperado:
- facilitar acompanhamento;
- ajudar em revisão antes de publicar;
- manter histórico claro das correções.

### 3. Inclusão de filtros na tela "Visão geral"

O que foi feito:
- foram adicionados os filtros de `Rodovia`, `Cenário` e `Ano` na tela `Visão geral`;
- antes, essa tela trabalhava de forma mais fixa;
- agora ela permite um recorte mais claro da informação.

Resultado esperado:
- leitura mais controlada dos dados;
- mais facilidade para analisar uma rodovia específica;
- redução de dúvidas sobre qual conjunto de dados está sendo mostrado.

### 4. Ajuste no entendimento do cenário

O que foi feito:
- foi alinhado que o cenário exibido no painel deve seguir o nome cadastrado na base;
- o nome do cenário passou a respeitar a estrutura real dos dados ligados ao ciclo analisado.

Resultado esperado:
- evitar confusão sobre o que é cenário;
- deixar a leitura mais próxima da organização real do banco.

### 5. Simplificação visual do nome dos cenários

O que foi feito:
- os nomes dos cenários estavam longos e repetiam informações que já apareciam em outros filtros;
- isso foi ajustado para mostrar apenas o que realmente ajuda a diferenciar um cenário do outro;
- informações importantes como `SH`, `Fixa`, sentido da pista e gatilho foram mantidas.

Exemplos do que passou a ser mostrado:
- `SH - DECRESCENTE - GATILHO IQO`
- `Fixa - TODOS - GATILHO REGULAR`

Resultado esperado:
- filtro mais limpo;
- leitura mais rápida;
- menos repetição visual.

### 6. Ajuste no valor do card "Custo total"

O que foi feito:
- o valor do card `Custo total` na tela `Visão geral` não acompanhava a troca do ano;
- isso foi corrigido;
- agora o valor mostrado considera apenas o ano selecionado no filtro.

Resultado esperado:
- valor mais coerente com o recorte da tela;
- menos risco de interpretação errada;
- leitura mais lógica para quem estiver usando o painel.

### 7. Ajustes visuais para interação

O que foi feito:
- foram ajustados os textos mostrados nos filtros para facilitar a escolha;
- alguns campos passaram a exibir mensagens mais claras quando dependem da escolha de uma rodovia;
- o uso dos filtros ficou mais guiado.

Resultado esperado:
- navegação mais clara;
- menos confusão ao interagir com a tela;
- experiência mais simples para o usuário.

### 8. Correção de escopo na "Matriz Cadastrada"

O que foi feito:
- foi identificado que, ao abrir a `Visão geral` com `Matriz Cadastrada` e `Todas as rodovias`, o painel ainda tentava consultar rodovias fora do grupo que realmente possui dados dessa metodologia;
- isso aumentava a carga no banco e podia gerar erro de conexão;
- a lógica foi ajustada para que a `Matriz Cadastrada` consulte apenas as rodovias que realmente têm dados desse tipo.

Resultado esperado:
- menos erro ao abrir a rede inteira na `Matriz Cadastrada`;
- menos carga desnecessária no banco;
- comportamento mais coerente com a metodologia escolhida.

## Resumo curto

Adicionado:
- filtros de rodovia, cenário e ano na tela `Visão geral`;
- melhoria na velocidade entre telas;
- opção de funcionamento sem dependência obrigatória de serviço de apoio;
- ajustes nos visuais e nos textos para facilitar a interação;
- simplificação do nome dos cenários sem perder a informação importante;
- correção do valor do `Custo total` para respeitar o ano selecionado.

Observação:
- este documento está em formato de acompanhamento simples e pode continuar sendo atualizado como um diário das próximas mudanças.

## Comparação simples entre Paragon e Matriz Cadastrada

### O que hoje é parecido entre os dois

No painel, as duas metodologias usam uma estrutura visual parecida:
- filtros no topo;
- cards;
- mapas;
- tabelas;
- visão de custo;
- organização geral das telas.

Isso passa a impressão de que o comportamento interno também é igual, mas não é.

### O que é diferente entre os dois

Apesar da aparência parecida, a lógica de análise muda bastante:

- **Paragon**
  - trabalha com IAP e índices ligados à condição do pavimento;
  - usa uma forma própria de priorizar os trechos;
  - usa uma leitura própria para solução recomendada;
  - usa uma projeção própria de evolução do pavimento.

- **Matriz Cadastrada**
  - trabalha com IRI, IGG, deflexão e regras da matriz cadastrada;
  - usa outra forma de priorizar os trechos;
  - usa outra lógica para solução;
  - usa outra leitura para o cenário e para a programação das intervenções.

### O problema encontrado

Em vários pontos do dashboard, a interface parecia pronta para trabalhar com as duas metodologias, mas a lógica interna ainda estava misturada.

Em linguagem simples:
- o painel mostrava filtros e caminhos como se tudo já estivesse separado;
- mas por dentro, partes da lógica ainda tratavam uma metodologia usando pedaços da outra.

Isso foi encontrado com clareza na tela `Visão geral`, principalmente ao trocar o filtro `Tipo de Matriz`.

### O que isso mostra sobre o dashboard

Esse comportamento reforça a leitura de que o material desenvolvido anteriormente se aproximava mais de um protótipo funcional do que de um produto final já bem estruturado.

Ou seja:
- existe base de trabalho;
- existe muita coisa pronta visualmente;
- mas parte da lógica ainda precisa ser revista, separada e corrigida com cuidado.

### O impacto disso no retrabalho

O trabalho de correção não é apenas:
- trocar texto;
- ajustar cor;
- mover filtro;
- ou corrigir detalhe visual.

Também será necessário:
- revisar regras;
- separar melhor as metodologias;
- verificar em quais telas há mistura de lógica;
- confirmar se os números mostrados estão usando a fonte correta em cada caso.

### Resumo executivo dessa comparação

Em poucas palavras:
- o painel foi montado para parecer unificado;
- mas `Paragon` e `Matriz Cadastrada` têm regras diferentes;
- e parte dessas diferenças não foi separada corretamente no desenvolvimento anterior;
- por isso o retrabalho atual envolve correção de lógica, e não apenas acabamento.

### Atualização de 2026-07-14

Foi ampliada a flexibilidade dos filtros da tela `Visão geral`.

Em linguagem simples:
- agora `Rodovia`, `Cenário` e `Ano` aceitam escolher mais de uma opção;
- a tela passou a organizar melhor os nomes quando existem várias combinações selecionadas;
- os blocos visuais também foram ajustados para deixar mais claro quando o painel está mostrando vários recortes ao mesmo tempo.

Impacto prático:
- ficou possível comparar 1, 2 ou mais opções na mesma tela;
- a navegação da análise ficou mais útil para conferência e comparação;
- a lógica interna da montagem da tela precisou ser adaptada para acompanhar essa nova forma de filtro.

### Atualização de 2026-07-14 2

Foi melhorada a conversa interna da tela `Diagnóstico`.

Em linguagem simples:
- a faixa de km escolhida no bloco de `Índice de Aptidão do Pavimento` agora também afeta o mapa e a distribuição;
- o bloco de `Distribuição IAP` ganhou um seletor para mostrar só a faixa desejada, como `Bom`, `Regular`, `Mau` ou `Péssimo`;
- isso evita comparar números e trechos que estavam sendo mostrados com recortes diferentes.

Impacto prático:
- o mapa e a distribuição passam a responder juntos ao mesmo trecho selecionado;
- a análise fica mais clara quando o objetivo é olhar apenas uma faixa de condição;
- foi corrigido também um encaixe visual/técnico que estava renderizando o mapa duas vezes nessa parte da tela.

Observação importante:
- o clique direto na fatia da rosca ainda não foi criado;
- por enquanto, o filtro por faixa está funcionando pelo seletor exibido no próprio bloco da distribuição.

### Atualização de 2026-07-14 3

Foi reorganizada a lógica da tela `Soluções`.

Em linguagem simples:
- o cenário no topo passou a funcionar no mesmo estilo das outras telas;
- a tela deixou de misturar vários cenários ao mesmo tempo;
- os filtros internos agora nascem apenas do que realmente existe na rodovia e no cenário escolhidos;
- além disso, a página passou a considerar só os trechos que terão intervenção.

Impacto prático:
- o usuário deixa de ver opções de filtro que não fazem sentido para aquele recorte;
- mapa, gráfico e tabela ficam alinhados ao objetivo real da tela, que é mostrar o que será tratado;
- a navegação fica mais clara porque a análise passa a começar pelos filtros mestres `Rodovia` e `Cenário`.

### Atualização de 2026-07-14 4

Foi melhorado o comportamento da tela `Soluções` quando não existe intervenção prevista.

Em linguagem simples:
- a tela ganhou também o filtro `Ano`;
- quando a combinação escolhida não tiver obra prevista, o painel agora avisa isso de forma clara;
- em vez de parecer vazio ou quebrado, o mapa continua aparecendo com o trecho completo.

Impacto prático:
- fica mais fácil entender que o caso é `sem intervenção prevista`, e não erro de carregamento;
- a leitura visual do trecho continua disponível mesmo sem obra recomendada;
- a análise da tela `Soluções` ficou completa com os filtros mestres `Rodovia`, `Cenário` e `Ano`.

### Atualização de 2026-07-14 5

Foi ampliada a interação da `Matriz Cadastrada` na tela `Diagnóstico`.

Em linguagem simples:
- a faixa por km do diagrama linear agora afeta também o mapa e os donuts;
- a rosca de `IRI` ganhou o mesmo tipo de seletor por faixa que já existia no `Paragon`;
- ao escolher uma faixa como `Bom`, `Regular` ou `Ruim`, o mapa passa a mostrar só aqueles trechos.

Impacto prático:
- a leitura da tela fica mais coerente porque mapa e gráficos passam a falar exatamente do mesmo recorte;
- o comportamento da `Matriz Cadastrada` fica mais parecido com o que já foi ajustado no `Paragon`;
- o donut de `IGG` também acompanha o recorte visível atual, para não ficar mostrando um universo diferente do mapa.

### Atualização de 2026-07-14 6

Foi feito um ajuste visual na rosca de distribuição.

Em linguagem simples:
- quando uma fatia fica muito pequena, o percentual deixa de ser escrito em cima da rosca;
- esses casos continuam aparecendo normalmente na legenda;
- os rótulos maiores também foram aproximados um pouco do gráfico para evitar embolar no topo.

Impacto prático:
- o gráfico fica mais limpo;
- a leitura melhora nos casos em que existem várias fatias pequenas ao mesmo tempo;
- nenhuma conta foi alterada, só a forma de mostrar.

### Atualização de 2026-07-15

Foi padronizado o espaçamento dos subtítulos e da área visual dos gráficos.

Em linguagem simples:
- os gráficos ganharam mais respiro entre o texto explicativo e a parte desenhada;
- esse ajuste foi aplicado no padrão base dos cards, e não só em um gráfico isolado;
- o objetivo foi deixar a leitura mais limpa e organizada.

Impacto prático:
- os elementos deixam de parecer colados no subtítulo;
- os cards passam a ter um ritmo visual mais consistente entre si;
- a navegação fica mais agradável sem alterar os dados ou cálculos.

### Atualização de 2026-07-15 2

Foi reorganizado o filtro da tela `Cenário econômico`.

Em linguagem simples:
- saiu o filtro antigo com linguagem de `sentidos`;
- entrou um filtro de `Cenários`, no mesmo estilo de seleção múltipla usado em outras telas;
- também foi incluído o filtro de `Ano`.

Impacto prático:
- a tela fica mais padronizada com o restante do dashboard;
- a escolha de cenários fica mais clara para o usuário;
- o recorte econômico passa a poder considerar também o ano escolhido.
