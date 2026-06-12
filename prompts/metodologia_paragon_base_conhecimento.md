# Metodologia Paragon — Avaliação e Diagnóstico de Pavimentos Asfálticos

> **Base de conhecimento técnica para agente de IA.**
> Fonte: Livro técnico "Metodologia Paragon" (autores: Paulo Cerejo, Christel Almeida Pereira, Humberto Santana, Armando Martins Pereira), Cap. 2 — "Avaliação e Diagnóstico de Pavimentos Asfálticos".
> Conteúdo: filosofia metodológica, equipamentos de levantamento, catálogo de defeitos com codificação, fórmulas de cálculo do ISG, pesos de ponderação, escala de sanidade, correlações com PSI/AASHTO e análise de deformação permanente.

---

## 1. INTRODUÇÃO E FILOSOFIA DA METODOLOGIA PARAGON

### 1.1. Crítica aos métodos tradicionais
A engenharia rodoviária dedicou grande esforço a desenvolver ferramentas cibernéticas para dimensionar reforços estruturais em pavimentos asfálticos (análises de sistemas estratificados elásticos submetidos a tensões e deformações). Entretanto, essas ferramentas falham em caracterizações excepcionais dos materiais constituintes do reforço estrutural pavimento-solo de fundação, principalmente porque:

- Os índices de caracterização habituais (como IRI e flechas nas trilhas de roda) **têm demanda reduzida e não são específicas** para o tratamento de defeitos diversos da pista.
- As proposições de tratamento de defeitos parcos dados são consistentemente primárias por misignar patologias e parâmetros de comportamento de natureza completamente distintas (muitas vezes por fronteiras cabalísticas).
- Os índices de caracterização, usualmente processados conjuntamente em **ambas as faixas de tráfego**, propõem-se a estabelecer uma classificação conceitual nos estados do pavimento, por meio de uma classificação para "**Segmentos homogêneos**" definidos a propósito de poder calcular um conceito estrutural representativo. Na realidade, as definições lavradas não correspondem à definição de valores modulares, na sequência de raciocínio, vale destacar que esta estratégia simplesmente viabiliza o dimensionamento mecanístico de reforços estruturais, pautado na definição dos esforços atuantes em camadas de reforço que externam espessuras crescentes (de 0,5 em 0,5 cm, até 20 cm ou mais — e no cotejamento contra os esforços resistentes máximos admissíveis).

### 1.2. Conceitos centrais da Metodologia Paragon
A Metodologia Paragon foi desenvolvida com o objetivo prático de definir um sistema de codificação numérica integrada e estabelecer uma linguagem comum e universal para a **caracterização das condições vigentes**, do tráfego, da constituição dos pavimentos e camadas, independentemente das particularidades dos materiais constituintes ou da região onde se localizam.

No âmbito do trabalho metodológico que caráter exortativo, define-se, por meio de um algoritmo de ordenação genética, **conjuntos específicos contemplados por distintas famílias de características físicas**, um *Código de Sanidade do pavimento* — estabelecidos cumulativamente em relação a cada estado de degradação do pavimento, qual define, com a devida acuidade, o seu verdadeiro diagnóstico.

Os critérios de avaliação e diagnóstico de pavimentos asfálticos que regem a sua **Metodologia Paragon** são apoiados em pareceres técnicos rico desenvolvidos, sustentados nos princípios básicos concebidos para a definição dos estados de sanidade correspondentes a cada família de característica física e aos processos pensados para uma sumarização adequada das opções em conjunto, estabelecida uma classificação para conjunto integral do pavimento (Concreto Asfáltico - CA ou Tratamento Superficial - TS).

A metodologia desenvolveu-se em procedimento analítico para o cálculo de reforços de pavimentos com uso da **Metodologia Paragon** ou *Multifunction Vehicle (Figura 2)*, dotado de um conjunto de instrumentos de auscultação de pavimentos que operam de forma integrada e simultânea, e o *Laser Crack Measurement System II – Pavement Scanner (Figura 3)*, dotado de equipamento autossuficiente dotado de **17 módulos de avaliação**.

Parte dos instrumentos coletados propiciam a identificação e quantificação das degradações superficiais, os quais são tão precisos para identificar as deformações permanentes, mas com a equipamento são adiante devidamente descritos.

### 1.3. Equipamentos integrantes do *Multifunction Vehicle* (Figura 2)
- High Speed Laser Camera
- LCMS-II Laser Crack Measurement System
- Orthogonal Pavement Scanner / Orthogonal Pavement Recorder
- DGPS
- IMU
- GNSS
- Câmaras integradas com sincronismo entre si
- Conjunto que possibilita simultaneamente: deflexões, IRI, panorama, perfil, levantamento da superfície e geo-referenciamento.

### 1.4. Frase-síntese da filosofia
> *"A esperança tem duas filhas lindas: a indignação e a coragem; a indignação para não aceitar as coisas como estão, e a coragem, para mudá-las."* — Santo Agostinho

---

## 2. CAPÍTULO 2 — AVALIAÇÃO E DIAGNÓSTICO DE PAVIMENTOS ASFÁLTICOS

### 2.1. Levantamento Histórico do Pavimento Existente

No âmbito da metodologia de avaliação de pavimentos asfálticos, a proposição primária consiste em **promover, antes de quaisquer providências, uma visita de inspeção técnica ao campo** com o objetivo de adquirir uma sensibilidade maior sobre as condições de serventia vigentes, a natureza das principais degradações existentes, a hierarquia preponderante do sistema envolvido, as características das drenagens vigentes e sobre a composição da frota solicitante.

A análise desse espectro envolverá, atrelada a uma visão pragmática, que possibilite o levantamento, faculta o despertar de uma mística que possibilita o sentido do sucesso de todo o empreendimento, particularmente no que toca à qualidade dos levantamentos e à fiadora das soluções de restauração a serem propostas.

No desenvolvimento de um *Projeto de Restauração* considera-se de importância superior à obtenção de **todas as informações disponíveis acerca do histórico do pavimento existente, dos elementos relativos à sua constituição e aos materiais empregados**, das intervenções de manutenção e reabilitação já realizadas, às respectivas datas de entrega e periodicidade etc.

Considera-se: para obter informações com maior nível de detalhe, é imprescindível promover entrevistas com os Engenheiros Residentes/Regionais das rodovias, subsidiados pelos procedimentos sem conjunto operacional, podendo-se destacar dentre eles: existentes e escalecedoras, organizando o pavimento original e largura da pista e dos acostamentos.

**Documentos e informações de interesse:**
- Constituição do pavimento e acostamentos.
- Ações de conservação, intervenções de manutenção e/ou restauração já executadas.
- Projetos originais de pavimentação e/ou restauração.
- Datas da entrega do pavimento ao tráfego.
- Características do tráfego usuário (cargas típicas, sazonalidade, desvios, polos geradores e rotas de adesão, faixa de tráfego solicitante, percentual de veículos comerciais carregados etc.).
- Características específicas ou singularidades dos solos de fundação regionais.
- Comportamentos específicos a eventuais sucessos ou insucessos verificados (a observar, por exemplo, materiais inadequados, materiais constituintes ou intervenções etc.).
- Dificuldades de aplicação de remédios ou eventuais restrições.
- Características regionais relevantes (hidrologia, geologia, clima etc.).

---

## 3. AVALIAÇÃO DAS CARACTERÍSTICAS FUNCIONAIS DOS PAVIMENTOS

### 3.1. Considerações Gerais (2.2.1)

O princípio basilar da Metodologia Paragon aproxima-se do que aqui se diagnóstico do pavimento esteja-se de fundamental para definição do paramento único, determinado com base no tratamento conjunto das manifestações de ruína que, sem se ter conta, são formuladas em conjunto, suas naturezas, magnitudes individualizadas, suas associações, distância entre si, tempos e percentuais de ocorrência.

Na busca de uma solução, a opção que se apresenta foi a de contemplar uma forma particularizada e independente, **distintas famílias de manifestações de ruína que, em conjunto, traduzem a serventia do pavimento — degradações superficiais e deformações permanentes — associadas ao nível de eficácia que vigora experimentada pelo pavimento bajo os carros do tráfego**.

Dessa modo, espera-se conjuntamente, fundamentalmente entre si os índices de detecção das distintas famílias de degradação, a consideração de que ambos devem **pelo menos em principio, ser alvo**, perfeitamente de intervenções comborrativas preliminares às obras de restauração funcional pré-estabelecida do pavimento existente.

Desfase, no âmbito da presente metodologia e a partir da consignação de diferentes manifestações de ruína, sem se ter conta, esta forma individualizada — suas naturezas, magnitudes e percentuais de ocorrência.

A pesquisa fundamenta-se, portanto, na busca de um procedimento prático e codificação numérica integrada, como o estabelecimento de uma linguagem comum e universal, tradutora da caracterização dos pavimentos analisados, independentemente de suas idades, composições estruturais, tráfegos suportados e localizações geográficas.

Adicionalmente, com o caráter integrante de modo a permitir a detecção das diferentes famílias de degradação individualizadas das suas associações, da deformabilidade elástica, um único genérico capaz de **permitir a definição do estado de sanidade externado pelo pavimento, amparado em atributos qualificados para processar seu diagnóstico**.

Assim, foram consideridos os procedimentos por estaca — por preliminarmente considerados em conjunto todos os índices conceituais, **artifício que possibilitará a definição de estado de sanidade**, partindo de identificadores característicos, artifício esse que se qualifica para permitir a definição em conjunto da depuração, podendo destacar e considerar dentre eles os mais comprometidos e do estado de degradação, condição que impõe ao projetista um conjunto de valores específicos.

### 3.2. Avaliação das Características de Degradação Superficial (2.2.2)

Na busca de um procedimento novo, que se mostrasse competente bastante para definir os distintos graus de degradação e fornecer os subsídios necessários ao acompanhamento das medidas corretivas ideais, conceberam-se as proposições novas para subsidiar a base de sustentação, denominada *"Metodologia Paragon"*, pelo Prof. Armando Martins Pereira, das proposições genéticas (do tipo *"Método Expedito de Avaliação Paragon — Um Fleximela e Semi-Rigidos"*) — se apresentava com qualificação excepcional.

Alicerçada pelos pressupostos do mestre, **promovam-se inicialmente a identificação e o agrupamento dos mais distintas manifestações de ruína de caráter funcional ocorrentes em um pavimento asfáltico, em famílias agrupadas de acordo com suas naturezas e ordenadas em ações de sua origem, manifestação e magnificância**. Aplicou-se procedimento de modo que se promovesse, dentro do universo de manifestações ou degradações, fossem definidos com os percentuais a serem de fato considerados, por meio de simples e estabeleceu-se as respectivas codificações.

### 3.3. Multifunction Vehicle

Parte dos equipamentos eletrônicos capazes de propiciar o levantamento contínuo de pavimentos asfálticos são empregados em conjunto, dotado de um sistema avançado de navegação composto de um encoder/odômetro de alta precisão para registros das distâncias percorridas por faixa de tráfego e por tipo de revestimento.

Esses equipamentos são especialmente desenvolvidos para a *Metodologia Paragon* ou *Multifunction Vehicle (Figura 2)*, dotado de um conjunto de instrumentos de auscultação de pavimentos que operam de forma integrada e simultânea, e o *Laser Crack Measurement System II – Pavement Scanner (Figura 3)*, dotado de equipamento autossuficiente, dotado de 17 módulos de avaliação.

#### 3.3.1. Road Video Survey

Equipamento de filmagem digital dotado de software desenvolvido pela Strata Engenharia que possibilita concomitantemente a delimitação gráfica das áreas comprometidas, em sistema multimídia, com absoluta precisão.

O Multifunction Survey é composto dos seguintes equipamentos:

- **Equipamento de filmagem digital dotado de software** que estabelece o sincronismo entre o posicionamento (georreferenciamento) dos veículos. Suas câmeras, de altíssima resolução *Full HD 1920x1080* pixels e estrategicamente posicionadas, captam uma sequência contínua de imagens à taxa mínima de 30 frames/s, propiciando a filmagem em altíssima definição, das paredes que componham o perfil panorâmico do veículo, juntamente com os subsistemas vinculados a cada foto coordenadas geodésica permitem a definição do trajeto planialtimétrico da estrada. As três câmaras estão posicionadas conforme a seguinte disposição:

- Duas câmaras, dispostas nas partes frontal e traseira do veículo, promovem a filmagem digital especial (panorâmica) do pavimento dos acostamentos, incluindo elementos de drenagem (laterais (dispositivos das estruturas e/ou vertical), drenagem superficial, estabilidade de taludes de corte, ocupação da faixa de domínio, localização de perímetros urbanos, pontes e viadutos etc.);

- A terceira câmara, disposta na parte central do veículo, é focada a 10° do plano da rodovia, propiciando a captura de fotos sequenciais, de altíssima resolução, a cada faixa independentemente, com largura inferior a 1,0 mm; eventuais dúvidas de interpretação podem ser facilmente dirimidas com a aplicação do "zoom" e por meio de avanços de retroprocessamento automático.

Com o emprego do "*Mouse*" — processa-se a demarcação gráfica de cada manifestação de ruína, com seus pontos poligonais devidamente georreferenciados em sistema multimídia, processo que se denomina *Levantamento Específico das Áreas Degradadas - LEAD*, o qual, mais adiante detalhado, propicia a identificação e definição de suas localizações geográficas, e a quantificação por tipo e área específicos.

#### 3.3.2. *Orthogonal Pavement Recorder*

Equipamento que processa o escaneamento digital do pavimento, com base no uso de câmara disposta ortogonalmente ao plano da superfície, firmada por uma luz LED de alta resolução. O registo digital do pixels — é processado em continua a velocidade de 100 km/h — cabendo ao software promover a velocidade de processamento.

### 3.4. *Levantamento Visual Contínuo*

Levantamentos da ordem dos 80km/h com coleta de imagens à taxa mínima de 30 frames/s, todos georreferenciados (Figura 5).

A projeção do filme em tela de 75″ — que retrata o pavimento praticamente em verdadeira grandeza — permite a detecção, identificação e localização de todas as degradações superficiais (pontuais e extensas) ocorrentes no pavimento, inclusive fissuras capilares e/ou incipientes com larguras inferiores a 1,0 mm; eventuais dúvidas de interpretação podem ser facilmente dirimidas com a aplicação do "zoom" e por meio de avanços de retroprocessos automáticos.

Com o emprego do "Mouse" — processa-se a demarcação gráfica de cada manifestação de ruína, com seus pontos poligonais devidamente georreferenciados em sistema multimídia, processo que se denomina *Levantamento Específico das Áreas Degradadas (LEAD)*, o qual, mais adiante detalhado, propicia a identificação e definição de suas localizações geográficas, e a quantificação por tipo e área específicos.

### 3.5. *Laser Crack Measurement System II — Pavement Scanner*

O **Laser Crack Measurement System II (LCMS-II)** é o equipamento que consiste em um sistema de escaneamento do perfil transversal de alta resolução, que utiliza dois perfiladores a laser para gerar perfis 3D completos com 4.160 metros de largura. Na realidade, trata-se de um *"Pavement Scanner"* que processa a varredura contínua da superfície do pavimento através da leitura de **28.000 perfis transversais à razão de 4,1m por segundo (correspondendo a uma velocidade de operação de até 100 km/h) — resultando em uma coleta de 116 milhões de pontos a cada segundo (Figura 7);** os dados coletados a bordo do veículo de inspeção e as especificações técnicas dos LCMS-II estão indicados no **Quadro 3**.

No âmbito do procedimento de escaneamento, as resoluções às distâncias da leitura LCMS são altíssimas, particularmente para as larguras de altíssimas particularidades das suturas, que permitem a sutileza das informações que se converte em uma imagem virtual, tão consistente que permite a detecção de todas as fissuras existentes. O levantamento dos LCMS-II são processados a altas velocidades — até 116 km/h — cabendo do software promover a velocidade de processamento.

#### 3.5.1. **Quadro 3** — Especificações LCMS-I e LCMS-II (Pavement Scanner)

| Especificações | LCMS-1 | LCMS-2 |
|---|---|---|
| Taxa de Aquisição de Dados | 116.000.000 pontos/s | — |
| Escaneamento Longitudinal (1mm) | 28.000 perfis/s | — |
| Escaneamento Transversal (1mm) | 4.160 pontos | — |
| Taxa de Coleta de Dados/km | 3 Gb/km | — |
| Acuidade Vertical (Precisão do Alcance) | 0,25mm/0,05mm | — |
| Resolução Vertical / Cálculo do IRI (Intervalo a cada 25mm) | 0,05mm | — |

### 3.6. *Levantamento Específico de Áreas Degradadas (LEAD)*

Estabelecimento específico de áreas degradadas, que distintas podem ocorrer várias vezes ao longo de uma mesma estaca ou até mesmo se repetirem no âmbito de uma mesma seção métrica Paragon (artifício de quantificação das fissuras), no âmbito da *Metodologia Paragon (Tabela TS3)*, localização e quantificação das fissuras no LCMS-II, o processado por meio de inteligência artificial — IA.

Para um procedimento de análise mais elaborada, desenvolve-se sendo um procedimento minucioso e detalho, qual consiste em concluir o universo de análises efetuada por ele em sua extensão correspondente, ela é cada estaca por meio da medida correspondente, ela é cada extensão na sua extensão correspondente, ela é cada estaca por meio da medida exata requerida. Assim sendo, procura-se promover a definição do número médio de defeitos por estaca, considerando-se trechos de 20m com 4 estacas, de modo a obter um real fidedignidade desta definição, na real do tráfego.

A população analisada (20 unidades). Como a frequência relativa é definida pela relação entre o número de vezes em que o defeito se torna ocorrente em relação ao número de eventos que compõe o universo, tem-se:

**f_e = (número de semi-intervalos de 1,0m afetados) / 20  × 100**

> Conferindo um fator de ponderação capaz de exprimir, em sua gravidade individual e relativa, concomitantemente, a importância de seus reforços e a definição da operação corretiva a empreender.

---

## 4. CATÁLOGO DE DEFEITOS — CODIFICAÇÃO PARAGON

Os defeitos são organizados em famílias e sub-famílias com codificação alfanumérica padronizada. A tabela abaixo (Quadro 1) refere-se a revestimentos do **tipo Concreto Asfáltico**.

### 4.1. **Quadro 1** — Identificação e Codificação das Degradações Superficiais (Concreto Asfáltico)

| TRINCAMENTO — Natureza Aparente | Falhas na Superfície do Revestimento | Codificação |
|---|---|---|
| **AUSÊNCIA APARENTE DE FALHAS NO REVESTIMENTO** | — | **OK** |
| **FISSURAS INCIPIENTES** | — | **FI** |
| **TRINCAS ISOLADAS — Trincas atribuídas à fadiga de misturas asfálticas ou à reflexão de trincas da camada de base** | Longitudinal Curta | **TLC** |
| | Longitudinal Longa | **TLL** |
| | Transversal Curta | **TTC** |
| | Transversal Longa | **TTL** |
| **TRINCAS INTERLIGADAS** | "Jacaré" — sem erosão acentuada com erosão acentuada nos bordos | **J / JE** |
| | Blocos sem erosão nos bordos | **TB** |
| | Blocos com erosão nos bordos | **TBE** |
| | Trincas atribuídas ao padrão original, atribuídas à acomodação volumétrica ou dissipação de energia da camada de base (retração térmica) | **TPE** |
| | Trincas higroscópicas devidas a variações de umidade no corpo do aterro e/ou camadas granulares | **TH** |
| | Trincas associadas ao cisalhamento ou corte da camada de base | **TCB** |
| | Trincas associadas a deformações permanentes excessivas | **TDP** |
| | Trincas associadas ao bombeamento de finos | **TPM** |
| | Trincas atribuídas à concolidação ou diferencial dos maciços terrosos | **TRA** |
| **PANELAS (Desagregação do Revestimento com ou sem Comprometimento da Base)** | — | **P** |
| **REMENDOS** | Peladas (superficiais ou profundos) | **PEL** |
| | Padrões (superficiais ou profundos) | **RP** |
| | Emergenciais ("Tapa Panelas") | **RE** |
| **DESGASTE OU DESAGREGAÇÃO SUPERFICIAL DO REVESTIMENTO ASFÁLTICO** | Segregação de Massa Asfáltica | **DSG / SEG** |
| | Migrações por *ascensum* | — |
| **DEFEITOS EXSUDATIVOS** | Afloramento Incipiente de Ligante | **EXI** |
| | Afloramento do Ligante (Exsudação) | **EX** |
| **TEXTURA MUITO LISA OU ESPELHAMENTO** | Profundidade de Textura Inadequada ou Polimento das Asperezas | **TEX** |

### 4.2. **Quadro 2** — Identificação e Codificação das Degradações Superficiais (Tratamento Superficial)

| TRINCAMENTO — Natureza Aparente | Falhas na Superfície do Revestimento | Codificação |
|---|---|---|
| **AUSÊNCIA APARENTE DE FALHAS NO REVESTIMENTO** | — | **OK** |
| **TRINCAS ATRIBUÍDAS AO COMPORTAMENTO DEFICIENTE DA CAMADA DE BASE E/OU MAÇOS TERROSOS** | (Trincas interligadas a variações de tensões de retração) | — |
| **TRINCAS ATRIBUÍDAS AO ESCOREGAMENTO DOS COMPORTAMENTOS DEFICIENTES** | (Trincas interligadas) | **TLB / TPM** |
| **TRINCAS HIGROSCÓPICAS DEVIDAS A VARIAÇÕES DE UMIDADE NO CORPO DO ATERRO E/OU CAMADAS GRANULARES** | Trincas ocorrentes referentes às bordas associadas ao cisalhamento da camada de base | **FC.3** |
| | Trincas ocorrentes devido às deformações plásticas excessivas das camadas de base com o do revestimento (estado de superfície) | **TDP / TPM** |
| | Trincas referentes ao cisalhamento da consolidação ou diferencial de maciços terrosos | **TRA** |
| **PANELAS (Desagregação do Revestimento com ou sem Comprometimento da Base)** | — | **P** |
| **REMENDOS** | Revestimentos perdidos ou generalizados | **RD** |
| | Estrias leves | **ELG** |
| | Estrias acentuadas | **EAG** |
| **DESAGREGAÇÕES** | Mais trinhas de roda generalizadas | — |
| | Mais trinhas de roda generalizadas dos agregados | **DSG** |
| **REMENDOS** | Padrão (superficial ou profundo) | **RP / RE** |
| | Emergencial ("Tapa Buraco") | **RE** |
| **DEFEITOS EXSUDATIVOS** | Afloramento de Ligante Incipiente | **EXI / EX** |
| | Afloramento de Ligante (Exsudação) | **EX** |
| **ZONAS DE ACUMULAÇÃO DE ÁGUA** | — | **ZAA** |

---

## 5. CÁLCULO DO ISG — ÍNDICE DE SEVERIDADE GLOBAL

### 5.1. Lógica conceitual
Não trata-se da soma dos defeitos da estaca a serem a serem submetidos a soma dos defeitos com a estaca corretiva, mas sim do tratamento de **ponderações sequenciais distintas associadas a tipologias diferentes (FC.1, FC.2, FC.3) — que devem ser consideradas pela expressão**:

```
ISG_OS = Σ f_e × ISG_OS  (somatório por estaca)
```

> Onde:
> - **f_e** = frequência relativa de ocorrência por semi-intervalos de 1,0 m afetados (universo de 20 unidades por estaca de 20m).
> - **ISG_OS** = índice de severidade global por estaca.
> - O cálculo é feito **por estaca** (e não para o trecho como um todo), permitindo identificar pontualmente as áreas mais críticas.

### 5.2. Regra de não-duplicação (sobre o mesmo grupo)
Quando, em uma mesma estaca, ocorrerem **simultaneamente degradações de um mesmo grupo (ex.: fissuras enquadradas nos tipos FC.1, FC.2, FC.3), na contabilização do ISG_OS deve-se ressaltar que, quando constatadas ocorrências simultâneas de degradações enquadradas no mesmo grupo (exemplo: tipo FC.1, FC.2, FC.3), no cálculo do ISG_OS, só se deve considerar a mais grave (FC-3)** — devem ser desconsideradas anotadas, mas para efeitos de ponderação no cálculo do ISG_OS, **só se deve considerar a mais grave (FC-3)**.

A consideração desse condicionamento em face da concepção das escalas qualquer que seja o estado de degradação ou de severidade adotada, constata-se que **uma vez que correspondente índice de severidade global - ISG_OS, é sempre representada por componente de uma mesma magnitude, e qualquer ela um valor único, jamais um composto de várias parcelas — assim sendo, são situações distintas, induzem a obtenção de valores "médios" não aderentes à condição que impõe ao projetista um conjunto de valores específicos**.

Quanto ao quesito das características funcionais, algumas técnicas têm sido desenvolvidas, podendo-se citar realmente como metodologias aplicadas e admissíveis nos métodos pelo Departamento Nacional de Infraestrutura de Transportes (DNIT) – o critério de procedimento aplicado nos EUA fundamentado no *Present Serviceability Index – (PSI)*.

### 5.3. Fórmulas de cálculo (Tratamento Superficial - TS)

Tomando os valores do ISG_OS, comprendidos entre 0 e 30, regidos por uma relação logarítmica linear, e para valores entre 30 e 480, regidos por uma relação logarítmica de base 2, os resultados obtidos, traduzindo correlações simplesmente perfeitas para ambos os casos (**r² = 1**), assim expressam-se:

- **Para ISG_OS ≤ 30:**

```
Z_2x = ISG_OS / 30
```

- **Para ISG_OS > 30:**

```
Z_2x = log_2 (2 × ISG_OS / 30)
```

### 5.4. Fórmulas de cálculo (Concreto Asfáltico - CA)

Considerando os valores do ISG_OS, comprendidos entre 0 e 20, regidos por uma relação logarítmica linear, e para valores entre 20 e 320, regidos por uma relação logarítmica de base 2, os resultados obtidos traduzindo correlações simplesmente perfeitas para ambos os casos (**r² = 1**), assim expressam-se:

- **Para ISG_OS ≤ 20:**

```
Z_2x = ISG_OS / 20
```

- **Para ISG_OS > 20:**

```
Z_2x = log_2 (2 × ISG_OS / 20)
```

### 5.5. Fórmulas do ICDS (Índice da Condição de Degradação Superficial)

Aplicando-se de forma analítica, o parâmetro **ICDS - Índice da Condição de Degradação Superficial**, que traduz a degradação superficial em escala de igual forma, correlações perfeitas, definidas pelas seguintes expressões (Quadro 11):

#### Concreto Asfáltico (CA):
- **Para 0 ≤ ISG_OS ≤ 20:**
```
ICDS = 5 - (ISG_OS / 20)
```

- **Para ISG_OS > 20:**
```
ICDS = 5 - log_2 (2 × ISG_OS / 20)
```

Considerando, porém, a maior familiaridade dos engenheiros rodoviários como os logaritmos expressos na base 10, promoveu-se a devida conversão, obtendo-se:

- **Para 0 ≤ ISG_OS ≤ 20:**
```
ICDS = 5 - 0,05 × ISG_OS
```

- **Para ISG_OS > 20:**
```
ICDS = 8,2228 - 3,3219 × log ISG_OS
```

#### Tratamento Superficial (TS):
- **Para 0 ≤ ISG_OS ≤ 30:**
```
Z_2x = ISG_OS / 30
```

- **Para ISG_OS > 30:**
```
Z_2x = log_2 (2 × ISG_OS / 30)
```

Convertendo, obtém-se:

- **Para 0 ≤ ISG_OS ≤ 30:**
```
ICDS = 5 - 0,0333 × ISG_OS
```

- **Para ISG_OS > 30:**
```
ICDS = 6,9074 - 3,3219 × log ISG_OS
```

---

## 6. PESOS DE RESPONSABILIDADE — FATORES DE PONDERAÇÃO

### 6.1. **Quadro 4** — Pesos de Responsabilidade das Degradações Superficiais (Revestimento tipo Concreto Asfáltico)

| Natureza da Ocorrência Superficial | Codificação | Fator de Ponderação |
|---|---|---|
| Ausência aparente de falhas | **OK** | — |
| Fissuras incipientes | **FI** | — |
| **TRINCAS ISOLADAS** | | |
| Longitudinal curta | TLC | (*) |
| Longitudinal longa | TLL | (*) |
| Transversal curta | TTC | (*) |
| Transversal longa | TTL | (*) |
| **TRINCAS INTERLIGADAS** | | |
| "Jacaré" sem erosão / acentuada com bordas | **JE / FC.1** | **0,4** |
| Blocos com erosão nos bordos | **FC.2** | **0,8** |
| Blocos sem erosão nos bordos | **FC.2** | **0,9** |
| Trincas atribuídas ao escoregamento ou variações de umidade nos camadas | **FC.3** | **0,7** |
| Trincas associadas ao cisalhamento da camada de base | **FC.3** | **0,7** |
| Trincas associadas a deformações plásticas excessivas | **FC.3** | **1,0** |
| Trincas associadas ao bombeamento de finos | **FC.3** | **0,2** |
| **PANELAS** (com ou sem comprometimento da base) | **P** | **0,5** |
| **REMENDOS** — Peladas (superficiais ou profundas) | **PEL** | **0,4** |
| Padrões ("tapa panelas") | **RP** | **0,1** |
| Emergenciais | **RE** | **0,5** |
| Desagregação de massa asfáltica | **DSG** | **0,3** |
| Segregação por *ascensum* | **SEG** | **0,5** |
| **DEFEITOS EXSUDATIVOS** — Afloramento incipiente | **EXI** | **0,1** |
| Afloramento do ligante (Exsudação) | **EX** | **0,1** |
| **TEXTURA MUITO LISA OU ESPELHAMENTO** | **TEX** | (****)|

### 6.2. **Quadro 5** — Pesos de Responsabilidade das Degradações Superficiais (Revestimento tipo Tratamento Superficial)

| Natureza Aparente de Falhas na Superfície do Revestimento | Codificação | Fator de Ponderação |
|---|---|---|
| Ausência de falhas | OK | — |
| **TRINCAS ATRIBUÍDAS À COMPORTAMENTO DEFICIENTE DAS CAMADAS DE BASE OU DOS MAÇOS TERROSOS** | | |
| **TRINCAS INTERLIGADAS** — Bordas associadas ao cisalhamento da camada de base | TCB/FC.3 | (***) |
| Trincas associadas a deformações plásticas excessivas das camadas de base do revestimento | TDP/FC.3 | (***) |
| Trincas associadas a deformações em geral, formação concolidação ou diferencial dos maços terrosos | TPM/FC.3 | (***) |
| Trincas semi-circulares atribuídas à concolidação ou rompimento do maço terroso | TRA/FC.3 | (***) |
| **TRINCAS ATRIBUÍDAS AOS ESCOREGAMENTOS DOS COMPONENTES OU À VARIAÇÃO DE UMIDADE NO CORPO DO ATERRO E/OU CAMADAS GRANULARES** | | |
| Longitudinais ou transversais nos acostamentos e/ou bordas | TPE/FC.2 | **0,5** |
| Trincas higroscópicas atribuídas a variações de umidade nos corpos de aterros e/ou camadas granulares | TH6/FC.2 | **0,7** |
| **PANELAS** | **P** | **1,0** |
| **PANELAS INDIVIDUALIZADAS** | **RID** | **0,6** |
| **ESTRIAS LEVES** | **ELG** | **0,4** |
| **ESTRIAS ACENTUADAS** | **EAG** | **0,6** |
| **DESAGREGAÇÕES** (ou desgaste) — Mais trinhas de roda generalizadas | **DSG** | **0,7** |
| Desagregação acentuada dos agregados (generalizada) | **DSG** | **0,5** |
| **REMENDOS** — Padrão (superficial ou profundo) | **RP** | **0,5** |
| Emergencial ("Tapa Buraco") | **RE** | **0,3** |
| **MIGRAÇÕES POR ASCENSUM** | | |
| Afloramento do ligante incipiente (exsudação incipiente) | **EXI** | **0,6** |
| Afloramento do ligante (Exsudação) | **EX** | **0,5** |
| **ZONAS DE ACUMULAÇÃO DE ÁGUA** | **ZAA** | **0,1** |

> **Observações dos Quadros 4 e 5:**
> (*) Trincas isoladas longitudinais ou transversais — em pequenas extensões — usualmente são consideradas como manifestações de origem em juntas frias, e não consequências de comportamento estrutural disfuncional do conjunto pavimento-solo de fundação. São de pequena gravidade global e o seu tratamento é simples: lacre selado das fissuras com mástique modificado.
> (**) Os pesos dos defeitos exsudativos têm peso muito baixo (0,1) — em razão de serem consideradas de baixa intensidade.
> (***) Os pesos das trincas atribuídas ao escoregamento das camadas estão definidos como variáveis em decorrência da magnitude da extensão afetada — devendo ser definidos caso a caso pelo Engenheiro Responsável.
> (****) Texturas muito lisas ou polidas — em geral resultantes da exposição prolongada do pavimento ao tráfego — exigem reconstituição da textura por meios mecânicos como o uso de fresadoras eletromotrizes. O peso final é determinado pelo Engenheiro Responsável em função da gravidade do polimento.

---

## 7. CONCEITUAÇÃO DOS ESTADOS DE SANIDADE

### 7.1. Escala conceitual de cinco níveis (Figura 12)
A Metodologia Paragon adota uma escala de cinco níveis para a qualificação do estado de sanidade:

| Estado de Sanidade | Cor |
|---|---|
| **Excelente** | Verde escuro |
| **Bom** | Verde claro |
| **Regular** | Amarelo |
| **Mau** | Laranja |
| **Péssimo** | Vermelho |

### 7.2. **Quadro 6** — Distribuição dos Níveis de Sanidade Regidos por Lei Logarítmica de Base 2

| Estado | Intervalo CDS (ICDS) | Intervalo ISG (TSD) |
|---|---|---|
| **Excelente** | 0 – 20 (escala CDS) | 0 – 30 |
| **Bom** | 20 – 40 | 30 – 60 |
| **Regular** | 40 – 80 | 60 – 120 |
| **Mau** | 80 – 160 | 120 – 240 |
| **Péssimo** | 160 – 320 | 240 – 480 |

> Acreditando ser esta disciplina matemática-procurou-se de seguidamente da forma totalmente independente, estudar quais e quantos níveis de sanidade poderiam ser concebidos, definindo-se que cinco seriam suficientes para uma boa caracterização, considerando bastantes que para definir os estados de sanidade dos pavimentos (**Figura 12**).

### 7.3. Conceito da escala AASHTO/PSI (referência comparativa)

A escala AASHTO (Ottawa-Illinois - 1960) evidenciou na sua referência ao primeiro de cinco intervalos de variação do ISG_OS — e os respectivos estados de sanidade. Os índices de aptidão presente (**PSI – *Present Serviceability Index***) até hoje preconizados pela atual *American Association of State Highway and Transportation Officials – AASHTO*.

#### **Quadro 10** — Conceitos de Serventia AASHTO (PSI – Present Serviceability Index)

| Qualitativos | Quantitativos |
|---|---|
| **Excelente** | 5 – 4 |
| **Bom** | 4 – 3 |
| **Regular** | 3 – 2 |
| **Mau** | 2 – 1 |
| **Péssimo** | 1 – 0 |

> Verifica-se, entretanto, que enquanto os valores de parâmetro Z policiam a gravidade dos estados de sanidade em ordem crescente, a AASHTO propõe a qualificação para sua conceituação, da sequência decrescente, traduzindo a sua proposição em uma escala decrescente para sanidade, condicionando para um conceito conceitualmente desenvolvido pela Metodologia Paragon — torna-a similar à escala AASHTO.

O processo de inversão, de fácil resolução, consiste em algébricamente uma estrategicamente estabelecido em termos qualitativos, podem manter a mesma qualificação. Mas, **5,0 - Z_2x**, qual se denominado em ICDS — "*Índice da Condição de Degradação Superficial*".

---

## 8. CORRELAÇÕES ISG_OS x ÁREA COMPROMETIDA

### 8.1. **Quadro 7** — Correlação entre os Valores de ISG_OS, os Estados de Degradação Superficial e as Percentagens de Área Comprometida (Concreto Asfáltico - CA)

| Estados de Degradação Superficial | Intervalos de Variação do ISG_OS | Área de Pavimento Afetada (%) |
|---|---|---|
| **Excelente** | 0 – 20 | 0 – 6,25 % |
| **Bom** | 20 – 40 | 6,25 – 12,5 % |
| **Regular** | 40 – 80 | 12,5 – 25 % |
| **Mau** | 80 – 160 | 25 – 50 % |
| **Péssimo** | 160 – 320 | 50 – 100 % |

### 8.2. **Quadro 8** — Correlação para Tratamento Superficial

| Estados de Degradação Superficial | ISG_OS (CA) | ISG_OS (TS) | % de Área Comprometida |
|---|---|---|---|
| **Excelente** | 0 – 30 | 0 – 30 | 0 – 6,25 % |
| **Bom** | 30 – 60 | 30 – 60 | 6,25 – 12,5 % |
| **Regular** | 60 – 120 | 60 – 120 | 12,5 – 25 % |
| **Mau** | 120 – 240 | 120 – 240 | 25 – 50 % |
| **Péssimo** | 240 – 480 | 240 – 480 | 50 – 100 % |

### 8.3. **Quadro 9** — Correlação Z_2x x ISG_OS

| Z_2x | ISG_OS (CA) | ISG_OS (TS) |
|---|---|---|
| 0 | 0 | 0 |
| 1 | 20 | 30 |
| 2 | 40 | 60 |
| 3 | 80 | 120 |
| 4 | 160 | 240 |
| 5 | 320 | 480 |

---

## 9. AVALIAÇÃO DAS CARACTERÍSTICAS DE DEFORMAÇÃO PERMANENTE (2.2.3)

### 9.1. Considerações iniciais
Pesquisas realizadas em literatura especializada não evidenciam a existência de um método para a avaliação conjunta de um pavimento integrada de pavimentos e seus respectivos comportamentos, ou de comportamento estrutural de pavimentos asfálticos e os efeitos de cada componente.

De forma geral, verifica-se uma tendência por simplesmente ignorar — em uma das misturas asfálticas tipos de defeitos permanentes acumulados como comparativos traduções com misigenagens excessivas para deformações permanentes — exemplo, **a miscigenação das características permanentes e desigualadades planas — vinculadas à uniformidade longitudinal**.

### 9.2. IRI — *International Roughness Index*

Atribuindo aos revestimentos tipo TS valores do ISG_OS, compreendidos entre 0 e 30, regidos por uma relação linear, e para valores entre 30 e 480, regidos por uma relação logarítmica de base 2. Os resultados obtidos, traduzindo correlações simplesmente perfeitas para ambos os casos (**r² = 1**), assim se expressam:

- Para 0 ≤ ISG_OS ≤ 30:
```
Z_2x = ISG_OS / 30
```
- Para ISG_OS > 30:
```
Z_2x = log_2 (2 × ISG_OS / 30)
```

Por maior familiaridade dos engenheiros rodoviários com os logaritmos expressos na base 10, promove-se a devida conversão, obtendo-se:

- Para 0 ≤ ISG_OS ≤ 30:
```
ICDS = 5 - 0,0333 × ISG_OS
```
- Para ISG_OS > 30:
```
ICDS = 6,9074 - 3,3219 × log ISG_OS
```

### 9.3. Slope Variance (SV) e Iregularidade Longitudinal

| Sigla | Significado | Comentário |
|---|---|---|
| **RD** | **Rut Depth** — profundidade média das flechas nas trilhas de roda | Em mm; média de 4 medidas (1120x4) dispostas sobre cada trilha de roda |
| **SV** | **Slope Variance** — variância da inclinação x 10 | Média de ambas as trilhas de roda |
| **C** | **Cracking** — Fissuração expressa por área | Em pés² (área de pavimento com fissuração); padrões ou outras com fissuras (afetam o PSI em áreas de 1000 pés² apenas, 0,3 da mesma forma, uma diferença nas trilhas de roda — Rut Depth) — profundidade afetada (RD) inexistente para 0,5 / 1,27mm afetada o PSI apenas em 0,4 |
| **P** | **Patching** — Áreas remendadas em áreas de 1000 pés² | — |

Nos EUA, o cálculo do *Present Serviceability Index (PSI)* contempla concomitantemente a flecha (Rut Depth - RD), as trincas (Cracking) e os remendos (Patching), as variações das irregularidades longitudinais (IRI) e transversais (FwwL) de forma independente e desvinculada.

Em síntese, as características de deformação permanente têm sido apreciadas, normalmente, por meio de medições das irregularidades longitudinais e transversais, feitas em ambas as trilhas de roda.

Na avaliação da irregularidade longitudinal busca-se aquilar o nível de deformações permanentes existentes por meio do parâmetro *International Roughness Index (IRI)*, o qual é considerado qualificado para "traduzir" de forma plena, toda a sorte de irregularidades existentes, com aceitação do grau de comprometimento — desligadamente associadas à conjugação, corrugação, emporadamento, estufamentos, desintegração, desnívelamento etc.

A avaliação da irregularidade transversal procura-se definir a magnitude das deformações permanentes por meio da medição pura e simples das flechas nas trilhas de roda (FwwL), das considerações com auxílio de uma régua de 1,20 m. **Esta vertente clássica, no Brasil, vinculada ao sabido Professor Armando Martins Pereira, tem o objetivo de apreciar, mesmo que de forma indireta, a irregularidade longitudinal estabelecida pelo pavimento.**

### 9.4. Os três processos de deformação permanente
Os três primeiros processos, que se caracterizam por deformações permanentes excessivas com reduções modulares, derivam fundamentalmente do número de repetições, da magnitude das cargas impostas, ao expoente da resistência das misturas, da magnitude das cargas, das tensões, das condições granulométricas, das características dos materiais e da efetividade dos seus processos de compactação.

Os processos permanentes podem-se manifestar de forma classificada em três processos distintos:

#### a) Por consolidação diferencial (densificação)
Excessivas deformações resultantes da redução do volume de ar nas misturas asfálticas (densificação).

#### b) Por perda de materiais
Deformações associadas a perdas de materiais por *plasticidades excessivas dos solos de fundação* (quase sempre vinculadas à umidade) ou *desestabilização granulométrica* (excesso ou deficiências de drenagem etc.).

#### c) Por cisalhamento ou deformações plásticas
Deformações permanentes, sem variações no volume, associadas a estabilidades reológicas inadequadas (tempo de aplicação das cargas e temperatura de operação) ou plasticidades excessivas dos materiais constituintes (misturas asfálticas, granulometria do solo de fundação, base e sub-base ou solo de fundação).

> **Verifica-se, portanto, que os diferentes comportamentos externados por um pavimento sob a ação das cargas no que tange às distintas formas de manifestação dos defeitos permanentes evidenciam a impossibilidade de processar medições das flechas nas trilhas de roda de forma sistemática e indiscriminada.**
>
> **O primeiro processo de ocorrência admite, em tese, sua correção mediante a reposição de camadas estruturais; os três últimos, em face de suas gravidades, determinam a abertura de quatro processos, abrangendo deformações permanentes nas trilhas de roda em face das deficiências de drenagem etc.**

---

## 10. CONSIDERAÇÕES FINAIS E APRESENTAÇÃO DOS RESULTADOS

### 10.1. Resultados (forma de apresentação)

Os resultados podem ser tratados em relação à faixa de tráfego como um todo ou somente nas trilhas de roda, no entanto, nos procedimentos adotados pela metodologia, tem-se constituindo uma prática usual sob percentuais previstos para cada faixa de tráfego, expressando os resultados por estaca, por meio do *Levantamento Específico das Áreas Degradadas (LEAD)*, com a aplicação do "*zoom*" e por meio de avanços de retroprocessos automáticos.

Após reflexões filosóficas e algumas análises matemáticas, optou-se por intervalos globais de ambos os revestimentos, caso considerando ambos os revestimentos em termos de área afetada, abrangendo, de maneira magistral as informações apuradas dos principais parâmetros, a distribuição de níveis de sanidade regidos por uma lei logarítmica de base 2, ou seja, por uma progressão geométrica de razão igual a 2, traduzindo no **Quadro 6**.

### 10.2. Indicação de procedimentos
- A consideração dos defeitos correntes encontrados, por meio dos processos de varredura ao longo do trecho, decidindo os levantamentos efetuados por meio dos sistemas dotados de inteligência artificial.
- A definição dos tipos de defeitos individualizados, tratados respectivamente entre as faixas de tráfego, codificados de forma simplificada, segundo uma linguagem comum normalizada e adotada pelo Departamento Nacional de Infraestrutura de Transportes (DNIT), promovendo um sistema unificado de classificação.
- A consideração individualizada dos diferentes tipos de revestimento asfáltico existentes (Concreto Asfáltico ou Tratamento Superficial - TS).

> **Conclusão filosófica:**
> "*Definidos, portanto, os intervalos máximos de variação do ISG_OS — para ambos os revestimentos-tipo — procurou-se per quisar a existência de alguma formulação matemática capaz de disciplinar a variação dos valores com sua sensibilidade e a rigorosidade definidos para o ISG_OS, até hoje não evidenciada na literatura especializada.*"

---

## 11. GLOSSÁRIO DE TERMOS E SIGLAS

| Sigla / Termo | Definição |
|---|---|
| **CA** | Concreto Asfáltico (revestimento). |
| **TS** | Tratamento Superficial (revestimento). |
| **DNIT** | Departamento Nacional de Infraestrutura de Transportes (Brasil). |
| **AASHTO** | *American Association of State Highway and Transportation Officials* (EUA). |
| **PSI** | *Present Serviceability Index* — índice de serventia atual. |
| **IRI** | *International Roughness Index* — índice de irregularidade longitudinal. |
| **SV** | *Slope Variance* — variância da inclinação. |
| **RD** | *Rut Depth* — profundidade da flecha nas trilhas de roda. |
| **ISG_OS** | Índice de Severidade Global por estaca. |
| **ICDS** | Índice da Condição de Degradação Superficial. |
| **LCMS-II** | *Laser Crack Measurement System II* — sistema de escaneamento a laser de alta resolução. |
| **LEAD** | Levantamento Específico de Áreas Degradadas. |
| **GNSS** | *Global Navigation Satellite System*. |
| **GPS** | *Global Positioning System*. |
| **IMU** | *Inertial Measurement Unit*. |
| **DGPS** | *Differential GPS*. |
| **VGAi** | Software *Visual Basic for Application* — empregado em formulações executivas e quantificações específicas. |
| **f_e** | Frequência relativa de ocorrência de um defeito por semi-intervalos de 1,0 m afetados (universo de 20 unidades por estaca). |
| **Z_2x** | Variável logarítmica em base 2, usada para transformar o ISG_OS em uma escala compatível com o ICDS. |
| **Concreto Asfáltico Usinado a Quente (CAUQ)** | Tipo de revestimento de alta qualidade. |

---

## 12. CODIFICAÇÕES DE DEFEITOS (RESUMO RÁPIDO PARA CONSULTA)

### Famílias de Fissuras / Trincas
| Código | Descrição |
|---|---|
| **OK** | Ausência aparente de falhas no revestimento |
| **FI** | Fissuras incipientes |
| **TLC** | Trincas Longitudinais Curtas |
| **TLL** | Trincas Longitudinais Longas |
| **TTC** | Trincas Transversais Curtas |
| **TTL** | Trincas Transversais Longas |
| **J / JE** | Trinca "Jacaré" (sem ou com erosão acentuada nos bordos) |
| **TB / TBE** | Trincas em Blocos (sem ou com erosão nos bordos) |
| **TPE** | Trincas de padrão original (retração térmica/dissipação de energia) |
| **TH** | Trincas higroscópicas (variações de umidade) |
| **TCB** | Trincas associadas ao cisalhamento da camada de base |
| **TDP** | Trincas associadas a deformações permanentes |
| **TPM** | Trincas associadas ao bombeamento de finos |
| **TRA** | Trincas atribuídas à consolidação diferencial dos maciços terrosos |

### Famílias de Defeitos Superficiais
| Código | Descrição |
|---|---|
| **P** | Panela |
| **PEL** | Pelada |
| **RP** | Remendo Padrão (superficial ou profundo) |
| **RE** | Remendo Emergencial ("Tapa Panelas" / "Tapa Buraco") |
| **DSG** | Desgaste / Desagregação superficial |
| **SEG** | Segregação de massa asfáltica |
| **EXI** | Exsudação incipiente / Afloramento incipiente de ligante |
| **EX** | Exsudação / Afloramento do ligante |
| **TEX** | Textura muito lisa ou espelhamento (polimento das asperezas) |
| **RD** | Mais trinhas de roda generalizadas (TS) |
| **ELG** | Estrias leves |
| **EAG** | Estrias acentuadas |
| **ZAA** | Zonas de acumulação de água |

### Famílias de fissuras (agrupamentos por grau de severidade)
| Grupo | Tipos de Trinca |
|---|---|
| **FC.1** | Trincas isoladas (TLC, TLL, TTC, TTL), "Jacaré" sem erosão (J) — baixa severidade |
| **FC.2** | Trincas em Blocos (TB, TBE), Trincas associadas ao padrão (TPE), Trincas higroscópicas (TH) — média severidade |
| **FC.3** | Trincas com erosão nos bordos, cisalhamento da camada de base (TCB), deformações permanentes (TDP, TPM), consolidação diferencial (TRA) — alta severidade |

### Regra de aplicação dos grupos FC
> **Sempre que houver simultaneamente FC.1 + FC.2 + FC.3 na mesma estaca, deve-se considerar apenas a mais grave (FC.3) para fins de cálculo do ISG_OS — os demais ficam anotados em relatório, mas não somam no índice.**

---

## 13. FLUXO METODOLÓGICO DE APLICAÇÃO

1. **Levantamento histórico** — coletar projetos originais, registros de manutenção, datas de entrega ao tráfego, características do tráfego usuário, características regionais (clima, hidrologia, geologia), entrevistas com Engenheiros Residentes.
2. **Visita de inspeção técnica** — sensibilidade ao trecho, drenagens, composição da frota.
3. **Levantamento em campo com Multifunction Vehicle (Strata)** — Road Video Survey + LCMS-II Pavement Scanner + Orthogonal Pavement Recorder + DGPS/IMU/GNSS, operando a até ~80–116 km/h.
4. **Processamento dos dados** — software com módulos de Processamento (Cracking, Sealed Crack, Bleeding, Patching, Raveling, Shoving, Pumping, Late Marking, Water Entrapment, Potholes) + Inteligência Artificial.
5. **Levantamento Específico das Áreas Degradadas (LEAD)** — demarcação gráfica via "mouse", com pontos poligonais georreferenciados em sistema multimídia.
6. **Codificação dos defeitos** — aplicar Quadro 1 (CA) ou Quadro 2 (TS) por estaca, intervalo de 20 m, semi-intervalos de 1 m (universo n=20).
7. **Cálculo de f_e** — frequência relativa por defeito.
8. **Aplicação dos pesos (Quadro 4 ou 5)** — usando regra de "apenas a mais grave por grupo FC".
9. **Cálculo do ISG_OS por estaca** = Σ f_e × peso.
10. **Cálculo do Z_2x e ICDS** — converter para a escala de sanidade (Quadro 7 ou 8).
11. **Classificação do estado de sanidade** — Excelente / Bom / Regular / Mau / Péssimo (Quadro 6 e Figura 12).
12. **Avaliação da deformação permanente (2.2.3)** — IRI + Slope Variance + medições de Rut Depth (RD) com régua de 1,20 m.
13. **Definição da intervenção corretiva** — selecionar tratamento individualizado por área homogênea, em razão direta do nível de degradação superficial.

---

## 14. PERGUNTAS FREQUENTES PARA O AGENTE DE IA

**P: Quais os 5 estados de sanidade do pavimento na Metodologia Paragon?**
R: Excelente (verde escuro), Bom (verde claro), Regular (amarelo), Mau (laranja) e Péssimo (vermelho).

**P: O que significa a sigla ISG_OS?**
R: Índice de Severidade Global por estaca. É a somatória dos produtos das frequências relativas de ocorrência (f_e) pelos pesos de ponderação de cada defeito apurado no trecho de 20 m da estaca.

**P: Como se calcula a frequência relativa (f_e) de um defeito?**
R: f_e = (número de semi-intervalos de 1,0 m afetados / 20) × 100. O universo de análise é de 20 unidades por estaca de 20 m.

**P: O que fazer quando ocorrem trincas FC.1, FC.2 e FC.3 na mesma estaca?**
R: Apenas a mais grave (FC.3) deve ser considerada no cálculo do ISG_OS. Os demais devem ser anotados em relatório para registro histórico, mas não somam no índice.

**P: Qual a diferença entre Concreto Asfáltico (CA) e Tratamento Superficial (TS) no cálculo?**
R: Mudam os intervalos de ISG_OS (CA usa base 20; TS usa base 30), os pesos dos defeitos (Quadro 4 para CA; Quadro 5 para TS) e a tabela de correlação com a área comprometida (Quadro 7 para CA; Quadro 8 para TS). A escala de sanidade qualitativa é a mesma.

**P: Qual a faixa de ISG_OS para um pavimento "Bom" em Concreto Asfáltico?**
R: ISG_OS entre 20 e 40, correspondente a 6,25 % – 12,5 % de área comprometida.

**P: O que é o LCMS-II?**
R: Laser Crack Measurement System II. Sistema com dois perfiladores a laser que processa varredura contínua da superfície do pavimento, gerando 28.000 perfis/s, com 4.160 pontos transversais e 116 milhões de pontos/s coletados. Resolução vertical de 0,05 mm.

**P: Como a metodologia se relaciona com o PSI da AASHTO?**
R: Pela conversão ICDS = 5 - Z_2x. O parâmetro Z_2x ordena a gravidade dos estados em ordem crescente (0 = excelente, 5 = péssimo), enquanto AASHTO/PSI usa escala decrescente (5 = excelente, 0 = péssimo). A inversão ICDS = 5 - Z_2x torna a Metodologia Paragon comparável ao PSI.

**P: Quais são os três processos de deformação permanente?**
R: (1) Por consolidação diferencial (densificação); (2) Por perda de materiais (plasticidades excessivas dos solos, desestabilização granulométrica, deficiências de drenagem); (3) Por cisalhamento ou deformações plásticas (estabilidades reológicas inadequadas, plasticidades excessivas).

**P: O que é o LEAD?**
R: Levantamento Específico de Áreas Degradadas — processo de demarcação gráfica de cada manifestação de ruína, com pontos poligonais georreferenciados em sistema multimídia, processado via filmagem do Road Video Survey, com identificação por tipo e área específicos.

**P: Quem desenvolveu a Metodologia Paragon?**
R: A Metodologia Paragon foi concebida pelo Prof. Armando Martins Pereira, integrante do "*Método Expedito de Avaliação Paragon — Pavimentos Flexíveis e Semi-Rígidos*". O livro é assinado pelos autores Paulo Cerejo, Christel Almeida Pereira, Humberto Santana e Armando Martins Pereira.

---

*Documento técnico extraído e estruturado a partir do livro "Metodologia Paragon" (Strata Engenharia). Conteúdo destinado a alimentar agente de IA para apoio a consultas técnicas sobre análise de defeitos de pavimentos asfálticos.*
