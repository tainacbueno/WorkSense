"""Valida plano e log sem usar scores como critério de aceitação."""
import argparse,json
from pathlib import Path
from gerar_profissional_v1 import plan,render,sha,write,WINDOWS,VERSION
import gerar_profissional_v1 as generator
from trello_funcoes_originais import extract_trello_events,aggregate_trello_indicators_by_user,infer_workflow_intermediate_stages
from score_funcoes_originais import calculate_professional_score

def check(board,manifest):
    rows=plan(manifest['seed'],list(manifest['profiles'].items()))
    if rows!=manifest['cards'] or render(rows)!=board:raise ValueError('Log ou plano diverge da geração determinística')
    events=extract_trello_events(board);stages=infer_workflow_intermediate_stages(board)
    metrics={p:aggregate_trello_indicators_by_user(events,start_date=s,end_date=e,workflow_intermediate_stages=stages) for p,(s,e) in WINDOWS.items()}
    scores=[]
    for p,users in metrics.items():
        if set(users)!=set(manifest['profiles']):raise ValueError('Perfis ausentes')
        for pid,data in users.items():
            planned=[x for x in rows if x['period']==p and x['userId']==pid];m=data['professionalMetrics'];d=m['deadline'];q=m['quality'];closed=[x for x in planned if not x['open']]
            expected={'deliveryEligibleCards':6,'deliveredCards':len(closed),'lateCompletedCards':sum(x['delayHours']>0 for x in closed),'overdueOpenCards':6-len(closed),'onTimeCards':sum(x['delayHours']==0 for x in closed)}
            if any(d[k]!=v for k,v in expected.items()):raise ValueError((pid,p,d,expected))
            if q['completedWithChecklist']!=len(closed) or q['completedWithIncompleteChecklist']!=sum(x['quality']=='checklist' for x in closed) or q['reworkCards']!=sum(x['quality'] in ('retorno','reabertura') for x in closed) or q['reopenedCards']!=sum(x['quality']=='reabertura' for x in closed):raise ValueError((pid,p,q))
            if m['workflowProgression']['evaluatedCards']!=len(closed) or m['workflowProgression']['workflowProgressionRate']!=1:raise ValueError('Fluxo divergente')
            scores.append({**calculate_professional_score({'userId':pid,**data}).to_dict(),'period':p})
    return events,metrics,scores

def main():
    p=argparse.ArgumentParser();p.add_argument('--origem',type=Path,required=True);p.add_argument('--saida',type=Path,required=True);a=p.parse_args()
    log=a.origem/'para_analise/trello_log.json'; manifest=json.loads((a.origem/'privado/plano.json').read_text(encoding='utf-8'))
    if manifest.get('base')!='piloto' or manifest.get('version')!=VERSION or sha(Path(generator.__file__))!=manifest['sha256_gerador']:raise ValueError('Versão do gerador divergente')
    if sha(log)!=manifest['sha256_log']:raise ValueError('Hash divergente')
    events,metrics,scores=check(json.loads(log.read_text(encoding='utf-8')),manifest)
    a.saida.mkdir(parents=True,exist_ok=False)
    for f,d in [('trello_events_normalizados.json',events),('indicadores_profissional_periodos.json',metrics),('professional_period_scores.json',scores)]:write(a.saida/f,d)
    print(f'{len(events)} eventos; {len(scores)} scores; plano e indicadores conferidos.')
if __name__=='__main__':main()
