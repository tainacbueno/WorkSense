"""Calibração, predições cegas, revelação controlada e avaliação integrada."""
import argparse
from collections import Counter
from decimal import Decimal
from pathlib import Path
from avaliar_sinalizacoes import load,save,sha,number,predict,evaluate,threshold_calibration
from preparar_experimento_v2 import IDS,require,verify_freeze,verify_manifest,VERSION

DIMS=('comunicacional','profissional')

def prediction(scores,dim,freeze_path):
    f=verify_freeze(load(freeze_path)); rows=load(scores)
    pred=predict(rows,dim,f['thresholds'][dim]);require(set(pred)==IDS,'Exige 40 IDs TST, sem exclusões')
    return {'version':VERSION,'dimension':dim,'threshold':f['thresholds'][dim],'rule':f['rules'][dim],'freeze_sha256':sha(freeze_path),'source_sha256':sha(scores),'predictions':pred}

def verified_prediction(path,registered,dim,freeze_path):
    require(sha(path)==registered,'Hash de predições diverge do registro anterior à revelação')
    f=verify_freeze(load(freeze_path));p=load(path)
    require(p.get('version')==VERSION and p['dimension']==dim and p['freeze_sha256']==sha(freeze_path) and p['threshold']==f['thresholds'][dim] and p['rule']==f['rules'][dim] and set(p['predictions'])==IDS,'Predições incompatíveis com o teste congelado')
    t=number(p['threshold'])
    for x in p['predictions'].values():
        d=number(x['reference'])-number(x['comparison']);require(d==Decimal(x['drop']) and d-t==Decimal(x['margin']) and x['flag'] is (d>t if dim=='comunicacional' else d>=t),'Predição inconsistente')
    return p['predictions']

def truth_from_profiles(profiles):
    require(set(profiles)==IDS and Counter(v['group'] for v in profiles.values())==Counter({x:10 for x in 'ABCD'}),'Distribuição A–D inválida')
    for group in 'ABCD':
        count=Counter(v['professional_intensity'] for v in profiles.values() if v['group']==group)
        require(count==Counter({'estavel':10} if group in 'AB' else {'leve':5,'acentuada':5}),'Distribuição profissional inválida')
    return {dim:{i:{'altered':v['group'] in ('BD' if dim=='comunicacional' else 'CD'),'intensity':('unica' if v['group'] in 'BD' else None) if dim=='comunicacional' else (v['professional_intensity'] if v['group'] in 'CD' else None)} for i,v in profiles.items()} for dim in DIMS}

def reveal(mpath,comm_path,freeze_path,paths,hashes):
    for dim,p,h in zip(DIMS,paths,hashes):verified_prediction(p,h,dim,freeze_path)
    m=verify_manifest(mpath,comm_path,freeze_path);truth_from_profiles(m['profiles'])
    return {'version':VERSION,'freeze_sha256':sha(freeze_path),'manifest_sha256':sha(mpath),'prediction_hashes':dict(zip(DIMS,hashes)),'profiles':m['profiles']}

def assess(labels,freeze_path,paths,hashes):
    l=load(labels);require(l.get('version')==VERSION and l['freeze_sha256']==sha(freeze_path) and l['prediction_hashes']==dict(zip(DIMS,hashes)),'Rótulos incompatíveis com predições registradas')
    truth=truth_from_profiles(l['profiles']);results={};preds={}
    for dim,p,h in zip(DIMS,paths,hashes):
        preds[dim]=verified_prediction(p,h,dim,freeze_path);results[dim]=evaluate(preds[dim],truth[dim])
    joint={g:{'n':0,'ambas_corretas':0,'apenas_comunicacional_correta':0,'apenas_profissional_correta':0,'nenhuma_correta':0} for g in 'ABCD'}
    rows=[]
    for i,v in sorted(l['profiles'].items()):
        c=preds['comunicacional'][i]['flag']==truth['comunicacional'][i]['altered'];p=preds['profissional'][i]['flag']==truth['profissional'][i]['altered'];j=joint[v['group']];j['n']+=1;j['ambas_corretas' if c and p else 'apenas_comunicacional_correta' if c else 'apenas_profissional_correta' if p else 'nenhuma_correta']+=1
        rows.append({'userId':i,**v,**{d:{**preds[d][i],**truth[d][i]} for d in DIMS}})
    return {'version':VERSION,'freeze_sha256':sha(freeze_path),'labels_sha256':sha(labels),'prediction_hashes':dict(zip(DIMS,hashes)),'dimensions':results,'joint_by_group':joint,'profiles':rows}

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('calibrar');a.add_argument('--scores',type=Path,required=True);a.add_argument('--saida',type=Path,required=True)
    a=s.add_parser('predizer');a.add_argument('--scores',type=Path,required=True);a.add_argument('--dimensao',choices=DIMS,required=True);a.add_argument('--congelamento',type=Path,required=True);a.add_argument('--saida',type=Path,required=True)
    for cmd in ('revelar','avaliar'):
        a=s.add_parser(cmd);a.add_argument('--congelamento',type=Path,required=True);a.add_argument('--pred-com',type=Path,required=True);a.add_argument('--pred-prof',type=Path,required=True);a.add_argument('--sha-com',required=True);a.add_argument('--sha-prof',required=True);a.add_argument('--saida',type=Path,required=True)
        if cmd=='revelar':a.add_argument('--manifesto',type=Path,required=True);a.add_argument('--plano-comunicacional',type=Path,required=True);a.add_argument('--confirmar-hashes-registrados',action='store_true')
        else:a.add_argument('--rotulos',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='calibrar':r={'threshold':str(threshold_calibration(load(a.scores))),'source_sha256':sha(a.scores),'n':40,'k':2,'rule':'>'}
    elif a.cmd=='predizer':r=prediction(a.scores,a.dimensao,a.congelamento)
    else:
        paths=[a.pred_com,a.pred_prof];hashes=[a.sha_com,a.sha_prof]
        if a.cmd=='revelar':
            require(a.confirmar_hashes_registrados,'Registre hashes antes da revelação');r=reveal(a.manifesto,a.plano_comunicacional,a.congelamento,paths,hashes)
        else:r=assess(a.rotulos,a.congelamento,paths,hashes)
    save(a.saida,r);print('SHA256',sha(a.saida))
if __name__=='__main__':main()
