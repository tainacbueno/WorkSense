"""Executa os mesmos indicadores do notebook corrigido sobre qualquer base planejada."""
import argparse
import os
from pathlib import Path
from collections import Counter
from datetime import datetime
from avaliar_sinalizacoes import load,save,sha
from controle_comunicacional import expected_ids,require,DAYS,processing_environment

def validate_messages(rows,base):
    ids=expected_ids(base);counts=Counter();seen=set()
    require(isinstance(rows,list) and len(rows)==200*len(ids),'Quantidade de mensagens incompatível')
    for row in rows:
        require(set(row)=={'messageId','userId','userName','createdAt','text'},'Formato inesperado ou rótulo na entrada')
        uid=row['userId'];mid=row['messageId'];ts=datetime.fromisoformat(row['createdAt']);day=ts.date().isoformat()
        require(uid in ids and day in DAYS and ts.tzinfo is None and 8<=ts.hour<18,'ID, data ou horário incompatível')
        require(mid not in seen and isinstance(row['text'],str) and row['text'].strip(),'Mensagem vazia ou ID repetido')
        seen.add(mid);counts[uid,day]+=1
    require(set(counts)=={(uid,day) for uid in ids for day in DAYS} and all(4<=n<=10 for n in counts.values()),'Distribuição diária incompatível')
    require(all(sum(counts[uid,d] for d in DAYS)==200 for uid in ids),'Quantidade por perfil incompatível')
    return rows  # mantém a ordem original do arquivo validado

def model_identity(f):
    def config_info(model):
        config=getattr(model,'config',None)
        return {'name_or_path':getattr(config,'_name_or_path',None),'commit_hash':getattr(config,'_commit_hash',None)}
    return {'spacy':{'name':f.nlp.meta.get('name'),'version':f.nlp.meta.get('version'),'lang':f.nlp.meta.get('lang')},
            'sentiment':config_info(getattr(f.sentiment_analyzer,'model',None)),
            'semantic':config_info(getattr(f.semantic_model[0],'auto_model',None))}

def process(rows, expected_models=None):
    import pln_funcoes_originais as f
    identity=model_identity(f)
    if expected_models is not None:require(identity==expected_models,'Identidade dos modelos difere do piloto congelado')
    print('Linguagem e MATTR...',flush=True)
    results=f.extract_many_text_metrics(rows)
    basic=f.add_linguistic_baseline_reference(f.aggregate_by_day(results),baseline_start_date=f.BASELINE_START_DATE,baseline_end_date=f.BASELINE_END_DATE)
    lex=f.aggregate_lexical_diversity_by_period(results,period_windows=f.PERIOD_WINDOWS,window_size=f.MATTR_WINDOW_SIZE)
    print('Sentimento...',flush=True)
    sentiment=f.aggregate_sentiment_by_day(f.extract_many_sentiment_metrics(rows))
    print('Semântica (diagnóstico)...',flush=True)
    sem=f.calculate_semantic_shift(f.extract_daily_semantic_embeddings(rows),baseline_start_date=f.BASELINE_START_DATE,baseline_end_date=f.BASELINE_END_DATE)
    return {'basicLinguistic':f.group_by_user(basic),'lexicalDiversityByPeriod':f.group_by_user(lex),'sentimentAnalysis':f.group_by_user(sentiment),'semanticShift':f.group_by_user(sem)},identity

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--base',choices=['piloto','calibracao','teste'],required=True);p.add_argument('--mensagens',type=Path,required=True);p.add_argument('--saida',type=Path,required=True,help='Nova pasta para resultados');p.add_argument('--congelamento',type=Path);p.add_argument('--recibo',type=Path);p.add_argument('--confirmar-revisao-base',action='store_true')
    a=p.parse_args();require(not a.saida.exists() or not any(a.saida.iterdir()),'Pasta de saída não vazia')
    if a.base!='piloto':
        require(a.congelamento and a.recibo and a.confirmar_revisao_base,'Exige recibo, congelamento e revisão humana fixada antes da análise')
        receipt=load(a.recibo);require(receipt=={'base':a.base,'messages':8000,'profiles':40,'messages_sha256':sha(a.mensagens),'freeze_sha256':sha(a.congelamento)},'Recibo divergente')
    rows=validate_messages(load(a.mensagens),a.base);env=processing_environment(a.base,a.congelamento)
    if a.base!='piloto':
        os.environ['HF_HUB_OFFLINE']='1'
        os.environ['TRANSFORMERS_OFFLINE']='1'
    indicators,identity=process(rows,env.get('model_identity'))
    env['model_identity']=identity
    a.saida.mkdir(parents=True,exist_ok=True);path=a.saida/'indicadores_chat.json';save(path,indicators)
    save(a.saida/'execucao_pln.json',{'base':a.base,'environment':env,'input_sha256':sha(a.mensagens),'output_sha256':sha(path),'freeze_sha256':sha(a.congelamento) if a.congelamento else None,'declared_review_fixed':a.confirmar_revisao_base})
    print('SHA256',sha(path))
if __name__=='__main__':main()
