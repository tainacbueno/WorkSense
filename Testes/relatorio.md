# Regras de sinalização — teste exploratório do WorkSense

## Critério demonstrativo
- Δ = média da reanálise menos média do baseline (chat) ou score por período (profissional).
- Sinalizar queda no ciclo mais recente se Δcom <= -4 pontos ou Δprof <= -15 pontos, por dimensão.
- Esse é um exemplo exploratório de limiares, **não uma regra validada ou aprovada**.
- O gestor visualizaria a variação, os componentes e os avisos técnicos; histórico de sinalizações anteriores apenas como observação, nunca como alerta cumulativo.

## Resultado demonstrativo

| Perfil | ΔCom | ΔProf | Sinalização |
|---|---:|---:|---|
| A | -0.51 | +0.00 | Nenhuma |
| B | -4.68 | +0.00 | Comunicacional |
| C | -1.43 | -24.63 | Profissional |
| D | -5.99 | -18.07 | Ambas |

## Dependência dos limiares

### Dimensão comunicacional

| Limiar de queda (pontos) | Perfis sinalizados |
|---:|---|
| 1 | B, C, D |
| 2 | B, D |
| 3 | B, D |
| 4 | B, D |
| 5 | D |
| 6 | Nenhum |
| 7 | Nenhum |

### Dimensão profissional

| Limiar de queda (pontos) | Perfis sinalizados |
|---:|---|
| 5 | C, D |
| 10 | C, D |
| 15 | C, D |
| 18 | C, D |
| 20 | C |
| 25 | Nenhum |
| 30 | Nenhum |

## Verificação de controle (componente comunicacional)

| Perfil | Referência -> controle | Controle -> reanálise |
|---|---:|---:|
| A | -2.09 | -1.29 |
| B | -2.79 | -1.75 |
| C | -2.15 | +0.74 |
| D | -1.66 | -4.94 |

## Sensibilidade das decisões aos parâmetros (limiares apenas demonstrativos)

| Dimensão | Perfil | Número de variantes sinalizando / total |
|---|---|---:|
| Comunicacional | A | 0/28 |
| Comunicacional | B | 27/28 |
| Comunicacional | C | 0/28 |
| Comunicacional | D | 28/28 |
| Profissional | A | 0/27 |
| Profissional | B | 0/27 |
| Profissional | C | 27/27 |
| Profissional | D | 26/27 |

No controle interno, 0/112 avaliações perfil-variante ultrapassaram o limiar comunicacional demonstrativo de 4 pontos.
Este número é específico do experimento e não representa uma taxa de falso positivo em produção.

## Limitações
- Os limiares foram explorados **depois** de conhecermos os scores e os perfis. A correspondência com os rótulos simulados não valida os limites para uso real.
- O controle interno contém apenas uma divisão temporal e usa referência de dez dias úteis. Não fornece taxa de falso positivo populacional.
- A simulação tem apenas quatro perfis, scores profissionais de A/B no teto (100) e progressão do workflow sem variação. Isso limita o estudo de alertas indevidos.
- A regra demonstrativa sinaliza quedas. Crescimentos do score, mesmo grandes, não são avaliados como alteração aqui; uma regra de mudanças bidirecionais exigiria avaliação complementar.
- Scores ausentes ou insuficiência de registros devem gerar estado "dados insuficientes", não uma pontuação zero nem "nenhuma alteração".
- Avisos técnicos (como cartões vencidos abertos) são informações contextuais, não gatilhos automáticos adicionais neste teste.
- Somente o último ciclo deve determinar a sinalização exibida. Eventual recorrência de sinalizações anteriores cabe no máximo em observação separada.
