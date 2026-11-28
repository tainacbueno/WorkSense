"""Controle de calibração e verificação do congelamento integrado existente."""
import argparse
from datetime import date,timedelta
from pathlib import Path
import sys, platform, importlib.metadata as md
from avaliar_sinalizacoes import load,save,sha
import preparar_experimento_v2 as integrated
from preparar_experimento_v2 import require,tagged_files,verify_freeze,relative

ROOT=Path(__file__).resolve().parent.parent
DAYS=[(date(2026,5,4)+timedelta(days=7*b+d)).isoformat() for b in range(6) for d in range(5)]
CORE=['gerar_comunicacional_estilo_v4.py','validar_base_estilo_v4.py','gerar_comunicacional_definitivo.py','controle_comunicacional.py','validar_base_comunicacional_definitiva.py','pln_funcoes_originais.py','preprocessar_comunicacional.py','calcular_score_comunicacional.py','avaliar_sinalizacoes.py','avaliar_sinalizacoes_v2.py','preparar_experimento_v2.py','score_funcoes_originais.py','testar_gerador_estilo_v4.py','testar_pipeline_comunicacional.py']
GENERATOR='Gerador/gerar_comunicacional_estilo_v4.py'
PROTOCOL='docs/protocolo_pipeline_comunicacional.md'
PACKAGES=['spacy','pt_core_news_sm','pysentimiento','sentence-transformers','transformers','torch','numpy','scikit-learn','tokenizers','huggingface-hub','tzdata']

def expected_ids(base):
    if base=='piloto':return {f'pilot-P{i:02}' for i in range(7,11)}
    require(base in ('calibracao','teste'),'Base inválida')
    prefix='CAL' if base=='calibracao' else 'TST'
    return {f'{prefix}{i:03}' for i in range(1,41)}

def environment():
    packages={}
    for name in PACKAGES:
        try:packages[name]=md.version(name)
        except md.PackageNotFoundError:packages[name]=None
    require(all(packages[x] is not None for x in PACKAGES if x!='tzdata'),'Dependências de PLN ausentes: '+', '.join(x for x,v in packages.items() if v is None and x!='tzdata'))
    return {'python':sys.version,'platform':platform.platform(),'packages':packages,'models':{'spacy':'pt_core_news_sm','sentiment':'pysentimiento task=sentiment lang=pt','semantic':'paraphrase-multilingual-MiniLM-L12-v2'}}

def freeze_calibration(tag,review,env,extra,confirmed):
    require(confirmed,'Revisão V4 deve estar concluída e decisão de manutenção documentada antes da calibração')
    require(review.is_file() and review.stat().st_size>0,'Registro da revisão ausente')
    record=load(env);require('model_identity' in record and {k:v for k,v in record.items() if k!='model_identity'}==environment(),'Ambiente diferente do registro ou incompleto')
    paths=[ROOT/'Gerador'/x for x in CORE]+[ROOT/PROTOCOL,review,env,*extra]
    commit,files=tagged_files(tag,paths)
    return {'stage':'calibracao','version':'pipeline_comunicacional_v1','tag':tag,'commit':commit,'files':files,'review':relative(review),'environment':relative(env),'confirmed_review':True}

def verify_calibration(f):
    require(f.get('stage')=='calibracao' and f.get('version')=='pipeline_comunicacional_v1' and f.get('confirmed_review') is True,'Congelamento de calibração inválido')
    required={f'Gerador/{x}' for x in CORE}|{PROTOCOL,f['review'],f['environment']}
    require(required<=set(f['files']),'Arquivos da calibração ausentes')
    commit,files=tagged_files(f['tag'],[ROOT/x for x in f['files']]);require(commit==f['commit'] and files==f['files'],'Congelamento de calibração divergente')
    return f

def authorize(base,path):
    f=load(path)
    if base=='calibracao':return verify_calibration(f)
    require(base=='teste','Base oficial inválida')
    f=verify_freeze(f)
    require(f['communication_generator']==GENERATOR,'Use a V4 original como fonte do plano no congelamento integrado')
    records=[p for p in f['files'] if p.endswith('/congelamento_calibracao.json') or p=='congelamento_calibracao.json']
    require(len(records)==1,'Inclua exatamente um congelamento_calibracao.json no congelamento integrado')
    cal=verify_calibration(load(ROOT/records[0]))
    require(all(f['files'].get(k)==v for k,v in cal['files'].items()),'Método da calibração não foi integralmente preservado no congelamento integrado')
    score_path=Path(f['calibration_scores']);record_path=score_path.with_name(score_path.stem+'_execucao.json').as_posix()
    require(record_path in f['files'],'Registro de cálculo da calibração ausente do congelamento')
    record=load(ROOT/record_path)
    require(record['base']=='calibracao' and record['scores_sha256']==f['files'][f['calibration_scores']] and record['score_count']==1200 and record['freeze_sha256']==f['files'][records[0]],'Registro de scores CAL incompatível')
    require(record['indicators_sha256'] in f['files'].values(),'Indicadores CAL ausentes do congelamento')
    pln_records=[k for k,v in f['files'].items() if v==record['pln_record_sha256'] and Path(k).name=='execucao_pln.json']
    require(len(pln_records)==1,'Registro de PLN da calibração ausente ou ambíguo')
    pln=load(ROOT/pln_records[0]);require(pln['base']=='calibracao' and pln['output_sha256']==record['indicators_sha256'] and pln['freeze_sha256']==record['freeze_sha256'] and pln['declared_review_fixed'] is True and pln['environment']==load(ROOT/cal['environment']),'Registro de PLN CAL incompatível')
    require(pln['input_sha256'] in f['files'].values(),'Mensagens CAL ausentes do congelamento')
    return f

def processing_environment(base,freeze):
    env=environment()
    if base!='piloto':
        f=authorize(base,freeze)
        if base=='teste':f=load(ROOT/next(p for p in f['files'] if p.endswith('/congelamento_calibracao.json') or p=='congelamento_calibracao.json'))
        record=load(ROOT/f['environment']);require(env=={k:v for k,v in record.items() if k!='model_identity'},'Ambiente de PLN difere da calibração');env=record
    return env

def main():
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='cmd',required=True)
    a=s.add_parser('ambiente');a.add_argument('--saida',type=Path,required=True);a.add_argument('--execucao-piloto',type=Path,required=True)
    a=s.add_parser('congelar-calibracao');a.add_argument('--tag',required=True);a.add_argument('--revisao',type=Path,required=True);a.add_argument('--ambiente',type=Path,required=True);a.add_argument('--arquivos-metodo',nargs='*',type=Path,default=[]);a.add_argument('--confirmar-revisao-v4',action='store_true');a.add_argument('--saida',type=Path,required=True)
    a=p.parse_args()
    if a.cmd=='ambiente':
        pilot=load(a.execucao_piloto);require(pilot['base']=='piloto','Registro deve pertencer ao piloto V4')
        result=pilot['environment'];require('model_identity' in result and {k:v for k,v in result.items() if k!='model_identity'}==environment(),'Ambiente divergente do piloto')
    else:result=freeze_calibration(a.tag,a.revisao,a.ambiente,a.arquivos_metodo,a.confirmar_revisao_v4)
    save(a.saida,result);print('SHA256',sha(a.saida))
if __name__=='__main__':main()
