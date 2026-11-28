"""Cálculo exclusivo da comunicação, usando as funções da correção 10."""
import argparse
from pathlib import Path
from avaliar_sinalizacoes import load, save, sha, drops
from score_funcoes_originais import calculate_chat_score
from controle_comunicacional import expected_ids, require, DAYS, authorize

def get_chat_items_by_user_and_date(
    items_by_user: dict[str, list[dict]],
) -> dict[tuple[str, str], dict]:
    result = {}

    for user_id, items in items_by_user.items():
        for item in items:
            result[(user_id, item["date"])] = {
                "userId": user_id,
                **item,
            }

    return result

def get_lexical_items_by_user_and_date(
    items_by_user: dict[str, list[dict]],
) -> dict[tuple[str, str], dict]:
    result = {}
    for user_id, items in items_by_user.items():
        for item in items:
            if "dates" not in item:
                raise ValueError("Indicadores MATTR antigos: reexecute o pré-processamento.")
            for day in item["dates"]:
                key = (user_id, day)
                if key in result:
                    raise ValueError(f"Blocos MATTR sobrepostos: {key}")
                result[key] = {"userId": user_id, **item}
    return result

CHAT_PERIOD_WINDOWS = {
    "baseline": ("2026-05-01", "2026-05-30"),
    "reanalise": ("2026-05-31", "2026-06-14"),
}

def get_chat_period(date_value: str) -> str | None:
    for period_name, (start_date, end_date) in CHAT_PERIOD_WINDOWS.items():
        if start_date <= date_value <= end_date:
            return period_name
    return None

def calculate(indicators, base):
    basic=get_chat_items_by_user_and_date(indicators['basicLinguistic'])
    lex=get_lexical_items_by_user_and_date(indicators['lexicalDiversityByPeriod'])
    sent=get_chat_items_by_user_and_date(indicators['sentimentAnalysis'])
    sem=get_chat_items_by_user_and_date(indicators['semanticShift'])
    expected={(uid, day) for uid in expected_ids(base) for day in DAYS}
    for name, mapping in [('linguagem',basic),('MATTR',lex),('sentimento',sent),('semântica',sem)]:
        require(set(mapping)==expected, f'Dias ou IDs incompletos/inesperados: {name}')
    for name in ('basicLinguistic','sentimentAnalysis','semanticShift'):
        require(all(len(rows)==30 for rows in indicators[name].values()), f'Dias duplicados: {name}')
    scores=[]
    for key in sorted(expected):
        item=calculate_chat_score(basic[key],sent[key],sem[key],lex[key]).to_dict()
        item['period']=get_chat_period(key[1]); scores.append(item)
    drops(scores,'comunicacional')  # exige cobertura integral, 20/10 dias e scores válidos
    return scores

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',choices=['piloto','calibracao','teste'],required=True)
    p.add_argument('--indicadores',type=Path,required=True);p.add_argument('--saida',type=Path,required=True)
    p.add_argument('--execucao-pln',type=Path);p.add_argument('--congelamento',type=Path)
    a=p.parse_args();record=a.saida.with_name(a.saida.stem+'_execucao.json')
    require(not a.saida.exists() and not record.exists(),'Saída existente; não sobrescrever')
    if a.base!='piloto':
        require(a.execucao_pln and a.congelamento,'Exige registro de pré-processamento e congelamento')
        authorize(a.base,a.congelamento)
        info=load(a.execucao_pln)
        require(info['base']==a.base and info['output_sha256']==sha(a.indicadores) and info['freeze_sha256']==sha(a.congelamento) and info['declared_review_fixed'] is True,'Registro de PLN incompatível')
    rows=calculate(load(a.indicadores),a.base);save(a.saida,rows)
    save(record,{'base':a.base,'indicators_sha256':sha(a.indicadores),'scores_sha256':sha(a.saida),'pln_record_sha256':sha(a.execucao_pln) if a.execucao_pln else None,'freeze_sha256':sha(a.congelamento) if a.congelamento else None,'score_count':len(rows)})
    print(f'{len(rows)} scores; SHA256 {sha(a.saida)}')
if __name__=='__main__':main()
