"""Verifica invariância dos indicadores após excluir eventos posteriores às janelas.
Requer o script original teste_sensibilidade_profissional.py na pasta --entrada.
"""
import argparse
import importlib.util
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Scripts'))
from recalcular_correcao10 import load, HERE

ap=argparse.ArgumentParser(description=__doc__)
ap.add_argument('--entrada',type=Path,required=True)
args=ap.parse_args()
p=args.entrada
spec=importlib.util.spec_from_file_location(
    'sens_prof',
    Path(__file__).resolve().parent / 'teste_sensibilidade_profissional.py'
)
t=importlib.util.module_from_spec(spec); spec.loader.exec_module(t)
scope,metrics,events,stages=t.compile_cells(HERE/'extrairInfosLogTrello.ipynb',HERE/'calculosDeScore.ipynb',p/'trello_log_simulado_4perfis.json')
old=load(p/'professional_period_scores.json'); calc=t.calculate(scope,metrics)

for r in old:
    x=calc[(r['period'],t.MEMBERS[r['userId']])]
    assert x['score']==r['score'] and x['components']==r['components']

print(f'Profissional: {len(old)}/{len(old)} scores e componentes reproduzidos; eventos: {len(events)}')

for period,(start,end) in t.PERIODS.items():
    truncated=[e for e in events if e['date']<=end]
    m=scope['aggregate_trello_indicators_by_user'](truncated,start_date=start,end_date=end,workflow_intermediate_stages=stages)
    assert m==metrics[period]
    print(f'{period}: indicadores idênticos após excluir {len(events)-len(truncated)} eventos posteriores.')
