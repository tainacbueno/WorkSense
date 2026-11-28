"""Validação privada e exportação sem rótulos. Nunca seleciona por score."""
import argparse
from datetime import datetime, time, timezone, timedelta
from statistics import mean
from pathlib import Path
from gerar_profissional_v1 import sha,write,WINDOWS,TZ
from validar_profissional_v1 import check
from preparar_experimento_v2 import verify_manifest, VERSION,require,load,IDS
import gerar_profissional_v2 as g

def validate(origin,out,mpath,comm_path,freeze_path):
    m=verify_manifest(mpath,comm_path,freeze_path);p=load(origin/'privado/plano.json');log=origin/'para_analise/trello_log.json'
    require(p.get('base')=='teste' and p.get('version')==VERSION and p['manifest_sha256']==sha(mpath) and p['freeze_sha256']==sha(freeze_path) and p['communication_plan_sha256']==sha(comm_path) and p['sha256_gerador']==sha(Path(g.__file__)), 'Proveniência divergente')
    require(p['seed']==m['professional_seed'] and p['profiles']=={i:v['professional_intensity'] for i,v in m['profiles'].items()},'Atribuição profissional divergente')
    require(p['sha256_log']==sha(log),'Hash do log divergente')
    board=load(log);require(board.get('id')=='board-profissional-teste','Quadro incorreto');board['id']='board-profissional-piloto'
    events,metrics,scores=check(board,p)
    # Conferência independente da duração do atraso e dos retornos de etapa.
    for period,users in metrics.items():
        cutoff=datetime.combine(datetime.fromisoformat(WINDOWS[period][1]).date(),time.max,tzinfo=TZ)
        for pid,data in users.items():
            rows=[r for r in p['cards'] if r['userId']==pid and r['period']==period]
            hours=[round((cutoff-datetime.fromisoformat(r['due'].replace('Z','+00:00'))).total_seconds()/3600,2) if r['open'] else r['delayHours'] for r in rows if r['open'] or r['delayHours']>0]
            expected=round(mean(hours),4) if hours else None
            metrics_p=data['professionalMetrics'];d=metrics_p['deadline'];q=metrics_p['quality']
            require(d['avgLateHours']==expected and d['lateCards']==len(hours),f'Duração de atraso divergente: {pid}/{period}')
            require(q['backwardWorkflowCards']==sum(r['quality'] in ('retorno','reabertura') and not r['open'] for r in rows),f'Retorno de etapa divergente: {pid}/{period}')
    require(len(scores)==80 and {x['userId'] for x in scores}==IDS and all(x['evidenceCoverage']==1 and x['score'] is not None for x in scores),'Evidência incompleta: interromper, sem excluir perfis')
    out.mkdir(parents=True,exist_ok=False)
    for name,data in [('trello_events_normalizados.json',events),('indicadores_profissional_periodos.json',metrics),('professional_period_scores.json',scores)]:write(out/name,data)
    write(out/'integridade.json',{'freeze_sha256':sha(freeze_path),'log_sha256':sha(log),'profiles':40,'cards':480,'scores':80,'files':{x.name:sha(x) for x in sorted(out.glob('*.json'))}})
    print(f'{len(events)} eventos; 80 scores; plano e indicadores conferidos.')
def main():
    p=argparse.ArgumentParser(description=__doc__);g.args_common(p);p.add_argument('--origem',type=Path,required=True);a=p.parse_args();validate(a.origem,a.saida,a.manifesto,a.plano_comunicacional,a.congelamento)
if __name__=='__main__':main()
