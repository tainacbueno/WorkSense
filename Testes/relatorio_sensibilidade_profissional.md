# WorkSense — Sensibilidade dos scores profissionais

## Base e método

Arquivos de entrada: `trello_log_simulado_4perfis.json`, `extrairInfosLogTrello(1).ipynb`, `calculosDeScore(3).ipynb` e `professional_period_scores.json`. Reexecução independente das funções dos notebooks: **718 eventos normalizados**, 56 cartões, fluxo inferido `Em Andamento` e `Em Teste`, **8/8 scores e componentes reproduzidos exatamente**.

As janelas são *baseline* de 01/05/2026 a 30/05/2026 (30 dias) e *reanálise* de 31/05/2026 a 14/06/2026 (15 dias), ambas inclusivas. Cada rodada altera somente o parâmetro indicado, preservando a base simulada. Quando um peso agregado muda, os demais são redistribuídos proporcionalmente e a soma permanece 1. Resultados são descrições condicionais da base simulada, não estimativas de acurácia em dados reais.

## Referência

Score profissional: `0,25 × progressão + 0,40 × prazos + 0,35 × qualidade`.

Prazos: `0,40 × entrega + 0,40 × pontualidade + 0,20 × gravidade média dos atrasos`. A gravidade é `100 × max(0, 1 − média_de_horas_de_atraso / limite_de_horas)` quando há atrasos; vale 100 quando não há. O valor vigente do limite é **48 horas**.

Qualidade: `0,60 × (100 × (1 − taxa_de_retrabalho)) + 0,40 × (100 × (1 − taxa_de_problemas_em_checklists))`. Quando um subcomponente não é calculável, os pesos dos disponíveis são renormalizados conforme o código; nesta base, todos os componentes finais foram calculáveis.

| Perfil | Baseline | Reanálise | Variação |
|---|---:|---:|---:|
| A | 100,00 | 100,00 | 0,00 |
| B | 100,00 | 100,00 | 0,00 |
| C | 95,10 | 70,47 | −24,63 |
| D | 100,00 | 81,93 | −18,07 |

## 1. Peso externo de prazos

Redistribuição proporcional de progressão:qualidade = 25:35.

| Prazos | ΔA | ΔB | ΔC | ΔD |
|---|---:|---:|---:|---:|
| 20% | 0,00 | 0,00 | −15,82 | −13,90 |
| 30% | 0,00 | 0,00 | −20,22 | −15,98 |
| **40% (oficial)** | **0,00** | **0,00** | **−24,63** | **−18,07** |
| 50% | 0,00 | 0,00 | −29,04 | −20,15 |
| 60% | 0,00 | 0,00 | −33,44 | −22,24 |

O parâmetro é relevante para a **magnitude** das sinalizações, embora mantenha a ordem de variação C > D > A=B neste conjunto.

## 2. Peso externo de progressão

Redistribuição proporcional de prazos:qualidade = 40:35.

| Progressão | ΔC | ΔD |
|---|---:|---:|
| 0% (ablação) | −32,84 | −24,09 |
| 15% | −27,91 | −20,48 |
| **25% (oficial)** | **−24,63** | **−18,07** |
| 35% | −21,35 | −15,66 |

O componente de progressão é **100 em todos os oito casos**, portanto não há observações que permitam testar sua capacidade discriminativa. Reduzir seu peso amplia a participação relativa dos componentes que variam. Isso não justifica removê-lo com base apenas neste experimento.

## 3. Peso externo de qualidade

Redistribuição proporcional de progressão:prazos = 25:40.

| Qualidade | ΔC | ΔD |
|---|---:|---:|
| 20% | −27,54 | −18,39 |
| **35% (oficial)** | **−24,63** | **−18,07** |
| 50% | −21,72 | −17,75 |

## 4. Limite máximo de horas na gravidade dos atrasos

Demais pesos fixos. **Média de horas observada nos atrasos**: C baseline = 2,0 h; C reanálise = 72,6 h; D reanálise = 19,0 h; perfis A/B e D baseline não possuem atraso. A média inclui atrasos de cartões concluídos e cartões ainda vencidos e abertos, conforme a extração.

| Limite | ΔC | ΔD | Score C reanálise | Score D reanálise |
|---|---:|---:|---:|---:|
| 12 h | −23,63 | −22,90 | 70,47 | 77,10 |
| 24 h | −24,29 | −21,24 | 70,47 | 78,76 |
| 36 h | −24,51 | −19,12 | 70,47 | 80,88 |
| **48 h (oficial)** | **−24,63** | **−18,07** | **70,47** | **81,93** |
| 72 h | −24,74 | −17,01 | 70,47 | 82,99 |
| 96 h | −22,84 | −16,49 | 72,42 | 83,51 |
| 144 h | −20,89 | −15,96 | 74,43 | 84,04 |

**Saturação importante**: como C reanálise apresenta 72,6 horas médias, sua gravidade fica em **zero** para limites iguais ou inferiores a 72 h; nesses limites, o score C na reanálise fica exatamente igual. Para limites superiores a 72,6 h, o score C aumenta. O valor de 48 h é uma escolha de normalização cuja fundamentação ou origem empírica deve ser declarada, evitando apresentá-lo como um padrão cientificamente estabelecido sem fonte.

## 5. Peso da gravidade dentro do componente de prazos

Os pesos remanescentes de entrega e pontualidade são iguais e somam o restante.

| Peso da gravidade | ΔC | ΔD |
|---|---:|---:|
| 10% | −22,39 | −17,62 |
| **20% (oficial)** | **−24,63** | **−18,07** |
| 30% | −26,87 | −18,52 |
| 40% | −29,10 | −18,97 |

## 6. Peso do retrabalho dentro da qualidade

O checklist recebe o peso complementar.

| Retrabalho | ΔC | ΔD |
|---|---:|---:|
| 40% | −23,23 | −18,07 |
| **60% (oficial)** | **−24,63** | **−18,07** |
| 80% | −26,03 | −18,07 |

Em D, retrabalho e checklist têm o mesmo score (83,33); mudar seus pesos não altera o resultado. Em C, retrabalho = 80 e checklist = 100 na reanálise, por isso o peso de retrabalho tem algum efeito.

## Limites e interpretação

- **Estabilidade descritiva:** em todas as configurações testadas, A e B ficam em zero, C e D apresentam quedas, e a queda de C é maior do que a de D. Isso mostra estabilidade da interpretação **nesta base simulada**.
- **Dependência quantitativa:** os scores e variações de C/D dependem materialmente do peso de prazos, da importância relativa da progressão e do limite de horas. Limiares fixos de sinalização podem ser afetados; ainda não foram testados.
- **Efeito de teto:** os scores de A e B são 100 em ambos os períodos. O experimento não mede a propensão a falsos alertas diante de flutuações profissionais benignas e não discrimina configurações de peso com esses perfis.
- **Progressão não exercitada:** o componente é 100 em todos os períodos; o experimento não testa situações de passagem direta por etapas ou trajetórias incompletas.
- **Escolhas pós-resultados:** nenhuma configuração alternativa deve ser adotada apenas por gerar separações maiores. Preservar a configuração vigente como referência e documentar a sensibilidade observada.

## Próxima etapa

Aplicar as regras de sinalização para a configuração oficial e para uma seleção de configurações plausíveis, verificando se aparecem mudanças de status (sinaliza/não sinaliza). Interpretar os limiares em relação aos resultados do controle, à finalidade da ferramenta e ao custo de falsos alertas, sem ajustar o desenho da base para atingir as sinalizações desejadas.

Para resultados detalhados, consultar `sensibilidade_profissional_resultados.csv` (108 linhas, uma por configuração/perfil); para reprodução, executar `teste_sensibilidade_profissional.py` com os notebooks e o log indicados.
