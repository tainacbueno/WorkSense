#!/usr/bin/env python3
"""Análise de sensibilidade profissional WorkSense, sem editar a simulação.

Uso:
    python teste_sensibilidade_profissional.py \
      --trello trello_log_simulado_4perfis.json \
      --extrator 'extrairInfosLogTrello.ipynb' \
      --scores-notebook 'calculosDeScore.ipynb' \
      --oficial professional_period_scores.json

Execução independente usando o código efetivo dos notebooks de extração e score.
"""
from __future__ import annotations
import argparse
import csv
import json
import sys
import types
from pathlib import Path

PERIODS = {'baseline':('2026-05-01','2026-05-30'), 'reanalise':('2026-05-31','2026-06-14')}
BASE_WEIGHTS={'workflowProgressionScore':.25,'deadlineScore':.4,'qualityScore':.35}
MEMBERS={'member-perfil-a':'A','member-perfil-b':'B','member-perfil-c':'C','member-perfil-d':'D'}


def compile_cells(extraction_path:Path, score_path:Path, trello_path:Path):
    mod=types.ModuleType('_worksense_sensitivity')
    sys.modules[mod.__name__]=mod
    scope=mod.__dict__
    source=json.loads(extraction_path.read_text(encoding='utf-8'))
    for i in (2,6,7,8):
        code=''.join(source['cells'][i]['source'])
        if i==2:
            # Only replaces the notebook's fixed input path, not extraction or aggregation rules.
            code=code.replace('"../Logs/trello_log_simulado_4perfis.json"',repr(str(trello_path.resolve())))
        exec(compile(code, f'extraction_cell_{i}','exec'),scope)
    events=scope['extract_trello_events'](scope['trello_data'])
    stages=scope['infer_workflow_intermediate_stages'](scope['trello_data'])
    indicators={p:scope['aggregate_trello_indicators_by_user'](events,start_date=s,end_date=e,workflow_intermediate_stages=stages) for p,(s,e) in PERIODS.items()}
    score_source=json.loads(score_path.read_text(encoding='utf-8'))
    exec(compile(''.join(score_source['cells'][2]['source']),'score_cell_2','exec'),scope)
    return scope,indicators,events,stages


def calculate(scope, metrics, *, weights=None,late_hours=48):
    scope['PROFESSIONAL_SCORE_WEIGHTS']=(BASE_WEIGHTS if weights is None else weights).copy()
    scope['MAX_LATE_HOURS_FOR_SCORE']=float(late_hours)
    out={}
    for p,users in metrics.items():
        for uid,item in users.items():
            score=scope['calculate_professional_score']({'userId':uid,**item}).to_dict()
            out[(p,MEMBERS[uid])]=score
    return out


def deltas(result):
    return {k:round(result[('reanalise',k)]['score']-result[('baseline',k)]['score'],2) for k in ('A','B','C','D')}


def print_table(title,rows):
    print('\n'+title)
    print(f'{"Variante":<27} '+ ' '.join(f'{k:>9}' for k in ('A','B','C','D'))+'   C rean. D rean.')
    for label,result in rows:
        ds=deltas(result)
        print(f'{label:<27} '+' '.join(f'{ds[k]:>9.2f}' for k in ('A','B','C','D')) + f' {result[("reanalise","C")]["score"]:>8.2f} {result[("reanalise","D")]["score"]:>8.2f}')


def score_from_components(scope,metrics,deadline_weights=(.4,.4,.2),quality_weights=(.6,.4),late_hours=48,weights=None):
    """Varia subpesos internos, reproduzindo as funções oficiais para os demais itens.
    Apenas para as ablações de pesos internos, sem modificar os notebooks originais.
    """
    scope['MAX_LATE_HOURS_FOR_SCORE']=float(late_hours)
    w=weights or BASE_WEIGHTS
    out={}
    for p,users in metrics.items():
        for uid,item in users.items():
            mm=item['professionalMetrics']
            fw,_,_=scope['calculate_workflow_progression_score'](mm['workflowProgression'])
            d=mm['deadline'];q=mm['quality']
            delivery=None if d['deliveryRate'] is None else 100*d['deliveryRate']
            punctual=None if d['onTimeRate'] is None else 100*d['onTimeRate']
            if not d['deliveryEligibleCards']: severity=None
            elif d['lateCards']==0: severity=100.
            elif d['avgLateHours'] is None: severity=None
            else: severity=scope['linear_score'](d['avgLateHours'],0,float(late_hours),invert=True)
            ddl,_=scope['weighted_score']({'deliveryScore':(delivery,deadline_weights[0]),'deadlineOnTimeScore':(punctual,deadline_weights[1]),'deadlineLateSeverityScore':(severity,deadline_weights[2])})
            rew=None if q['reworkRate'] is None else 100*(1-q['reworkRate'])
            chk=None if q['checklistIssueRate'] is None else 100*(1-q['checklistIssueRate'])
            qual,_=scope['weighted_score']({'reworkScore':(rew,quality_weights[0]),'checklistScore':(chk,quality_weights[1])})
            tot,_=scope['weighted_score']({'workflowProgressionScore':(fw,w['workflowProgressionScore']),'deadlineScore':(ddl,w['deadlineScore']),'qualityScore':(qual,w['qualityScore'])})
            out[(p,MEMBERS[uid])]={'score':round(tot,2),'components':{'deadlineScore':round(ddl,2),'qualityScore':round(qual,2)}}
    return out


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--trello',type=Path,default=Path('trello_log_simulado_4perfis.json'))
    parser.add_argument('--extrator',type=Path,default=Path('extrairInfosLogTrello.ipynb'))
    parser.add_argument('--scores-notebook',type=Path,default=Path('calculosDeScore.ipynb'))
    parser.add_argument('--oficial',type=Path,default=Path('professional_period_scores.json'))
    parser.add_argument('--csv',type=Path,default=Path('sensibilidade_profissional_resultados.csv'))
    args=parser.parse_args()
    scope,metrics,events,stages=compile_cells(args.extrator,args.scores_notebook,args.trello)
    baseline=calculate(scope,metrics)
    official=json.loads(args.oficial.read_text(encoding='utf-8'))
    for item in official:
        key=(item['period'],MEMBERS[item['userId']])
        assert baseline[key]['score']==item['score'], f'Não reproduziu {key}'
        assert baseline[key]['components']==item['components'], f'Componentes não reproduzidos {key}'
    print(f'AUDITORIA: {len(official)}/{len(official)} scores e componentes reproduzidos; {len(events)} eventos; fluxo {stages}.')
    allrows=[]
    def add(test, label, obj):
        allrows.append((test,label,obj))
        return obj
    add('oficial','Atual (25/40/35;48h)',baseline)
    # Pesos externos: alterar prazos, redistribuir o restante na proporção original de 25:35.
    deadline_rows=[]
    for t in (.20,.30,.40,.50,.60):
        w={'workflowProgressionScore':(1-t)*.25/.60,'deadlineScore':t,'qualityScore':(1-t)*.35/.60}
        o=add('peso_prazo',f'Prazo {t:.0%}',calculate(scope,metrics,weights=w))
        deadline_rows.append((f'Prazos {t:.0%}',o))
    print_table('PESO EXTERNO DOS PRAZOS (outros proporcionais)',deadline_rows)
    # Ablation: component progression has no variation.
    progress_rows=[]
    for p in (.0,.15,.25,.35):
        w={'workflowProgressionScore':p,'deadlineScore':(1-p)*.40/.75,'qualityScore':(1-p)*.35/.75}
        o=add('peso_progressao',f'Progressão {p:.0%}',calculate(scope,metrics,weights=w))
        progress_rows.append((f'Progressão {p:.0%}',o))
    print_table('PESO EXTERNO PROGRESSÃO (outros proporcionais)',progress_rows)
    # Weight of quality, redistribute remaining deadline and workflow relative to baseline 25:40.
    quality_rows=[]
    for q in (.20,.35,.50):
        w={'workflowProgressionScore':(1-q)*.25/.65,'deadlineScore':(1-q)*.40/.65,'qualityScore':q}
        o=add('peso_qualidade',f'Qualidade {q:.0%}',calculate(scope,metrics,weights=w))
        quality_rows.append((f'Qualidade {q:.0%}',o))
    print_table('PESO EXTERNO QUALIDADE (outros proporcionais)',quality_rows)
    # Severity limit.
    hour_rows=[]
    for h in (12,24,36,48,72,96,144):
        o=add('limite_horas',f'{h} horas',calculate(scope,metrics,late_hours=h))
        hour_rows.append((f'{h} horas',o))
    print_table('LIMITE ATRASO (severidade)',hour_rows)
    # Deadline inner weights. Delivery and on-time equally share remainder.
    sub_deadline_rows=[]
    for late in (.10,.20,.30,.40):
        o=add('peso_severidade',f'Severidade {late:.0%}',score_from_components(scope,metrics,deadline_weights=((1-late)/2,(1-late)/2,late)))
        sub_deadline_rows.append((f'Severidade {late:.0%}',o))
    print_table('PESO INTERNO DA SEVERIDADE NO PRAZO',sub_deadline_rows)
    # Quality inner weights rework vs checklist.
    sub_quality_rows=[]
    for rework in (.4,.6,.8):
        o=add('peso_retrabalho',f'Retrabalho {rework:.0%}',score_from_components(scope,metrics,quality_weights=(rework,1-rework)))
        sub_quality_rows.append((f'Retrabalho {rework:.0%}',o))
    print_table('PESO INTERNO RETRABALHO NA QUALIDADE',sub_quality_rows)
    # Verification that independent recalc reproduces official.
    t=score_from_components(scope,metrics)
    assert all(t[key]['score']==baseline[key]['score'] for key in baseline)
    # Export long format.
    with args.csv.open('w',encoding='utf-8',newline='') as f:
        wr=csv.writer(f)
        wr.writerow(['teste','configuracao','perfil','baseline','reanalise','variacao','score_prazo_reanalise','score_qualidade_reanalise'])
        for kind,label,o in allrows:
            for profile in ('A','B','C','D'):
                wr.writerow([kind,label,profile,o[('baseline',profile)]['score'],o[('reanalise',profile)]['score'],round(o[('reanalise',profile)]['score']-o[('baseline',profile)]['score'],2),o[('reanalise',profile)]['components']['deadlineScore'],o[('reanalise',profile)]['components']['qualityScore']])
    print('\nCSV:',args.csv.absolute(),'n',len(allrows)*4)
    print('DADOS DE PRAZOS E QUALIDADE:')
    for p in ('baseline','reanalise'):
        for uid, item in metrics[p].items():
            print(p,MEMBERS[uid],json.dumps({k:item['professionalMetrics'][k] for k in ('deadline','quality')},ensure_ascii=False))

if __name__=='__main__': main()
