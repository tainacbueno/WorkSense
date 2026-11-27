
Anexo do usuárioAnexo do usuárioAnexo do usuário
Scripts, duas pastas de Logs, uma é a antiga e a segunda é o da correção 10. Retirei os últimos testes de Scripts e passei pra pasta Testes, mas o recalcular_correcao10 ainda está lá.
Agora ficou bem mais claro como você organizou o projeto. A estrutura atual está boa e não precisamos criar muitas pastas novas.

O que eu faria é manter Scripts, Logs e Testes como as três pastas principais, incorporando os arquivos da Correção 10 às pastas existentes. A versão anterior ficará preservada pela tag que você já criou.

Há, porém, um detalhe importante: conferi o código dos scripts que criamos e alguns deles dependem da localização dos outros arquivos. Precisamos ajustar esses caminhos antes de finalizar a organização.

1. Pasta Scripts
Arquivo

O que fazer

Pré-Processamento.ipynb

Manter a versão corrigida.

calculosDeScore.ipynb

Manter a versão corrigida.

extrairInfosLogTrello.ipynb

Manter como está.

recalcular_correcao10.py

Manter em Scripts.

debug.py

Manter como está por enquanto.

diagnostico_parcial.txt

Mover para Testes.

diagnostico_profissional.txt

Mover para Testes.

testar_correcao10.py

Manter somente em Testes.

testar_janelas_profissionais.py

Manter somente em Testes.

teste_sensibilidade_linguistica.py

Manter somente a versão corrigida em Testes.

Você fez certo ao manter o recalcular_correcao10.py em Scripts. Ele é um script de processamento e depende dos notebooks que estão nessa pasta.

Pelos prints, ainda aparecem cópias dos três scripts de teste em Scripts. Caso já os tenha movido posteriormente, pode desconsiderar essa observação.

2. Pastas Logs e Logs_correcao10
Aqui, eu unificaria as duas pastas. Os notebooks continuam utilizando ../Logs como caminho padrão, então manter duas pastas de logs pode fazer com que vocês utilizem resultados antigos sem perceber.

Primeiro, mantenha uma cópia de segurança dos logs antigos fora do repositório. Depois, faça as seguintes alterações:

Arquivo de Logs_correcao10

Destino

chat_scores.json

Substituir em Logs

indicadores_chat.json

Substituir em Logs

chat_scores_controle.json

Adicionar em Logs

indicadores_chat_controle.json

Adicionar em Logs

relatorio.md

Substituir em Testes

relatorio_sensibilidade_correcao10.md

Substituir Testes/relatorio_sensibilidade_linguistica.md, renomeando o novo arquivo

Todos os demais arquivos de Logs devem permanecer como estão, inclusive os registros profissionais e as duas versões das mensagens simuladas.

Caso ainda exista o chat_scores_sem_semantica.json, recomendo retirá-lo da versão atual após confirmar que nenhum outro código depende dele. Ele representava uma saída anterior e não foi atualizado pela Correção 10.

Não exclua a pasta Logs_correcao10 até conferir se todos os arquivos foram transferidos corretamente. Depois disso, ela deixa de ser necessária dentro do repositório.

3. Estrutura final sugerida
WorkSense/

Scripts/

outputs_graficos/

calculosDeScore.ipynb

Atualizado
debug.py

extrairInfosLogTrello.ipynb

Pré-Processamento.ipynb

Atualizado
recalcular_correcao10.py

Novo
Logs/

chat_scores.json

Atualizado
chat_scores_controle.json

Novo
indicadores_chat.json

Atualizado
indicadores_chat_controle.json

Novo
mensagens_simuladas_4perfis.json

mensagens_simuladas_4perfis_v2.json

... demais arquivos de Logs

Testes/

diagnostico_parcial.txt

Novo
diagnostico_profissional.txt

Novo
relatorio.md

Atualizado
relatorio_sensibilidade_linguistica.md

Atualizado
relatorio_sensibilidade_profissional.md

sensibilidade_profissional_resultados.csv

teste_sensibilidade_profissional.py

teste_sinalizacoes_worksense.py

testar_correcao10.py

Novo
testar_janelas_profissionais.py

Novo
teste_sensibilidade_linguistica.py

Atualizado
docs/

historico_base_desenvolvimento.md

Novo
Assim, teremos somente uma versão vigente dos notebooks, indicadores, scores e relatórios.

4. Pequenos ajustes necessários nos testes
Identifiquei dois problemas ao conferir os scripts que criamos anteriormente.

testar_correcao10.py
Como ele foi movido para Testes, precisamos permitir que encontre o recalcular_correcao10.py, que permanece em Scripts.

Antes deste import:

from recalcular_correcao10 import notebook_scope, group_by_user

Adicione:

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Scripts'))

testar_janelas_profissionais.py
Esse script também importa o recalcular_correcao10.py. Antes do import correspondente, adicione:

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Scripts'))

Substitua também:

spec=importlib.util.spec_from_file_location(
    'sens_prof', p/'teste_sensibilidade_profissional.py'
)

Por:

spec=importlib.util.spec_from_file_location(
    'sens_prof',
    Path(__file__).resolve().parent / 'teste_sensibilidade_profissional.py'
)

E substitua:

p/'extrairInfosLogTrello.ipynb'

Por:

HERE/'extrairInfosLogTrello.ipynb'

Esses ajustes são exclusivamente de localização dos arquivos. Não alteram os cálculos nem os resultados.

Atenção aos dados anteriores à Correção 10
O recalcular_correcao10.py e o testar_correcao10.py foram desenvolvidos especificamente para reproduzir e comparar os resultados anteriores à correção.

Portanto, depois de atualizar a pasta Logs, eles não deverão receber os novos indicadores como entrada para essa comparação histórica.

Uma vantagem da tag que você criou é que podemos recuperar a versão anterior em uma pasta separada, sem alterar a branch atual:

git worktree add --detach ../WorkSense_pre_correcao10 pre-correcao-10

Isso disponibilizará os arquivos que estavam commitados naquela versão. Não precisa executar esse comando agora.

5. Commits
Depois de organizar os arquivos e estando na branch feat/revisao-metodologica, sugiro separar as modificações em três commits:

fix: correct linguistic baseline self-reference
Notebooks corrigidos, script de recálculo e scripts de teste.

chore: update experimental results after baseline correction
JSONs corrigidos, relatórios e diagnósticos.

docs: document simulated dataset generation and refinement
Documentação referente às Correções 1, 2 e 3.

Por enquanto, faça a organização das pastas e depois me envie o resultado de:

git branch --show-current
git status --short

A partir disso, consigo montar os comandos exatos de git add para cada commit, sem incluir arquivos indesejados. Ainda não vamos utilizar git add ., nem excluir definitivamente os backups.

Não consegui verificar o estado do seu repositório local nem executar os testes nessa nova estrutura de pastas, por isso faremos essa conferência antes de consolidar a versão.

Preciso que refaça o historico_base_desenvolvimento.md, ficou mais parecendo um relatório seu  de conversa comigo (por ex, segundo os autores) do que a explicação final que decidimos.
Fiz as alterações nos arquivos que vc falou, mas como sei que estão funcionando corretamente antes de commitar?
PS C:\Users\taina\OneDrive\Documentos\WorkSense_TCC\WorkSense> git status --short
 M Logs/chat_scores.json
 D Logs/chat_scores_sem_semantica.json
 M Logs/indicadores_chat.json
 M "Scripts/Pr\303\251-Processamento.ipynb"
 M Scripts/calculosDeScore.ipynb
?? Logs/Logs_correcao10.json
?? Logs/chat_scores_controle.json
?? Logs/indicadores_chat_controle.json
?? Scripts/__pycache__/
?? Scripts/recalcular_correcao10.py
?? TCC_2026___Gestao_Preventiva_Uso_PLN.pdf
?? Testes/
?? docs/
?? "orienta\303\247\303\265es.txt"
?? parecer_final.txt
Tô na branch feat/revisao-metodologica
…

Pensou por 1m 10s
Agora estamos na etapa de consolidar os arquivos e verificar se a reorganização das pastas não prejudicou a execução dos scripts. Como você já está na branch feat/revisao-metodologica, podemos fazer tudo sem modificar a main.

1. Documentação da base de desenvolvimento
Refiz o arquivo Markdown para que tenha a linguagem de uma documentação oficial do WorkSense, escrita sob a perspectiva do projeto.

Retirei expressões como "segundo o relato dos autores", "durante esta revisão" e solicitações de recuperação de arquivos que você já confirmou não possuir.

Mantive a descrição da geração dos dados, as tabelas de distribuição, os critérios de refinamento, a comparação entre as versões disponíveis e os hashes dos arquivos. Também retirei os resultados intermediários que não conseguimos reproduzir.

historico_base_desenvolvimento.md

Versão revisada para a documentação oficial do projeto.
Baixar arquivo atualizado

Substitua o arquivo que está na pasta docs por esse.

A limitação referente à ausência dos prompts e das versões intermediárias continua documentada, pois é necessária para responder adequadamente ao parecer.

2. Conferência do git status
Seu status está, em grande parte, como eu esperava. Existem apenas alguns arquivos que precisamos conferir antes do commit.

Arquivo ou pasta

Ação

Logs/chat_scores.json

Commitar

Logs/indicadores_chat.json

Commitar

Logs/chat_scores_controle.json

Commitar

Logs/indicadores_chat_controle.json

Commitar

Logs/chat_scores_sem_semantica.json

Confirmar exclusão

Logs/Logs_correcao10.json

Verificar

Scripts/Pré-Processamento.ipynb

Commitar

Scripts/calculosDeScore.ipynb

Commitar

Scripts/recalcular_correcao10.py

Commitar

Scripts/__pycache__/

Ignorar

Testes/

Commitar os arquivos pertinentes

docs/

Commitar os arquivos pertinentes

PDF do TCC

Não incluir neste commit

orientações.txt

Não incluir

parecer_final.txt

Não incluir

O arquivo Logs/Logs_correcao10.json não corresponde a nenhuma das quatro saídas previstas no script de recálculo que criamos. Precisamos verificar seu conteúdo antes de decidir se deve permanecer.

O nome estranho que aparece no Git para Pré-Processamento.ipynb é apenas a representação escapada dos caracteres acentuados. Não é um problema no nome do arquivo.

3. Como testar antes de commitar
Montei uma estrutura de pastas equivalente à sua no meu ambiente e executei novamente os testes utilizando os arquivos corrigidos.

Testes estruturais da correção do baseline.

Reprodução dos 120 scores comunicacionais anteriores.

Reprodução dos 120 scores comunicacionais corrigidos e seus componentes.

Reprodução dos 120 scores da análise de controle e seus componentes.

Reprodução dos 8 scores profissionais.

Verificação das janelas temporais profissionais.

Análise de sensibilidade linguística.

Análise exploratória das sinalizações.

Comparação dos relatórios gerados com os relatórios atualizados anteriormente.

Todos passaram. Agora precisamos confirmar que o mesmo acontece no seu ambiente, pois não tenho acesso direto aos arquivos que você modificou localmente.

Execute os comandos a seguir pelo terminal do VS Code, na raiz do WorkSense, como você já está.

Teste 1 — Análise de sensibilidade linguística
Esse é o teste mais simples para começar, pois utiliza os novos arquivos JSON e não depende da execução do modelo spaCy.

Vamos criar uma pasta temporária fora do repositório para armazenar os resultados dos testes, evitando sobrescrever seus relatórios.

$saida = Join-Path $env:TEMP ("WorkSense_validacao_" + [guid]::NewGuid().ToString())
New-Item -ItemType Directory -Path $saida

Execute:

python -B Testes/teste_sensibilidade_linguistica.py `
    --oficial Logs/indicadores_chat.json `
    --controle Logs/indicadores_chat_controle.json `
    --scores Logs/chat_scores.json `
    --saida "$saida/relatorio_sensibilidade_linguistica.md"

Resultado esperado:

Recalculados 120 dias da execução oficial.
Maior diferença em relação ao JSON oficial: 0.0000 ponto.
Também deverá aparecer:

Atual {'A': 0.098, 'B': -4.3505, 'C': -0.6235, 'D': -5.0405}
Se os resultados forem esses, teremos confirmado que a análise de sensibilidade linguística está utilizando corretamente os novos indicadores.

Teste 2 — Janelas profissionais
python -B Testes/testar_janelas_profissionais.py --entrada Logs

Resultado esperado:

Profissional: 8/8 scores e componentes reproduzidos; eventos: 718
baseline: indicadores idênticos após excluir 327 eventos posteriores.
reanalise: indicadores idênticos após excluir 12 eventos posteriores.
Esse teste verifica tanto a reprodução dos resultados profissionais quanto a ausência de influência dos eventos posteriores ao encerramento das janelas, nas condições testadas.

Teste 3 — Sensibilidade profissional
python -B Testes/teste_sensibilidade_profissional.py `
    --trello Logs/trello_log_simulado_4perfis.json `
    --extrator Scripts/extrairInfosLogTrello.ipynb `
    --scores-notebook Scripts/calculosDeScore.ipynb `
    --oficial Logs/professional_period_scores.json `
    --csv "$saida/sensibilidade_profissional_resultados.csv"

Resultado esperado:

AUDITORIA: 8/8 scores e componentes reproduzidos; 718 eventos;
Esse teste é importante porque alteramos o notebook calculosDeScore.ipynb, que também contém o cálculo profissional. Precisamos confirmar que a correção comunicacional não afetou essa outra dimensão.

Teste 4 — Sinalizações
python -B Testes/teste_sinalizacoes_worksense.py `
    --chat Logs/chat_scores.json `
    --controle Logs/chat_scores_controle.json `
    --prof Logs/professional_period_scores.json `
    --prof-sens "$saida/sensibilidade_profissional_resultados.csv" `
    --chat-ind Logs/indicadores_chat.json `
    --chat-ind-controle Logs/indicadores_chat_controle.json `
    --chat-script Testes/teste_sensibilidade_linguistica.py `
    --saida "$saida/sinalizacoes"

Resultado esperado:

Perfil

Δ Comunicacional

Δ Profissional

Sinalização

A

+0,10

0,00

Nenhuma

B

−4,35

0,00

Comunicacional

C

−0,62

−24,63

Profissional

D

−5,04

−18,07

Ambas

Lembrando que esses resultados ainda utilizam os limiares demonstrativos anteriores, que serão revisados na Correção 4.

4. Testar a Correção 10 e reproduzir os resultados desde a base
Aqui utilizaremos a tag que você criou anteriormente. Esse é justamente um exemplo de como ela será útil.

Os scripts testar_correcao10.py e recalcular_correcao10.py precisam dos indicadores anteriores à correção, que não estão mais na sua pasta Logs.

O Git permite disponibilizar esses arquivos sem trocar de branch ou perder alterações locais.

Recuperar a versão anterior em uma pasta separada
Primeiro, confira se a tag contém os arquivos necessários:

git ls-tree -r --name-only pre-correcao-10 -- Logs

Estando tudo certo, execute:

git worktree add --detach ../WorkSense_pre_correcao10 pre-correcao-10

Sua estrutura ficará assim:

WorkSense_TCC/

WorkSense/

Projeto atual — branch de revisão
Scripts/

Logs/

Testes/

docs/

WorkSense_pre_correcao10/

Cópia do commit identificado pela tag
Scripts/

Logs/

Esse comando não modifica os arquivos da sua branch atual.

Teste 5 — Testes estruturais da Correção 10
Antes de executar, recomendo um pequeno ajuste adicional no testar_correcao10.py, para evitar problemas de codificação de caracteres no Windows.

Localize:

j=json.loads((src/'indicadores_chat.json').read_text()); old=json.loads((src/'chat_scores.json').read_text())

Substitua por:

j = json.loads((src/'indicadores_chat.json').read_text(encoding='utf-8'))
old = json.loads((src/'chat_scores.json').read_text(encoding='utf-8'))

Agora execute:

python -B Testes/testar_correcao10.py ../WorkSense_pre_correcao10/Logs

Resultado esperado:

Testes estruturais: OK (LOO, partição, referências disjuntas, lookup e MATTR mínima).
120/120 scores e componentes anteriores reproduzidos.
O restante da saída apresenta aquele diagnóstico parcial que fizemos inicialmente, alterando somente as referências de palavras e sentenças. Portanto, as variações exibidas nesse teste serão diferentes dos resultados finais corrigidos, como esperado.

Teste 6 — Recálculo completo
Esse é o teste mais importante para confirmar a reprodutibilidade da Correção 10. Requer o modelo pt_core_news_sm que você já utilizou anteriormente.

python -B Scripts/recalcular_correcao10.py `
    --entrada ../WorkSense_pre_correcao10/Logs `
    --saida "$saida/recalculo"

Resultado esperado:

user-001 Antes: -0.5115; depois: +0.0980
user-002 Antes: -4.6805; depois: -4.3505
user-003 Antes: -1.4280; depois: -0.6235
user-004 Antes: -5.9950; depois: -5.0405
Modelo spaCy: 3.8.0
Para verificar se os quatro arquivos gerados são equivalentes aos que você colocou em Logs, execute:

python -c "import json,sys; from pathlib import Path; names=['indicadores_chat.json','chat_scores.json','indicadores_chat_controle.json','chat_scores_controle.json']; a=Path('Logs'); b=Path(sys.argv[1]); results=[json.loads((a/n).read_text(encoding='utf-8'))==json.loads((b/n).read_text(encoding='utf-8')) for n in names]; print(*[f'{n}: {r}' for n,r in zip(names,results)],sep='\n'); sys.exit(0 if all(results) else 1)" "$saida/recalculo"

Os quatro resultados deverão ser True.

Assim, teremos confirmado que os JSONs que serão commitados correspondem aos resultados produzidos pelo código corrigido.

5. Ajustar o .gitignore
Verifique se já existe um arquivo .gitignore na raiz do projeto. Caso exista, acrescente estas regras, preservando as anteriores:

# Python
__pycache__/
*.pyc
.ipynb_checkpoints/
Isso evitará que os arquivos temporários do Python sejam incluídos no Git. Nos comandos anteriores, também utilizei a opção -B para evitar a criação de novos arquivos de bytecode.

Quanto ao PDF e aos documentos enviados pelo orientador, não os adicionaria ao repositório público. Podemos mantê-los localmente.

6. Checklist antes do commit
Validação pré-commit
0/12

Substituir o Markdown pela documentação revisada.

Executar a análise de sensibilidade linguística.

Executar o teste das janelas profissionais.

Executar a análise de sensibilidade profissional.

Executar o teste das sinalizações.

Executar os testes estruturais da Correção 10.

Recalcular os resultados comunicacionais.

Confirmar a equivalência dos quatro JSONs.

Conferir o .gitignore.

Verificar o arquivo Logs/Logs_correcao10.json.

Verificar se algum código ainda utiliza chat_scores_sem_semantica.json.

Conferir todos os arquivos pendentes no Git.
Quando terminar, execute:

git status --short --untracked-files=all

Essa opção é importante porque, no resultado anterior, o Git apresentou somente Testes/ e docs/, sem listar individualmente os arquivos novos dessas pastas.

Ainda não faça o commit. Me envie as saídas dos testes e desse último comando. Assim, conseguimos conferir os resultados e preparar os comandos de commit incluindo somente os arquivos desejados.

Os testes propostos verificam a implementação analítica e a reprodução dos resultados. Eles ainda não constituem uma execução integral de todos os notebooks, modelos de PLN e integrações do WorkSense, que será necessária posteriormente na etapa de reprodutibilidade solicitada pelo orientador.


historico_base_desenvolvimento.md
Documento




Base de desenvolvimento do WorkSense
1. Delineamento e geração dos dados
A base de desenvolvimento foi construída para examinar o comportamento dos indicadores, scores e sinalizações do WorkSense em condições simuladas. Foram definidos quatro perfis, correspondentes às seguintes condições experimentais:

Perfil	Dimensão comunicacional	Dimensão profissional
A	Estável	Estável
B	Alterada	Estável
C	Estável	Alterada
D	Alterada	Alterada
O período de referência (baseline) compreende 1 a 30 de maio de 2026, e o período de comparação, 31 de maio a 14 de junho de 2026. As condições experimentais foram estabelecidas antes da geração dos dados.

Mensagens
As 800 mensagens foram geradas integralmente pelo ChatGPT, mediante instruções sucessivas. Não foram utilizados conjuntos de dados de conversas reais como referência para a geração. As instruções priorizaram interações naturais, diversidade nas formas de escrita e coerência com as condições de cada perfil.

Para os perfis B e D, buscou-se introduzir mudanças sutis na forma de comunicação no período de comparação. Nos perfis A e C, buscou-se manter o padrão comunicacional entre os períodos. Evitou-se solicitar diretamente que as mensagens fossem mais positivas ou negativas ou utilizar frases com manifestações emocionais excessivamente explícitas. As alterações foram orientadas qualitativamente, sem metas numéricas de polaridade ou extensão das mensagens.

Registros profissionais
Os eventos profissionais foram gerados pelo ChatGPT com base na estrutura de Trello-base-log.json, arquivo exportado de um quadro do Trello utilizado pelos integrantes do projeto. O arquivo simulado trello_log_simulado_4perfis.json contém eventos de criação, atribuição, movimentação, conclusão e reabertura de cartões, além de alterações de prazos e checklists. Os cartões simulados foram representados em JSON, sem criação de cartões em um quadro real.

Para os perfis C e D, foram introduzidas ocorrências de atraso, pendências e retrabalho no período de comparação. A distribuição efetivamente observada está apresentada na seção seguinte. Nos perfis A e B, os registros profissionais não apresentaram atrasos, retrabalho ou pendências de checklist nos períodos analisados.

2. Distribuição da base consolidada
Fontes: mensagens_simuladas_4perfis_v2.json e indicadores_profissional_periodos.json. Ref. = referência; Comp. = comparação. Atrasados = cartões entregues com atraso; retrabalho = cartões com reabertura ou retorno no fluxo segundo os indicadores; checklist incompleto = cartões concluídos com checklist incompleto. Essas categorias não são mutuamente exclusivas.

Perfil	Período	Mensagens	Dias com mensagens	Mín.–máx./dia	Elegíveis	Entregues	Atrasados	Vencidos abertos	Retrabalho	Checklist incompleto
A	Ref.	133	20	4–10	7	7	0	0	0	0
A	Comp.	67	10	5–9	6	6	0	0	0	0
B	Ref.	138	20	4–10	7	7	0	0	0	0
B	Comp.	62	10	5–9	6	6	0	0	0	0
C	Ref.	132	20	4–10	7	7	2	0	0	0
C	Comp.	68	10	4–10	6	4	3	2	1	0
D	Ref.	139	20	5–10	7	7	0	0	0	0
D	Comp.	61	10	4–8	6	5	2	1	1	1
O arquivo de eventos profissionais contém 56 cartões. A soma das contagens de cartões elegíveis por perfil e período é 52. O retrabalho de C na comparação corresponde a um cartão reaberto; D apresenta um cartão com retorno no fluxo, sem reabertura.

Caracterização posterior das mensagens
Fonte: indicadores_chat.json, na versão posterior à correção do baseline. A extensão é a soma de totalWords dividida pelo número de mensagens no período; a proporção negativa é a soma de sentimentLabelCounts.NEG dividida pelo número de mensagens. São características observadas pelo processamento, não metas de geração nem rótulos independentes.

Perfil	Palavras/mensagem ref.	Palavras/mensagem comp.	Negativas ref.	Negativas comp.
A	22,69	21,87	1/133 (0,75%)	2/67 (2,99%)
B	21,60	19,26	2/138 (1,45%)	7/62 (11,29%)
C	20,56	19,91	2/132 (1,52%)	0/68 (0,00%)
D	20,60	19,18	3/139 (2,16%)	5/61 (8,20%)
3. Refinamento e versões da base
A geração das mensagens envolveu sucessivas revisões qualitativas. Entre os problemas identificados estavam a repetição de frases e estruturas entre usuários, inclusive mensagens que se diferenciavam pela substituição de poucas palavras, e a pouca diferenciação das formas de escrita. As revisões procuraram tornar as interações mais naturais e preservar as condições experimentais planejadas.

Parte do refinamento ocorreu após a inspeção dos indicadores e scores preliminares. No Perfil C, mensagens sobre dificuldades na execução de tarefas apresentavam alterações comunicacionais incompatíveis com a estabilidade planejada. A redação dessas mensagens foi revista para preservar os relatos de dificuldades profissionais, evitando alterações excessivas no tom e na forma de comunicação.

As duas versões preservadas apresentam as seguintes diferenças:

Característica	mensagens_simuladas_4perfis.json	mensagens_simuladas_4perfis_v2.json
Mensagens	800	800
Mensagens por perfil	200	200
Dias com mensagens por perfil	45	30
Mensagens nos fins de semana	Sim	Não
A comparação dos registros pelo identificador da mensagem mostra que o texto e a data e horário foram modificados nos 800 registros. Os identificadores das mensagens e dos usuários, os nomes registrados, os cenários e os períodos experimentais foram preservados. A versão mensagens_simuladas_4perfis_v2.json é a base consolidada utilizada nos experimentos.

4. Limitações do registro e finalidade da base
Os prompts completos, a versão exata do modelo e os parâmetros de geração não foram registrados sistematicamente. Durante o refinamento, os arquivos intermediários foram substituídos para manter os nomes utilizados pelo código. Por isso, não foi possível recuperar todas as etapas, determinar quantas mensagens e cartões foram alterados especificamente após a inspeção dos resultados preliminares ou reproduzir os scores imediatamente anteriores e posteriores a cada ajuste. As diferenças entre as duas versões preservadas representam o conjunto de modificações observáveis, sem permitir atribuí-las integralmente aos resultados preliminares.

A utilização dos resultados preliminares para refinar a base e definir parâmetros caracteriza este conjunto como base de desenvolvimento e calibração. Os resultados permitem examinar a coerência interna do método e a sensibilidade aos parâmetros, mas não constituem uma avaliação independente da capacidade de sinalização. Os dados consolidados foram mantidos inalterados durante os testes de sensibilidade.

5. Identificação dos arquivos
Hashes SHA-256 das versões utilizadas na documentação da base. O hash dos indicadores comunicacionais corresponde à saída posterior à correção do baseline.

mensagens_simuladas_4perfis.json: 6ae5f3aa45c5a5d6cd1ede266db56aa3783f301993a67a00be77c4ddec267707
mensagens_simuladas_4perfis_v2.json: 6b5379e1a7dbd55802901ccb808888817b676831d544660ac39b2729d0985e01
trello_log_simulado_4perfis.json: 6f88d96c5ec8a6a55531dd4176047825f861296c25105bcc2abec5153d062f1f
indicadores_chat.json: 22ee3a9ea9d432eb643e3cd5a2b9a38bcb42c337242f4b8ab938811d7eb219c7
indicadores_profissional_periodos.json: 01a17351e959b2e9c87edbae5a4425e150be22fa4b58c65aa5f4af2e77e24bb1
-1,65