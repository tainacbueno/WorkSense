# WorkSense

**Ferramenta experimental de apoio à identificação de alterações nos padrões comunicacionais e nos registros profissionais de equipes.**

O WorkSense foi desenvolvido como Trabalho de Conclusão de Curso de Ciência da Computação do Centro Universitário FEI. A proposta é comparar indicadores extraídos de mensagens e de registros de tarefas com o histórico de cada perfil, para mostrar variações que possam ser examinadas por uma pessoa responsável.

O estudo utilizou **dados simulados**. Os scores e as sinalizações não medem diretamente desempenho, produtividade ou estado emocional e não devem ser usados para diagnósticos ou decisões punitivas.

## Como o projeto funciona

O projeto possui duas partes:

- **Fluxo operacional:** recebe mensagens pelo Telegram, identifica o usuário, consulta vínculos no PostgreSQL e encaminha interações ao agente conversacional (Ollama/Qwen2.5-3B-Instruct) ou comandos de tarefas ao Trello, por meio do n8n.
- **Módulos de análise:** scripts e notebooks em Python leem arquivos JSON simulados/exportados, extraem indicadores, calculam scores e registram variações para a avaliação das sinalizações.

**Estado da implementação:** o fluxo operacional e os módulos analíticos foram desenvolvidos, mas a integração automática entre eles permaneceu parcial. Na avaliação do TCC, as análises foram executadas diretamente sobre arquivos, de forma separada do workflow.

### Tecnologias utilizadas

| Tecnologia | Uso no WorkSense |
| --- | --- |
| Telegram | Interface de mensagens e comandos |
| n8n | Automação das interações entre serviços |
| PostgreSQL | Registros operacionais e vínculos entre plataformas |
| Trello | Fonte dos eventos relacionados às tarefas |
| Ollama + Qwen2.5-3B-Instruct | Respostas do agente conversacional; não calcula os scores |
| Python + spaCy | Processamento linguístico das mensagens |
| pysentimiento | Estimativa de polaridade textual em português |
| Sentence Transformers | Representações vetoriais e comparação semântica |
| Pandas e NumPy | Organização dos dados e cálculos |
| scikit-learn | Cálculo da similaridade de cosseno na análise semântica |

## Base experimental

Foram avaliados quatro perfis fictícios, definidos por duas dimensões:

| Perfil | Comunicação | Registros profissionais |
| --- | --- | --- |
| A | Estável | Estável |
| B | Alterada | Estável |
| C | Estável | Alterados |
| D | Alterada | Alterados |

A base final descrita no artigo contém **800 mensagens textuais** e registros de **56 cartões do Trello**, dos quais foram processados **718 eventos normalizados**.

Os períodos de comparação foram:

- **Baseline:** 1º a 30 de maio de 2026 (30 dias corridos; 20 dias com mensagens por perfil).
- **Reanálise:** 31 de maio a 14 de junho de 2026 (15 dias corridos; 10 dias com mensagens por perfil).

A comparação é feita com o histórico do próprio perfil. Os dados foram revisados e refinados durante o desenvolvimento; por isso, a avaliação final tem caráter **exploratório**, e a correspondência entre sinalizações e perfis planejados não representa validação independente.

## Indicadores e cálculo dos scores

Os scores variam de **0 a 100** e são calculados separadamente para cada dimensão. São medidas construídas a partir dos indicadores disponíveis, não avaliações absolutas de pessoas.

### 1. Score comunicacional

Combina dois componentes:

| Componente | Peso no score | Como é obtido |
| --- | ---: | --- |
| **Sentimento** | 53,33% (8/15) | Diferença entre as probabilidades médias de polaridade positiva e negativa |
| **Interação linguística** | 46,67% (7/15) | Proximidade das características das mensagens ao baseline individual |

**Sentimento.** O modelo estima probabilidades de texto positivo, negativo e neutro. A pontuação parte de 50 e aumenta quando a probabilidade positiva supera a negativa, ou diminui no caso inverso. A regra utilizada é `50 + 50 × (positiva − negativa)`, limitada à escala de 0 a 100. Uma pontuação próxima de 50 indica equilíbrio entre essas probabilidades, não um estado emocional específico.

**Interação linguística.** Compara três características das mensagens com o padrão de referência:

| Indicador | Peso dentro da interação linguística |
| --- | ---: |
| Média de palavras por mensagem | 35% |
| Diversidade lexical (MATTR) | 45% |
| Média de sentenças por mensagem | 20% |

A referência de palavras e sentenças utiliza a **mediana** e o **desvio absoluto mediano (MAD)** do baseline. A MATTR é calculada sobre os lemas válidos das mensagens de cada período, com janela móvel de **20 lemas**, e comparada ao valor do baseline. Se não houver lemas suficientes, a MATTR fica indisponível. Quanto maior o afastamento dessas referências, menor a pontuação de proximidade.

**Parâmetros da normalização linguística na configuração final:**

| Parâmetro | Valor | Para que serve |
| --- | ---: | --- |
| Escala mínima para palavras por mensagem | 2 | Evita dividir uma diferença por uma escala muito pequena |
| Escala mínima para sentenças por mensagem | 0,25 | Mesma finalidade para sentenças |
| Escala mínima para MATTR | 0,08 | Mesma finalidade para diversidade lexical |
| Escala proporcional à referência | 20% | Define uma escala mínima relativa ao padrão do perfil |
| Multiplicador do MAD | 1,4826 | Ajusta a medida de dispersão usada na comparação |
| Divisor da distância normalizada | 3 | Controla a velocidade de redução da pontuação |

Em termos simples, cada diferença é comparada com a **maior escala aplicável**: o mínimo fixo, 20% do valor absoluto da referência ou, para palavras e sentenças, o MAD ajustado. A distância resultante é convertida em uma pontuação entre 0 e 100. O parâmetro de 20% é uma escolha empírica do experimento, não um limite validado para outras equipes.

O score comunicacional é calculado **por dia com registros** e depois resumido pela **média do período**. A MATTR, apesar de ser calculada por período, participa dos scores diários correspondentes. A quantidade de mensagens ajuda a caracterizar a disponibilidade dos dados, mas não recebe peso próprio na composição do score.

**Mudança semântica:** embeddings são usados para comparar o conteúdo textual com a referência do baseline e com a **última data com mensagens registrada para o perfil**. Essas medidas são disponibilizadas como informação complementar e **não entram no score comunicacional**.

### 2. Score profissional

Os eventos do Trello são organizados cronologicamente para reconstruir movimentações, prazos, conclusões, reaberturas e checklists. Os indicadores são agregados por perfil e janela de análise.

| Componente | Peso no score | O que considera |
| --- | ---: | --- |
| **Progresso** | 25% | Passagem dos cartões concluídos pelas etapas intermediárias esperadas |
| **Prazo** | 40% | Entrega das obrigações elegíveis, pontualidade e duração dos atrasos |
| **Qualidade operacional** | 35% | Reaberturas/retornos de etapa e problemas em checklists |

O componente **Prazo** utiliza três parcelas: **entrega (40%)**, **pontualidade (40%)** e **duração dos atrasos (20%)**. A entrega considera obrigações cujo prazo já chegou até o fim da janela, incluindo cartões que permaneceram abertos e vencidos. A pontualidade considera as obrigações entregues; se nenhuma foi entregue apesar de haver obrigações elegíveis, sua pontuação é zero. A duração média dos atrasos considera entregas atrasadas e cartões vencidos ainda abertos. Sua pontuação diminui linearmente até zero ao atingir **48 horas** de atraso médio.

O componente **Qualidade operacional** combina **retrabalho (60%)** e **problemas em checklist (40%)**. O retrabalho contabiliza cartões reabertos ou que retornaram a etapas anteriores, sem contar o mesmo cartão várias vezes. Os problemas de checklist são avaliados em cartões concluídos para os quais há informação disponível sobre os itens. Esses eventos são sinais indiretos do fluxo de trabalho: uma reabertura ou pendência não comprova, por si só, má qualidade da entrega.

Ao contrário do score comunicacional, o **score profissional é calculado diretamente para cada período**, a partir dos indicadores agregados. Não é uma média de pontuações diárias.

### Dados insuficientes

Quando um indicador não pode ser calculado por falta de dados aplicáveis, ele fica **sem pontuação**, em vez de receber zero. Os pesos são redistribuídos proporcionalmente entre os componentes disponíveis. Se nenhum componente estiver disponível, não há score calculável.

As saídas incluem `evidenceCoverage` (cobertura das evidências utilizadas) e avisos, por exemplo, quando não há tarefas elegíveis ou lemas suficientes para calcular a MATTR. **Cobertura não é uma medida de precisão ou confiança estatística no resultado.**

## Comparação temporal e sinalizações

Para cada perfil, compara-se o resultado da reanálise ao baseline:

`variação = score da reanálise − score do baseline`

Na configuração exploratória do TCC, foram examinados estes critérios:

| Dimensão | Sinalização quando a redução for de... |
| --- | ---: |
| Comunicacional | **4 pontos ou mais** |
| Profissional | **15 pontos ou mais** |

As dimensões são avaliadas separadamente, permitindo sinalizações comunicacionais, profissionais ou simultâneas. **Somente reduções acionam essas regras demonstrativas**; aumentos também aparecem na comparação, mas não geram sinalização por esses critérios. A sinalização se refere ao **ciclo de reanálise mais recente**.

Na avaliação do TCC, essas regras foram aplicadas aos resultados dos perfis. Os notebooks analisados calculam scores e variações, mas não apresentam uma rotina separada de envio automático de alertas.

Os limiares foram examinados **depois da observação dos resultados** e não foram validados para uso real. A ausência de sinalização significa apenas que os critérios definidos não foram atingidos.

## Testes de sensibilidade

Os testes verificaram se alterar um parâmetro, mantendo a base experimental fixa, modifica os scores ou as sinalizações. As alternativas foram utilizadas para **examinar a dependência dos resultados**, e não para escolher retrospectivamente a configuração de maior concordância com os perfis planejados.

No eixo comunicacional, foram examinados limites mínimos, escala proporcional, multiplicador do MAD, divisor de distância e peso da MATTR. Por exemplo, a escala proporcional original de **20%** foi comparada a **10%, 15%, 25% e 30%**.

No eixo profissional, foram examinados pesos dos componentes e o limite usado para pontuar atrasos. O peso de Prazo, por exemplo, foi testado entre **20% e 60%**, tendo **40%** como configuração original. **Ao modificar um peso, os demais foram redistribuídos proporcionalmente**, mantendo a soma em 100%. O limite original de atraso médio de **48 horas** foi comparado a outros limites entre **12 e 144 horas**.

Esses testes mostraram que as principais tendências permaneceram, mas algumas decisões de sinalização mudaram conforme os parâmetros. Os scripts de sensibilidade registram as configurações examinadas e os respectivos resultados.

## Como consultar e reproduzir as análises

A parte analítica utiliza três notebooks principais. Os caminhos presentes no código pressupõem que eles sejam executados em uma pasta como `Scripts/`, com os dados em uma pasta `Logs/` no mesmo nível.

| Ordem | Notebook | Entrada principal | Saída principal |
| --- | --- | --- | --- |
| 1 | `Pré-Processamento(3).ipynb` | `mensagens_simuladas_4perfis_v2.json` | `indicadores_chat.json` |
| 2 | `extrairInfosLogTrello(2).ipynb` | `trello_log_simulado_4perfis.json` | `trello_events_normalizados.json`, `indicadores_profissional.json`, `indicadores_profissional_periodos.json` |
| 3 | `calculosDeScore(5).ipynb` | Os arquivos de indicadores anteriores | `chat_scores.json`, `professional_scores.json`, `professional_period_scores.json` |

Esses arquivos são lidos ou gravados em `../Logs/` em relação aos notebooks. O notebook de scores também produz tabelas, arquivos CSV e gráficos em `outputs_graficos/`.

Os notebooks usam Python, spaCy (`pt_core_news_sm`), pysentimiento, Sentence Transformers (`paraphrase-multilingual-MiniLM-L12-v2`), Pandas, NumPy, scikit-learn e Matplotlib. A análise de sentimento é inicializada com `create_analyzer(task="sentiment", lang="pt")`; para reproduzir exatamente o modelo utilizado, também é necessário registrar a versão das dependências. As instruções de instalação e a versão do ambiente devem corresponder à execução final do experimento.

**Testes de sensibilidade:** os scripts `teste_sensibilidade_linguistica.py` e `teste_sensibilidade_profissional.py` executam variações de parâmetros sem modificar as bases oficiais. O teste comunicacional também utiliza um arquivo de indicadores do período de controle. Confira os caminhos e argumentos de execução dos scripts, pois as versões recebidas originalmente apontam para nomes anteriores dos notebooks.

O agente Qwen2.5-3B-Instruct participa do fluxo conversacional; ele **não é necessário para recalcular os scores a partir dos arquivos de indicadores já produzidos**.

## Limites da avaliação

- O experimento utiliza perfis e registros simulados, refinados durante o desenvolvimento.
- A análise verifica o comportamento do método nessa base, sem demonstrar capacidade de detectar alterações reais em colaboradores.
- Os indicadores textuais e operacionais podem mudar por motivos distintos dos planejados no experimento.
- O pré-treinamento do modelo de sentimento utiliza publicações do Twitter em português; seu desempenho em mensagens profissionais não foi avaliado neste estudo.
- A integração entre o fluxo operacional e os módulos de análise ainda não é totalmente automatizada.

Os resultados devem ser interpretados com os indicadores de origem e seu contexto, sempre sob avaliação humana.

## Autores

Caio Augusto Arnoni · Guilherme Matias Rodrigues de Souza · Tainá Cunha Bueno  
**Orientador:** Plinio Thomaz Aquino Junior  
**Instituição:** Centro Universitário FEI — Ciência da Computação, São Bernardo do Campo (2026).
