"""Recalcula linguagem a partir da base original e reutiliza sentimento/semântica salvos.
Execute com --entrada apontando para Logs; não sobrescreve os arquivos originais.
Requer spaCy e o mesmo pt_core_news_sm utilizado na execução original.
"""
import argparse
import json
import types
import sys
from pathlib import Path
from collections import defaultdict
from statistics import mean

HERE = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def notebook_scope(name, cells, *, skip_model=False):
    mod = types.ModuleType('_ws_' + name.split('.')[0])
    sys.modules[mod.__name__] = mod
    for i in cells:
        code = ''.join(load(HERE / name)['cells'][i]['source'])
        if skip_model:
            code = code.replace('nlp = spacy.load("pt_core_news_sm")', 'nlp = None')
        exec(compile(code, f'{name}:{i}', 'exec'), mod.__dict__)
    return mod


def group_by_user(rows):
    groups = defaultdict(list)
    for row in rows:
        groups[row['userId']].append({k: v for k, v in row.items() if k != 'userId'})
    return dict(groups)


def compute_scores(indicators, scorer, periods):
    scorer.CHAT_PERIOD_WINDOWS = periods
    basic = scorer.get_chat_items_by_user_and_date(indicators['basicLinguistic'])
    sentiment = scorer.get_chat_items_by_user_and_date(indicators['sentimentAnalysis'])
    semantic = scorer.get_chat_items_by_user_and_date(indicators['semanticShift'])
    lexical = scorer.get_lexical_items_by_user_and_date(indicators['lexicalDiversityByPeriod'])
    keys = sorted(set(basic) | set(sentiment))
    rows = []
    for key in keys:
        period = scorer.get_chat_period(key[1])
        if period is None:
            continue
        if key not in lexical and key in basic:
            raise ValueError(f'Bloco lexical ausente: {key}')
        result = scorer.calculate_chat_score(basic.get(key), sentiment.get(key), semantic.get(key), lexical.get(key)).to_dict()
        result['period'] = period
        rows.append(result)
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--entrada', type=Path, required=True)
    ap.add_argument('--saida', type=Path, required=True)
    args = ap.parse_args()
    if args.entrada.resolve() == args.saida.resolve():
        ap.error('Use uma pasta de saída distinta da entrada.')
    pre = notebook_scope('Pré-Processamento.ipynb', [2])
    scorer = notebook_scope('calculosDeScore.ipynb', [2,3])
    messages = load(args.entrada / 'mensagens_simuladas_4perfis_v2.json')
    old = load(args.entrada / 'indicadores_chat.json')
    old_scores = load(args.entrada / 'chat_scores.json')
    results = pre.extract_many_text_metrics(messages)
    daily = pre.aggregate_by_day(results)
    # Detecta diferenças de versão do modelo ou de dados antes de reutilizar as saídas.
    raw_daily = group_by_user(daily)
    old_daily = {u: [{**x, 'basicLinguistic': {k:v for k,v in x['basicLinguistic'].items() if k != 'baselineReference'}} for x in items] for u,items in old['basicLinguistic'].items()}
    if raw_daily != old_daily:
        raise ValueError('Indicadores diários originais não reproduzidos. Confira modelo e base.')
    for user, items in old['lexicalDiversityByPeriod'].items():
        for item in items:
            corpus = [r for r in results if r['userId']==user and item['startDate'] <= pre.get_date(r['createdAt']) <= item['endDate']]
            metrics = pre._lexical_corpus_metrics(corpus, pre.MATTR_WINDOW_SIZE)
            if any(metrics[k]!=item[k] for k in metrics):
                raise ValueError(f'MATTR original não reproduzida: {user}, {item["period"]}. Confira o modelo spaCy.')
    control = {'referencia':('2026-05-04','2026-05-15'), 'controle':('2026-05-18','2026-05-29'), 'reanalise':('2026-06-01','2026-06-12')}
    args.saida.mkdir(parents=True,exist_ok=True)
    all_scores = {}
    for suffix, periods, baseline in [('',pre.PERIOD_WINDOWS,'baseline'),('_controle',control,'referencia')]:
        start,end=periods[baseline]
        indicators = {**old, 'basicLinguistic':group_by_user(pre.add_linguistic_baseline_reference(daily,start,end)), 'lexicalDiversityByPeriod':group_by_user(pre.aggregate_lexical_diversity_by_period(results,periods,baseline_period_name=baseline))}
        scores=compute_scores(indicators,scorer,periods)
        for row in scores:
            if row['components']['sentimentScore'] is None or row['components']['lexicalDiversityMattrPatternScore'] is None:
                raise ValueError(f'Componente ausente: {row["userId"]}, {row["date"]}')
        for name,data in [('indicadores_chat',indicators),('chat_scores',scores)]:
            (args.saida / f'{name}{suffix}.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
        all_scores[suffix]=scores
    def summarize(rows):
        groups=defaultdict(list)
        for r in rows: groups[(r['userId'],r['period'])].append(r['score'])
        return {k:mean(v) for k,v in groups.items()}
    original=summarize(old_scores); new=summarize(all_scores[''])
    for user in sorted({k[0] for k in new}):
        a,b=(user,'baseline'),(user,'reanalise')
        print(user, f'Antes: {original[b]-original[a]:+.4f}; depois: {new[b]-new[a]:+.4f}')
    print('Modelo spaCy:',pre.nlp.meta.get('version'))
    print('Atenção: no controle, semântica diagnóstica reutilizada do baseline oficial; não integra o score.')


if __name__=='__main__':
    main()
