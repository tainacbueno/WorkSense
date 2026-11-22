# Sensibilidade da normalização linguística — WorkSense

**Configuração oficial:** sentimento 8/15; interação linguística 7/15;
pesos internos 35% comprimento, 45% MATTR e 20% sentenças.
Somente um parâmetro é modificado de cada vez.

As células com valores representam variações de médias de scores, em pontos.

## Baseline oficial → reanálise

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. comprimento=1 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. comprimento=3 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. comprimento=4 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. comprimento=5 | -0,53 | -4,40 | -1,48 | -5,84 |
| mín. comprimento=6 | -0,55 | -4,14 | -1,54 | -5,72 |
| mín. sentenças=0.15 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. sentenças=0.35 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. sentenças=0.45 | -0,52 | -4,59 | -1,48 | -5,64 |
| mín. sentenças=0.55 | -0,53 | -4,47 | -1,57 | -5,30 |
| mín. MATTR=0.04 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. MATTR=0.12 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. MATTR=0.16 | -0,51 | -4,68 | -1,43 | -6,00 |
| mín. MATTR=0.2 | -0,47 | -4,67 | -1,24 | -5,91 |
| escala proporcional=10% | -1,08 | -7,07 | -2,89 | -8,28 |
| escala proporcional=15% | -0,66 | -5,58 | -1,78 | -7,25 |
| escala proporcional=25% | -0,42 | -4,14 | -1,22 | -5,18 |
| escala proporcional=30% | -0,37 | -3,78 | -1,07 | -4,64 |
| divisor=2 | -0,73 | -6,03 | -1,96 | -7,71 |
| divisor=2.5 | -0,60 | -5,22 | -1,64 | -6,80 |
| divisor=3.5 | -0,45 | -4,29 | -1,27 | -5,42 |
| divisor=4 | -0,40 | -4,01 | -1,16 | -4,98 |
| multiplicador MAD=1 | -0,51 | -4,68 | -1,43 | -6,00 |
| multiplicador MAD=1.25 | -0,51 | -4,68 | -1,43 | -6,00 |
| multiplicador MAD=1.75 | -0,51 | -4,68 | -1,43 | -6,00 |
| multiplicador MAD=2 | -0,51 | -4,68 | -1,43 | -5,99 |
| peso MATTR=30% | -0,23 | -5,36 | -0,52 | -6,55 |
| peso MATTR=60% | -0,79 | -4,00 | -2,34 | -5,43 |

## Controle → reanálise

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. comprimento=1 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. comprimento=3 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. comprimento=4 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. comprimento=5 | -0,97 | -3,29 | +0,19 | -5,44 |
| mín. comprimento=6 | -0,88 | -3,02 | +0,08 | -5,40 |
| mín. sentenças=0.15 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. sentenças=0.35 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. sentenças=0.45 | -0,98 | -3,56 | +0,26 | -5,14 |
| mín. sentenças=0.55 | -1,02 | -3,51 | +0,18 | -4,82 |
| mín. MATTR=0.04 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. MATTR=0.12 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. MATTR=0.16 | -0,98 | -3,59 | +0,32 | -5,47 |
| mín. MATTR=0.2 | -0,97 | -3,58 | +0,42 | -5,40 |
| escala proporcional=10% | -1,65 | -5,74 | -0,14 | -7,18 |
| escala proporcional=15% | -1,20 | -4,34 | +0,38 | -6,40 |
| escala proporcional=25% | -0,87 | -3,13 | +0,29 | -4,86 |
| escala proporcional=30% | -0,80 | -2,83 | +0,26 | -4,45 |
| divisor=2 | -1,26 | -4,72 | +0,41 | -6,70 |
| divisor=2.5 | -1,10 | -4,04 | +0,36 | -6,09 |
| divisor=3.5 | -0,90 | -3,26 | +0,29 | -5,04 |
| divisor=4 | -0,84 | -3,02 | +0,28 | -4,71 |
| multiplicador MAD=1 | -0,98 | -3,59 | +0,32 | -5,47 |
| multiplicador MAD=1.25 | -0,98 | -3,59 | +0,32 | -5,47 |
| multiplicador MAD=1.75 | -0,98 | -3,59 | +0,32 | -5,47 |
| multiplicador MAD=2 | -1,01 | -3,59 | +0,32 | -5,47 |
| peso MATTR=30% | -1,01 | -4,17 | +1,07 | -5,86 |
| peso MATTR=60% | -0,96 | -3,00 | -0,43 | -5,08 |

## Referência → controle

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. comprimento=1 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. comprimento=3 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. comprimento=4 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. comprimento=5 | -0,71 | -1,38 | -1,62 | -1,15 |
| mín. comprimento=6 | -0,65 | -1,42 | -1,62 | -0,92 |
| mín. sentenças=0.15 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. sentenças=0.35 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. sentenças=0.45 | -0,72 | -1,32 | -1,64 | -1,35 |
| mín. sentenças=0.55 | -0,69 | -1,29 | -1,64 | -1,30 |
| mín. MATTR=0.04 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. MATTR=0.12 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. MATTR=0.16 | -0,72 | -1,34 | -1,64 | -1,40 |
| mín. MATTR=0.2 | -0,68 | -1,33 | -1,59 | -1,36 |
| escala proporcional=10% | -1,94 | -1,28 | -2,25 | -3,57 |
| escala proporcional=15% | -1,17 | -1,34 | -1,85 | -2,17 |
| escala proporcional=25% | -0,44 | -1,34 | -1,51 | -0,93 |
| escala proporcional=30% | -0,26 | -1,34 | -1,43 | -0,62 |
| divisor=2 | -1,43 | -1,35 | -1,95 | -2,55 |
| divisor=2.5 | -1,01 | -1,34 | -1,76 | -1,86 |
| divisor=3.5 | -0,52 | -1,34 | -1,55 | -1,06 |
| divisor=4 | -0,37 | -1,34 | -1,48 | -0,82 |
| multiplicador MAD=1 | -0,72 | -1,34 | -1,64 | -1,40 |
| multiplicador MAD=1.25 | -0,72 | -1,34 | -1,64 | -1,40 |
| multiplicador MAD=1.75 | -0,72 | -1,34 | -1,64 | -1,40 |
| multiplicador MAD=2 | -0,71 | -1,34 | -1,64 | -1,40 |
| peso MATTR=30% | -0,59 | -1,29 | -1,46 | -1,79 |
| peso MATTR=60% | -0,86 | -1,39 | -1,81 | -1,00 |

## Verificação

Recalculados 120 dias da execução oficial. Maior diferença em relação ao JSON oficial: 0.0000 ponto.

A escala proporcional domina a escala baseada no MAD na configuração oficial deste conjunto de dados.
Consequentemente, esses resultados não demonstram sensibilidade a ajustes pequenos do MAD.
As comparações são exploratórias e não constituem validação externa ou seleção de parâmetros ótimos.
