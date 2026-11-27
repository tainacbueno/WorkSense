# Sensibilidade da normalização linguística — WorkSense

**Configuração oficial:** sentimento 8/15; interação linguística 7/15;
pesos internos 35% comprimento, 45% MATTR e 20% sentenças.
Somente um parâmetro é modificado de cada vez.

As células com valores representam variações de médias de scores, em pontos.

## Baseline oficial → reanálise

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. comprimento=1 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. comprimento=3 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. comprimento=4 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. comprimento=5 | +0,07 | -4,07 | -0,68 | -4,94 |
| mín. comprimento=6 | +0,04 | -3,81 | -0,74 | -4,86 |
| mín. sentenças=0.15 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. sentenças=0.35 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. sentenças=0.45 | +0,09 | -4,27 | -0,68 | -4,70 |
| mín. sentenças=0.55 | +0,08 | -4,14 | -0,77 | -4,36 |
| mín. MATTR=0.04 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. MATTR=0.12 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. MATTR=0.16 | +0,10 | -4,35 | -0,62 | -5,04 |
| mín. MATTR=0.2 | +0,10 | -4,36 | -0,51 | -5,01 |
| escala proporcional=10% | +0,23 | -6,41 | -0,68 | -6,35 |
| escala proporcional=15% | +0,15 | -5,14 | -0,71 | -5,99 |
| escala proporcional=25% | +0,06 | -3,88 | -0,57 | -4,42 |
| escala proporcional=30% | +0,04 | -3,56 | -0,54 | -4,01 |
| divisor=2 | +0,19 | -5,53 | -0,76 | -6,28 |
| divisor=2.5 | +0,13 | -4,83 | -0,68 | -5,66 |
| divisor=3.5 | +0,07 | -4,01 | -0,59 | -4,60 |
| divisor=4 | +0,05 | -3,76 | -0,56 | -4,27 |
| multiplicador MAD=1 | +0,10 | -4,35 | -0,62 | -5,04 |
| multiplicador MAD=1.25 | +0,10 | -4,35 | -0,62 | -5,04 |
| multiplicador MAD=1.75 | +0,10 | -4,35 | -0,62 | -5,04 |
| multiplicador MAD=2 | +0,10 | -4,35 | -0,62 | -5,04 |
| peso MATTR=30% | +0,22 | -5,13 | +0,02 | -5,70 |
| peso MATTR=60% | -0,02 | -3,57 | -1,27 | -4,39 |

## Controle → reanálise

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. comprimento=1 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. comprimento=3 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. comprimento=4 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. comprimento=5 | -1,03 | -3,23 | +0,39 | -5,23 |
| mín. comprimento=6 | -0,94 | -2,96 | +0,28 | -5,20 |
| mín. sentenças=0.15 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. sentenças=0.35 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. sentenças=0.45 | -1,04 | -3,50 | +0,46 | -4,93 |
| mín. sentenças=0.55 | -1,08 | -3,45 | +0,38 | -4,62 |
| mín. MATTR=0.04 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. MATTR=0.12 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. MATTR=0.16 | -1,04 | -3,52 | +0,52 | -5,27 |
| mín. MATTR=0.2 | -1,03 | -3,52 | +0,61 | -5,21 |
| escala proporcional=10% | -1,76 | -5,62 | +0,26 | -6,77 |
| escala proporcional=15% | -1,27 | -4,26 | +0,65 | -6,13 |
| escala proporcional=25% | -0,92 | -3,08 | +0,44 | -4,70 |
| escala proporcional=30% | -0,83 | -2,79 | +0,40 | -4,31 |
| divisor=2 | -1,35 | -4,63 | +0,71 | -6,39 |
| divisor=2.5 | -1,16 | -3,96 | +0,60 | -5,84 |
| divisor=3.5 | -0,95 | -3,21 | +0,47 | -4,86 |
| divisor=4 | -0,89 | -2,97 | +0,43 | -4,55 |
| multiplicador MAD=1 | -1,04 | -3,52 | +0,52 | -5,27 |
| multiplicador MAD=1.25 | -1,04 | -3,52 | +0,52 | -5,27 |
| multiplicador MAD=1.75 | -1,04 | -3,52 | +0,52 | -5,27 |
| multiplicador MAD=2 | -1,06 | -3,52 | +0,52 | -5,27 |
| peso MATTR=30% | -1,05 | -4,13 | +1,20 | -5,72 |
| peso MATTR=60% | -1,04 | -2,92 | -0,16 | -4,81 |

## Referência → controle

| Cenário | A | B | C | D |
|---|---:|---:|---:|---:|
| Atual | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. comprimento=1 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. comprimento=3 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. comprimento=4 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. comprimento=5 | +0,43 | -0,14 | +0,04 | -0,62 |
| mín. comprimento=6 | +0,43 | -0,19 | -0,11 | -0,40 |
| mín. sentenças=0.15 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. sentenças=0.35 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. sentenças=0.45 | +0,40 | -0,08 | +0,19 | -0,81 |
| mín. sentenças=0.55 | +0,39 | -0,11 | +0,20 | -0,77 |
| mín. MATTR=0.04 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. MATTR=0.12 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. MATTR=0.16 | +0,42 | -0,07 | +0,20 | -0,85 |
| mín. MATTR=0.2 | +0,43 | -0,11 | +0,18 | -0,85 |
| escala proporcional=10% | +0,33 | +1,13 | +1,13 | -2,59 |
| escala proporcional=15% | +0,27 | +0,35 | +0,54 | -1,48 |
| escala proporcional=25% | +0,47 | -0,32 | -0,04 | -0,49 |
| escala proporcional=30% | +0,51 | -0,49 | -0,20 | -0,26 |
| divisor=2 | +0,28 | +0,56 | +0,80 | -1,73 |
| divisor=2.5 | +0,36 | +0,18 | +0,44 | -1,20 |
| divisor=3.5 | +0,45 | -0,25 | +0,03 | -0,59 |
| divisor=4 | +0,48 | -0,38 | -0,10 | -0,41 |
| multiplicador MAD=1 | +0,42 | -0,07 | +0,20 | -0,85 |
| multiplicador MAD=1.25 | +0,42 | -0,07 | +0,20 | -0,85 |
| multiplicador MAD=1.75 | +0,32 | -0,07 | +0,19 | -0,86 |
| multiplicador MAD=2 | +0,38 | -0,07 | +0,15 | -0,88 |
| peso MATTR=30% | +0,56 | -0,13 | +0,42 | -1,34 |
| peso MATTR=60% | +0,28 | -0,00 | -0,03 | -0,36 |

## Verificação

Recalculados 120 dias da execução oficial. Maior diferença em relação ao JSON oficial: 0.0000 ponto.

A escala proporcional domina a escala baseada no MAD na configuração oficial deste conjunto de dados.
Consequentemente, esses resultados não demonstram sensibilidade a ajustes pequenos do MAD.
As comparações são exploratórias e não constituem validação externa ou seleção de parâmetros ótimos.
