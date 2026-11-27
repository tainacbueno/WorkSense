"""Testes estruturais e diagnóstico parcial com indicadores originais.
"""
import json
import sys
from pathlib import Path
from collections import Counter, defaultdict
from statistics import mean

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'Scripts'))

from recalcular_correcao10 import notebook_scope, group_by_user

src=Path(sys.argv[1]) if len(sys.argv)>1 else Path('../Logs')
pre=notebook_scope('Pré-Processamento.ipynb',[2],skip_model=True)
sc=notebook_scope('calculosDeScore.ipynb',[2,3])

# Teste isolado com métricas artificiais: exclusão do dia e ausência de referência.
items=[{'userId':'u','date':f'2026-05-{i:02d}','basicLinguistic':{'avgWordsPerMessage':v,'avgSentencesPerMessage':v}} for i,v in [(1,10),(2,20),(3,100),(4,200)]]
r=pre.add_linguistic_baseline_reference(items,'2026-05-01','2026-05-03')

assert [x['basicLinguistic']['baselineReference']['avgWordsPerMessage']['median'] for x in r]==[60,55,15,20]
assert [x['basicLinguistic']['baselineReference']['avgWordsPerMessage']['sampleDays'] for x in r]==[2,2,2,3]
assert pre.add_linguistic_baseline_reference(items[:1],'2026-05-01','2026-05-03')[0]['basicLinguistic']['baselineReference']['avgWordsPerMessage']['median'] is None
assert pre.calculate_mattr(['a']*19) is None
assert pre.calculate_mattr(['a']*20)==.05

# Teste de partição com função de métrica instrumentada (não é resultado de PLN).
original=pre._lexical_corpus_metrics
calls=[]

def instrument(items,window):
    days={pre.get_date(i['createdAt']) for i in items}; calls.append(days)
    return {'lexicalDiversityMattr': .9 if days else None,'totalLemmas':20*len(days),'mattrWindowCount':max(20*len(days)-19,0)}

pre._lexical_corpus_metrics=instrument
messages=[{'userId':'u','createdAt':f'2026-05-{i:02d}T10:00:00','text':str(i)} for i in range(1,16)]
blocks=pre.aggregate_lexical_diversity_by_period(messages,{'baseline':('2026-05-01','2026-05-10'),'reanalise':('2026-05-11','2026-05-15')})

assert [b['referenceSampleDays'] for b in blocks]==[5,5,10]
assert len(blocks)==3

for i,b in enumerate(blocks):
    assert set(b['dates'])==calls[2*i]
    assert set(b['referenceDates'])==calls[2*i+1]
    assert not set(b['dates']) & set(b['referenceDates'])

lookup=sc.get_lexical_items_by_user_and_date(group_by_user(blocks))

assert len(lookup)==15 and lookup['u','2026-05-07']['startDate']=='2026-05-06'

pre._lexical_corpus_metrics=original

print('Testes estruturais: OK (LOO, partição, referências disjuntas, lookup e MATTR mínima).')

# Reproduz cálculo anterior pelo código efetivo e isola a mudança LOO.
j = json.loads((src/'indicadores_chat.json').read_text(encoding='utf-8'))
old = json.loads((src/'chat_scores.json').read_text(encoding='utf-8'))

basic=sc.get_chat_items_by_user_and_date(j['basicLinguistic']);sent=sc.get_chat_items_by_user_and_date(j['sentimentAnalysis']);sem=sc.get_chat_items_by_user_and_date(j['semanticShift']);lex={(u,i['period']):i for u,items in j['lexicalDiversityByPeriod'].items() for i in items}

newbasic=sc.get_chat_items_by_user_and_date(group_by_user(pre.add_linguistic_baseline_reference(list(basic.values()),'2026-05-01','2026-05-30')))

old_means=defaultdict(list);new_means=defaultdict(list)

for r in old:
    key=(r['userId'],r['date']); group=(r['userId'],r['period']); l=lex[group]
    old_calc=sc.calculate_chat_score(basic[key],sent[key],sem[key],l).to_dict()

    assert old_calc['score']==r['score'],(key,old_calc['score'],r['score'])
    assert old_calc['components']==r['components'],key

    if r['period']=='baseline':
        assert r['components']['lexicalDiversityMattrPatternScore']==100
        assert all(v['sampleDays']==19 for v in newbasic[key]['basicLinguistic']['baselineReference'].values())
    else: assert newbasic[key]==basic[key]
    
    new=sc.calculate_chat_score(newbasic[key],sent[key],sem[key],l).to_dict()
    old_means[group].append(r['score']); new_means[group].append(new['score'])

print(f'{len(old)}/{len(old)} scores e componentes anteriores reproduzidos.')
print('Diagnóstico PARCIAL: apenas LOO palavras/sentenças, MATTR antiga mantida.')
print('Perfil | Baseline anterior | Baseline LOO | Reanálise (inalterada) | Delta anterior | Delta parcial')

for u in sorted({k[0] for k in old_means}):
    b,r=(u,'baseline'),(u,'reanalise'); a=mean(old_means[b]); c=mean(new_means[b]); z=mean(old_means[r]); assert new_means[r]==old_means[r]
    print(f'{u} | {a:.4f} | {c:.4f} | {z:.4f} | {z-a:+.4f} | {z-c:+.4f}')
