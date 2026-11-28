"""Preparação da avaliação; predição sem rótulos e avaliação posterior.
Usa Decimal dos scores exportados, Wilson e teste permutacional de postos por perfil.
"""
import argparse, json, math, random, statistics, hashlib
from decimal import Decimal
from pathlib import Path
from collections import defaultdict, Counter
from datetime import date,timedelta

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def number(x):
    if isinstance(x,bool) or not isinstance(x,(int,float,str)):raise ValueError('Valor ausente/inválido')
    n=Decimal(str(x))
    if not n.is_finite() or not 0<=n<=100:raise ValueError('Score/limiar fora de faixa')
    return n

def drops(rows,dim):
    grouped=defaultdict(lambda:defaultdict(list));seen=set()
    for x in rows:
        pid=x['userId'];period=x['period'];day=x.get('date','')
        if period not in ('baseline','reanalise') or x.get('evidenceCoverage')!=1:raise ValueError(f'Evidência/período inválido: {pid}')
        k=(pid,period,day if dim=='comunicacional' else '')
        if k in seen:raise ValueError(f'Score duplicado: {k}')
        seen.add(k);grouped[pid][period].append(number(x['score']))
        if dim=='comunicacional':
            dt=date.fromisoformat(day);start,end=(date(2026,5,4),date(2026,5,29)) if period=='baseline' else (date(2026,6,1),date(2026,6,12))
            if not start<=dt<=end or dt.weekday()>4:raise ValueError(f'Data inesperada: {day}')
    result={}
    for pid,p in grouped.items():
        n=(20,10) if dim=='comunicacional' else (1,1)
        if tuple(len(p[k]) for k in ('baseline','reanalise'))!=n:raise ValueError(f'Janela incompleta: {pid}')
        ref=sum(p['baseline'])/n[0];comp=sum(p['reanalise'])/n[1]
        result[pid]={'reference':str(ref),'comparison':str(comp),'drop':str(ref-comp)}
    if not result:raise ValueError('Sem perfis')
    return result

def threshold_calibration(rows):
    d=drops(rows,'comunicacional')
    if set(d)!={f'CAL{i:03}' for i in range(1,41)}:raise ValueError('Exige 40 IDs de calibração')
    return max(Decimal(0),sorted((Decimal(x['drop']) for x in d.values()),reverse=True)[1])

def predict(rows,dim,threshold):
    t=number(threshold);d=drops(rows,dim)
    return {p:{**x,'margin':str(Decimal(x['drop'])-t),'flag':Decimal(x['drop'])>t if dim=='comunicacional' else Decimal(x['drop'])>=t} for p,x in d.items()}

def wilson(k,n):
    if not n:return None
    p=k/n;z=1.959963984540054;den=1+z*z/n;center=(p+z*z/(2*n))/den;half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/den
    return {'n':n,'successes':k,'estimate':p,'ci95':[max(0,center-half),min(1,center+half)]}

def effect(a,b):
    return sum((x>y)-(x<y) for x in a for y in b)/(len(a)*len(b))

def rank_analysis(altered,stable,seed=20261128):
    if not altered or not stable:return None
    # H0: permutabilidade dos rótulos entre perfis; teste bilateral de U.
    observed=effect(altered,stable);rng=random.Random(seed);pooled=altered+stable;n=len(altered);extreme=0
    for _ in range(9999):
        z=pooled[:];rng.shuffle(z);extreme+=abs(effect(z[:n],z[n:]))>=abs(observed)-1e-12
    boot=sorted(effect(rng.choices(altered,k=len(altered)),rng.choices(stable,k=len(stable))) for _ in range(2000))
    return {'U_alterados':(observed+1)*len(altered)*len(stable)/2,'cliffs_delta_drop':observed,'p_permutation_two_sided':(extreme+1)/10000,'bootstrap_percentile_ci95':[boot[49],boot[1949]],'permutations':9999,'bootstrap_resamples':2000,'seed':seed}

def evaluate(pred,truth):
    if set(pred)!=set(truth):raise ValueError('IDs de predições e rótulos divergem')
    if any(not isinstance(v['altered'],bool) or (v['altered'] and not v.get('intensity')) for v in truth.values()):raise ValueError('Rótulo inválido')
    c=Counter();levels=defaultdict(list);a=[];b=[]
    for pid,x in pred.items():
        y=truth[pid];actual=y['altered'];flag=x['flag'];c[('T' if actual==flag else 'F')+('P' if flag else 'N')]+=1
        (a if actual else b).append(float(x['drop']))
        if actual:levels[y['intensity']].append(flag)
    tp,fn,fp,tn=[c[k] for k in ('TP','FN','FP','TN')]
    return {'matrix':{'TP':tp,'FN':fn,'FP':fp,'TN':tn},'sensitivity':wilson(tp,tp+fn),'specificity':wilson(tn,tn+fp),'detection_by_intensity':{k:wilson(sum(v),len(v)) for k,v in sorted(levels.items())},'distribution':{k:{'n':len(v),'mean':statistics.mean(v),'sd':statistics.stdev(v) if len(v)>1 else None,'median':statistics.median(v)} for k,v in [('altered',a),('stable',b)] if v},'rank_analysis_exploratory':rank_analysis(a,b)}

def main():
    p=argparse.ArgumentParser();s=p.add_subparsers(dest='cmd',required=True)
    c=s.add_parser('calibrar');c.add_argument('--scores',type=Path,required=True);c.add_argument('--saida',type=Path,required=True)
    c=s.add_parser('predizer');c.add_argument('--scores',type=Path,required=True);c.add_argument('--dimensao',choices=['comunicacional','profissional'],required=True);c.add_argument('--limiar',required=True);c.add_argument('--saida',type=Path,required=True)
    c=s.add_parser('avaliar');c.add_argument('--predicoes',type=Path,required=True);c.add_argument('--rotulos',type=Path,required=True);c.add_argument('--sha-predicoes',required=True);c.add_argument('--saida',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='calibrar':save(a.saida,{'threshold':str(threshold_calibration(load(a.scores))),'source_sha256':sha(a.scores),'n':40,'k':2,'rule':'>'})
    elif a.cmd=='predizer':save(a.saida,{'dimension':a.dimensao,'threshold':a.limiar,'source_sha256':sha(a.scores),'predictions':predict(load(a.scores),a.dimensao,a.limiar)})
    else:
        if sha(a.predicoes)!=a.sha_predicoes:raise ValueError('Predições divergentes do hash registrado antes da revelação')
        pred=load(a.predicoes)['predictions'];truth=load(a.rotulos)
        if any(i.startswith('TST') for i in pred):
            if set(pred)!={f'TST{i:03}' for i in range(1,41)} or sum(v['altered'] is True for v in truth.values())!=20:raise ValueError('Teste planejado exige 40 perfis e 20 alterados por dimensão')
        result=evaluate(pred,truth);save(a.saida,{'predictions_sha256':sha(a.predicoes),'labels_sha256':sha(a.rotulos),**result})
    print('SHA256',sha(a.saida))
if __name__=='__main__':main()
