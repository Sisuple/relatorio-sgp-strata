# Relatório SGP - Dashboards

**Data:** 10/07/2026  
**Status:** diagnóstico inicial para priorização de melhorias  
**Público:** gestão, operação e equipe técnica

## 1. Objetivo do documento

Este documento apresenta o diagnóstico inicial do sistema de dashboards SGP, organizado pelas telas que compõem a jornada de análise. O objetivo é apoiar a decisão sobre o que deve ser corrigido, melhorado ou estruturado antes de novas evoluções.

O sistema consolida informações de pavimentos rodoviários e busca apoiar a sequência: diagnóstico técnico, definição de solução, projeção de desempenho, análise de risco e avaliação econômica.

## 2. Resumo executivo

O sistema possui uma base funcional e concentra informações relevantes para a gestão de rodovias. Há integração com banco de dados, filtros, mapas, gráficos, priorização de intervenções, simulações econômicas e o módulo IAGON.

O principal ponto de atenção é de manutenção e confiabilidade futura: regras importantes, telas e parte das consultas estão concentradas em poucos arquivos. Também foram identificadas configurações e dependências que precisam ser alinhadas para reduzir o risco de falhas em instalação, atualização ou troca de ambiente.

As recomendações foram divididas por tela para facilitar a validação com as áreas de negócio. Antes de qualquer correção, cada item deve ser confirmado quanto à regra de negócio, prioridade e responsável pela validação.

## 3. Escala de prioridade

| Prioridade | Significado |
| --- | --- |
| Alta | Pode impedir o funcionamento, gerar informação inconsistente ou dificultar implantação e suporte. |
| Média | Melhora a utilização, a clareza das análises ou reduz risco de manutenção. |
| Baixa | Evolução desejável, sem impacto imediato no funcionamento atual. |

## 4. Melhorias e pontos de atenção por tela

### 4.1 Visão Geral

**Finalidade da tela:** apresentar uma leitura consolidada da malha, permitindo que a gestão identifique rapidamente a situação das rodovias e os segmentos que exigem atenção.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Filtros globais | Padronizar e disponibilizar os filtros de Rodovia, Ano e Cenário de forma clara. Hoje a aplicação trabalha com seletores de rodovia, cenário e matriz/metodologia, mas o filtro de ano precisa ter sua regra e disponibilidade confirmadas. | Comparações mais confiáveis e redução de interpretações equivocadas. | Alta |
| Contexto entre telas | Garantir que a seleção feita na Visão Geral seja preservada ao navegar para as demais telas, quando aplicável. | Evita que o usuário analise telas com filtros diferentes sem perceber. | Alta |
| Estados sem dados | Exibir mensagens objetivas quando não houver resultado para a combinação de filtros escolhida. | Reduz dúvidas sobre falha do sistema versus ausência de dados. | Média |
| Indicadores principais | Validar com a gestão quais indicadores devem ser prioritários e manter definição/legenda acessível. | Facilita leitura por públicos não técnicos. | Média |
| Quebra entre metodologias | A tela foi montada de forma híbrida: os filtros mudam entre Paragon e Matriz Cadastrada, mas parte da lógica interna ainda seguia o fluxo Paragon mesmo quando a matriz escolhida era DNIT. Na prática, isso faz a interface parecer pronta para duas metodologias, mas com comportamento inconsistente ao aplicar certos filtros. | Gera falso "sem dados", dificulta confiança no painel e aumenta o retrabalho para correção da lógica real. | Alta |

#### Priorização de trechos: divergência a estruturar

A Visão Geral apresenta a quantidade de “Trechos Prioritários”, mas a regra atual do Streamlit não reproduz a versão anterior desenvolvida no Power BI. A divergência deve ser tratada como um item de estruturação da metodologia, antes de qualquer mudança no ranking exibido.

| Etapa | Referência Power BI | Implementação atual no Streamlit (Paragon) |
| --- | --- | --- |
| Índice técnico | `0,4 × VMDA + 0,35 × IRI + 0,25 × DEF` | `0,5 × VMDA + 0,3 × ICDS + 0,2 × ICDP` |
| Índice econômico | Normalização logarítmica da eficiência média por código | Normalização linear da eficiência por segmento |
| Priorização final | `0,6 × IPT + 0,4 × IPE` | Usa somente o IPT e o reescala em níveis de 1 a 10 |
| Unidade de análise | Eficiência média por código/SNV | Segmento individual; o SNV herda a condição do pior segmento |
| Leitura da escala | Pendente de confirmação | Menor número significa maior prioridade |

**Impacto atual:** o total de itens classificados como Alta ou Crítica na Visão Geral pode divergir do resultado do Power BI. Essa diferença também pode afetar a ordem de investimentos nas telas de Soluções e Cenário Econômico.

**Decisão pendente:** antes de alterar o sistema, estruturar e validar a regra de priorização, incluindo as fórmulas de normalização de VMDA, IRI, DEF e eficiência, o nível de agrupamento por código/SNV e o sentido da escala de prioridade. A validação deve comparar um conjunto conhecido de códigos do Power BI com o resultado esperado no Streamlit.

#### Quebra de fluxo entre Paragon e Matriz Cadastrada

Durante os ajustes na `Visão geral`, foi identificado que a tela não separava de forma completa o caminho de dados da metodologia Paragon e o caminho da `Matriz Cadastrada`. Em alguns casos, o filtro de `Tipo de Matriz` mudava corretamente o cenário e o ano exibidos ao usuário, mas a montagem interna da tela ainda começava pelo fluxo Paragon.

**Consequência prática:** o painel podia mostrar `Sem dados para a malha` mesmo quando havia dados válidos na `Matriz Cadastrada`. Isso não caracteriza apenas um erro pontual de tela, mas um sinal de que parte do dashboard foi construída como protótipo funcional, com acoplamento entre regras de metodologias diferentes.

**Leitura de gestão:** essa descoberta reforça que o trabalho atual não é apenas de ajuste visual ou correção isolada. Há necessidade de revisão lógica em trechos do dashboard para garantir que cada metodologia use sua própria fonte, seus próprios cálculos e sua própria leitura na interface.

### 4.2 Diagnóstico

**Finalidade da tela:** detalhar a condição do pavimento, com apoio de mapas, trechos, indicadores e classificações técnicas.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Regras de classificação | Centralizar as faixas e classificações técnicas utilizadas para condição do pavimento. Parte dessas regras está gravada diretamente no código e também aparece em consultas ao banco. | Menor risco de resultados diferentes para o mesmo trecho. | Alta |
| Legendas e cores | Unificar as cores usadas em mapas, gráficos e tabelas para cada condição ou intervenção. | Leitura mais rápida e consistente. | Média |
| Detalhamento por trecho | Confirmar quais informações devem aparecer ao selecionar um trecho e manter o mesmo padrão nas telas relacionadas. | Melhor rastreabilidade da análise. | Média |
| Qualidade dos dados | Identificar campos obrigatórios e comunicar ao usuário quando houver dados incompletos, antigos ou indisponíveis. | Evita decisões baseadas em informação parcial. | Alta |

#### Apuração do IAP: pontos a validar

O IAP não é calculado do zero pelo dashboard. A aplicação consulta o valor `iapa` gravado na base de intervenções, filtra por rodovia, análise, ciclo e ano, converte o valor para escala exibida e calcula a média ponderada pela extensão de cada trecho.

**Regra de conversão por trecho:** `IAP exibido = iapa / 100`.

Exemplos da consulta de banco enviada para esta análise: `iapa = 535` corresponde a IAP `5,35`; `iapa = 335` corresponde a IAP `3,35`; e `iapa = 225` corresponde a IAP `2,25`. A coluna `ano` identifica o ano associado ao registro de projeção.

**Figura 1 - Evidência de valores armazenados para o IAP.** A captura recebida mostra as colunas de ciclo, segmento/pista, ano e `iapa`, confirmando que o valor é armazenado em centésimos e precisa ser dividido por 100 antes de ser apresentado no painel.

| Ponto identificado | Possível impacto | Ação de validação |
| --- | --- | --- |
| Ano usado na tela | Quando o ano não é informado, a aplicação utiliza o primeiro ano de projeção disponível do ciclo. Esse ano pode ser diferente do ano que o usuário espera consultar. | Confirmar se o Diagnóstico deve exibir o ano-base, o ano da inspeção ou permitir escolha explícita de ano. |
| Faixas de classificação | A regra numérica passa de `++ Regular` para `- Regular`; a categoria `+ Regular` existe em referências visuais, mas não possui faixa própria na regra atual. | Validar as faixas oficiais do IAP e corrigir a classificação após aprovação técnica. |
| Cor/classe no mapa | Quando existe solução corretiva, o mapa pode classificar o trecho pela solução, e não pelo IAP numérico. Por exemplo, um IAP 2,25 pode aparecer como “Péssimo” se tiver solução `REC`. | Definir se o mapa deve representar condição medida, solução recomendada ou disponibilizar as duas leituras de forma claramente separada. |
| Regra duplicada | As faixas de classificação existem tanto no código Python quanto na consulta ao banco. | Centralizar a regra para impedir divergência em atualizações futuras. |

**Classes atualmente apresentadas no dashboard:** `Excelente`, `Bom`, `++ Regular`, `+ Regular`, `- Regular`, `Mau` e `Péssimo`.

**Faixas atualmente aplicadas na classificação numérica:** `Excelente` (IAP >= 4,01); `Bom` (3,01 a 4,00); `++ Regular` (2,51 a 3,00); `- Regular` (2,01 a 2,50); `Mau` (1,01 a 2,00); e `Péssimo` (até 1,00). A classe `+ Regular` aparece na legenda e pode ser atribuída pela solução corretiva, mas não possui faixa própria no cálculo numérico atual.

**Risco atual:** o usuário pode interpretar mapa, indicador e tabela como se todos mostrassem a mesma dimensão do IAP, quando parte da visualização pode estar refletindo a solução corretiva. A validação deve comparar uma rodovia, pista/faixa e trecho conhecidos com o valor bruto do banco antes de qualquer alteração de regra.

#### Inconsistência entre mapa e rosca de “Distribuição IAP”

**Evidência observada:** a captura da tela mostra trechos azuis classificados como “Excelente” no mapa, enquanto a rosca não apresenta essa faixa e exibe apenas parcelas relacionadas às intervenções. O IAP médio mostrado no centro da rosca (`4,91`) também não deve ser interpretado como a média das faixas desenhadas no anel.

| Componente | Regra atual | Consequência |
| --- | --- | --- |
| Mapa | Para trechos com solução, usa a classe associada à solução; sem solução, usa o IAP numérico. | Um trecho azul pode ser “Excelente” pelo valor numérico do IAP e não possuir solução corretiva. |
| Rosca intitulada “Distribuição IAP” | Recebe a composição das soluções corretivas e considera somente trechos cuja solução não é nula. | Trechos sem intervenção, inclusive os excelentes, ficam fora do gráfico. Os percentuais representam apenas a extensão com intervenção. |
| Distribuição numérica do IAP | A aplicação já consulta e calcula essa distribuição por faixas de IAP, mas ela não é a fonte enviada para a rosca atual. | Existe dado adequado para o gráfico, porém ele não está sendo utilizado na tela. |

**Regra de coerência do IAP médio:** o valor exibido no centro da rosca deve ser calculado sobre a mesma população exibida no anel. Enquanto a rosca considerar somente trechos com solução corretiva, o centro deve mostrar o IAP médio somente desses trechos e ser identificado como tal. Se a rosca passar a representar todos os trechos por faixa numérica de IAP, o IAP médio geral poderá permanecer no centro.

**Problema:** o título e a leitura esperada da rosca são de distribuição de condição/IAP, mas seu conteúdo é de distribuição de soluções corretivas. Isso torna a comparação visual com o mapa inconsistente e pode induzir a interpretação errada da condição da rodovia.

**Solução proposta para validação futura:** usar na rosca a distribuição por faixas numéricas do IAP, incluindo todos os trechos do filtro. Caso a distribuição de intervenções seja necessária, mantê-la em gráfico separado com o título “Distribuição de Soluções Corretivas” e informar que o percentual considera somente os trechos com solução.

### 4.3 Soluções

**Finalidade da tela:** apoiar a escolha de soluções de manutenção ou recuperação, considerando condição, prioridade e custo.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Critérios de priorização | Documentar e validar os pesos, limites e fórmulas usados para classificar prioridades. Atualmente existem parâmetros fixos no código. | Transparência na recomendação e facilidade para revisão de regras. | Alta |
| Parâmetros de negócio | Separar parâmetros que podem mudar com o tempo, como custos, pesos e faixas de decisão, do código da aplicação. | Ajustes futuros sem necessidade de alteração técnica extensa. | Alta |
| Explicação da recomendação | Mostrar, em linguagem simples, por que cada solução foi sugerida para o trecho selecionado. | Maior confiança da equipe usuária no resultado. | Média |
| Consistência visual | Reutilizar a mesma nomenclatura e cor das soluções em toda a aplicação. | Reduz ambiguidade entre telas. | Média |

### 4.4 Cenário Econômico

**Finalidade da tela:** permitir a comparação de alternativas de investimento e seus efeitos econômicos.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Premissas da simulação | Exibir claramente as premissas adotadas em cada cenário, incluindo horizonte, custos e critérios de cálculo. | Comparações auditáveis e compreensíveis. | Alta |
| Salvar ou exportar cenário | Avaliar a necessidade de registrar cenários analisados e permitir exportação do resultado. | Apoio a reuniões, prestação de contas e rastreabilidade. | Média |
| Validação dos cálculos | Criar casos de validação para garantir que alterações futuras não mudem o resultado econômico indevidamente. | Redução de risco em decisões financeiras. | Alta |
| Linguagem dos indicadores | Complementar siglas e termos técnicos com descrição simples. | Acesso mais fácil para públicos não técnicos. | Média |

### 4.5 Projeção

**Finalidade da tela:** apresentar uma estimativa da evolução da condição do pavimento ao longo do tempo, com ou sem intervenção.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Base da projeção | Documentar as regras, curvas e dados usados para produzir a estimativa de desempenho. | Clareza sobre limites e confiança da projeção. | Alta |
| Comparação de alternativas | Tornar explícita a comparação entre manter, intervir e adiar intervenção, quando os dados permitirem. | Melhor apoio à decisão de investimento. | Média |
| Avisos sobre incerteza | Informar que a projeção é uma estimativa e depende da qualidade/atualização dos dados de entrada. | Uso mais responsável da informação. | Média |
| Integração com soluções | Garantir que a solução escolhida seja refletida de forma consistente nas projeções relacionadas. | Coerência entre diagnóstico, solução e prognóstico. | Alta |

### 4.6 IAGON

**Finalidade da tela:** oferecer uma camada de apoio à interpretação das informações do painel por meio de inteligência artificial.

| Item | Situação identificada ou melhoria proposta | Impacto esperado | Prioridade |
| --- | --- | --- | --- |
| Dependências de instalação | Regularizar dependências utilizadas pelo módulo que não constam na lista principal de instalação. | Evita falha ao implantar em nova máquina ou servidor. | Alta |
| API da OpenAI | Criar ou assumir conta/projeto corporativo da API, configurar cobrança, gerar a chave e registrá-la no ambiente como `API_OPENAI_KEY`. | Sem a chave, o IAGON permanece indisponível, mesmo que a tela e as dependências estejam instaladas. | Alta |
| Arquivos de apoio | Confirmar e versionar os arquivos e diretórios esperados pelo módulo, como dados locais e instruções de contexto. | Reduz risco de funcionamento parcial fora do ambiente atual. | Alta |
| Uso em produção | Confirmar se o IAGON já faz parte do escopo produtivo ou se está em fase de preparação. | Define prioridade e nível de investimento adequado. | Alta |
| Limites da resposta | Apresentar aviso de que respostas do assistente devem apoiar, e não substituir, a análise técnica e a validação humana. | Uso mais seguro e alinhado ao processo decisório. | Alta |

### 4.7 Credenciais e serviços externos

**Situação identificada:** o IAGON não possui uma chave de API da OpenAI configurada no ambiente local. A chave do Google Maps está preenchida no arquivo de configuração local, mas seu funcionamento depende da habilitação e das restrições corretas no Google Cloud.

#### IAGON e OpenAI

O IAGON não usa a assinatura comum do ChatGPT para responder. Ele faz chamadas para a API da OpenAI e, por isso, precisa de uma chave vinculada a uma conta/projeto com responsabilidade definida sobre acesso e cobrança.

> **Evidência visual recebida em 10/07/2026:** na tela `API keys` do projeto selecionado há `0 results` e o botão `Create new secret key`. Isso indica que não há chave ativa disponível nesse projeto para configurar o IAGON.

| Ação necessária | Responsável recomendado | Observação |
| --- | --- | --- |
| Definir a conta corporativa dona da API | Gestão/TI | A conta e a cobrança não devem depender da conta pessoal de um desenvolvedor. |
| Criar ou assumir o projeto da API | Gestão/TI | O projeto deve ser destinado ao IAGON e ter orçamento/limite de uso definido. |
| Criar chave de API | Administrador do projeto | Criar em `API Keys > Create new secret key`; a chave completa só é mostrada uma vez. |
| Configurar a chave no ambiente | Equipe técnica autorizada | Registrar apenas em `.env`, com o nome `API_OPENAI_KEY`. Nunca publicar em Git, e-mail, chat ou documento. |
| Validar o IAGON | Área de negócio e equipe técnica | Confirmar resposta, contexto técnico e tratamento de erros antes de liberar para usuários. |

**Risco atual:** enquanto a chave não estiver disponível no ambiente, o IAGON ficará indisponível. A aplicação já identifica esse estado e informa que a chave precisa ser configurada.

#### Google Maps e Street View

No painel, o Google Maps é usado especificamente para abrir o Street View ao clicar em um trecho do mapa. O mapa analítico principal não depende dessa chave, pois é renderizado por outro componente.

| Ação necessária | Responsável recomendado | Observação |
| --- | --- | --- |
| Criar ou identificar o projeto no Google Cloud | Gestão/TI | A empresa deve ser proprietária do projeto e da conta de faturamento. |
| Associar conta de faturamento válida | Gestão/TI | A Maps Embed API exige conta de faturamento, mesmo sendo disponibilizada sem cobrança por requisição. |
| Habilitar `Maps Embed API` | Administrador do Google Cloud | Esta é a API efetivamente usada pelo código para o Street View embutido. |
| Criar chave exclusiva para o Embed | Administrador do Google Cloud | Evita que a mesma chave seja usada indevidamente em outros serviços do Google. |
| Restringir a chave | Administrador do Google Cloud | Restringir à API `Maps Embed API` e aos sites autorizados, incluindo `http://localhost:8501/*`, `http://127.0.0.1:8501/*` e o domínio de produção. |
| Configurar e validar | Equipe técnica autorizada | Registrar em `.env` como `GOOGLE_MAPS_API_KEY`, reiniciar o Streamlit e clicar em um trecho do mapa. |

**Risco atual:** uma chave preenchida no `.env` não garante funcionamento. O Street View pode falhar se a API não estiver habilitada, se não houver faturamento válido ou se o endereço local/de produção não estiver autorizado nas restrições da chave.

## 5. Pontos estruturais transversais

| Tema | Diagnóstico inicial | Recomendação | Prioridade |
| --- | --- | --- | --- |
| Organização do código | A aplicação principal concentra muitas responsabilidades: navegação, interface, regras de negócio e parte das análises. | Evoluir gradualmente para módulos por tela e serviços com responsabilidades menores. | Alta |
| Regras de negócio | Há faixas, pesos, cores e critérios definidos diretamente no código em mais de um local. | Centralizar e, quando validado, parametrizar em configuração ou banco de dados. | Alta |
| Documentação de implantação | Existem instruções divergentes sobre caminho de instalação, nome do serviço e endereço de execução. | Definir uma fonte oficial de instalação e atualizar os demais documentos. | Alta |
| Testes automatizados | Não foram identificados testes automatizados no repositório. | Criar testes progressivos para cálculos, classificações e cenários críticos. | Alta |
| Ambiente de desenvolvimento | O repositório contém um ambiente virtual local e depende de banco de dados real. | Retirar artefatos locais do controle de versão e definir ambiente seguro para homologação. | Média |
| Monitoramento de falhas | Há tratamento de erros de conexão, mas é preciso padronizar mensagens e registros de falha. | Melhorar mensagens ao usuário e registrar erros para suporte. | Média |

## 6. Plano sugerido de execução

### Fase 1 - Estabilização e confirmação de regras

1. Validar com as áreas responsáveis os filtros, indicadores, classificações e fórmulas atualmente utilizados.
2. Corrigir dependências e arquivos necessários para instalação completa, especialmente os relacionados ao IAGON.
3. Consolidar a documentação oficial de implantação e operação.
4. Definir os dados e acessos necessários para um ambiente de homologação.

### Fase 2 - Melhorias funcionais por tela

1. Padronizar filtros e preservar contexto de análise entre telas.
2. Melhorar mensagens para ausência de dados, falhas e limitações de informação.
3. Padronizar cores, nomenclaturas, legendas e explicações das recomendações.
4. Implementar as melhorias priorizadas em ciclos pequenos, revisáveis e testáveis.

### Fase 3 - Sustentação e evolução técnica

1. Separar gradualmente responsabilidades da aplicação principal em módulos menores.
2. Centralizar regras de negócio e reduzir duplicações.
3. Criar testes automatizados para cálculos e classificações de maior impacto.
4. Registrar decisões técnicas e regras de negócio relevantes para manutenção futura.

## 7. Riscos caso não sejam tratados

1. Dificuldade para atualizar regras ou corrigir problemas sem afetar outras telas.
2. Resultados possivelmente inconsistentes quando uma mesma regra estiver duplicada em locais diferentes.
3. Falha de instalação em um novo ambiente por dependências, arquivos ou configurações ausentes.
4. Dependência excessiva do conhecimento de quem hoje conhece o código e o ambiente.
5. Redução da confiança dos usuários se filtros, cores, critérios ou mensagens não forem consistentes.

## 8. Decisões necessárias da gestão

1. Confirmar quais telas e funções são prioritárias para uso operacional imediato.
2. Definir os responsáveis por validar regras técnicas, econômicas e de priorização.
3. Informar se o módulo IAGON faz parte da entrega produtiva atual.
4. Aprovar a criação de um ambiente de homologação e uma rotina de testes antes de publicar mudanças.
5. Priorizar a estabilização e documentação do sistema antes de uma expansão funcional maior.

## 9. Conclusão

O painel já reúne uma base importante para análise de pavimentos. O caminho recomendado é estabilizar os pontos que afetam confiabilidade, padronizar a experiência entre telas e evoluir a estrutura interna de forma gradual. Dessa forma, cada melhoria pode ser validada pela área de negócio antes de seguir para produção, com menor risco e melhor previsibilidade.

---

### Observação metodológica

Este documento foi elaborado a partir da análise do repositório e de sua documentação disponível em 10/07/2026. Os itens marcados como validação ou confirmação não devem ser tratados como defeito funcional confirmado sem confronto com as regras de negócio e o ambiente produtivo.
