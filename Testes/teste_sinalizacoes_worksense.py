#!/usr/bin/env python3
"""Análise exploratória de regras de sinalização do TCC WorkSense.

Usa os scores do ciclo atual e as análises de sensibilidade já calculadas.
Não modifica a base, os scores, ou os parâmetros oficiais.

Exemplo na pasta dos arquivos:
    python teste_sinalizacoes_worksense.py \
      --chat chat_scores.json \
      --controle chat_scores_controle.json \
      --prof professional_period_scores.json \
      --prof-sens sensibilidade_profissional_resultados.csv \
      --chat-ind 'indicadores_chat.json' \
      --chat-ind-controle 'indicadores_chat_controle.json' \
      --chat-script teste_sensibilidade_linguistica.py \
      --saida saida_sinalizacoes

As grades de limiares são análise exploratória, não calibração validada.
"""
from __future__ import annotations
import argparse
import csv
import importlib.util
import json
from collections import defaultdict
from pathlib import Path
from statistics import mean

PROFILES='ABCD'
CHAT_USER={f'user-00{i}':p for i,p in enumerate(PROFILES,1)}
PROF_USER={f'member-perfil-{p.lower()}':p for p in PROFILES}


def load(path):
    with Path(path).open(encoding='utf8') as f: return json.load(f)


def chat_aggregates(records):
    daily=defaultdict(list)
    components=defaultdict(lambda: defaultdict(list))
    coverage=defaultdict(list)
    for row in records:
        p=CHAT_USER[row['userId']]; period=row['period']; key=(p,period)
        if row.get('score') is not None: daily[key].append(float(row['score']))
        if row.get('evidenceCoverage') is not None: coverage[key].append(float(row['evidenceCoverage']))
        for name,val in row.get('components',{}).items():
            if val is not None: components[key][name].append(float(val))
    return daily,components,coverage


def prof_aggregates(records):
    return {(PROF_USER[row['userId']],row['period']):row for row in records}


def flag(delta,threshold):
    # Queda no score; aumentos são relatados, mas não são rotulados como queda.
    return delta <= -threshold + 1e-9


def state(c,p):
    if c and p:return 'Ambas'
    if c:return 'Comunicacional'
    if p:return 'Profissional'
    return 'Nenhuma'


def write_csv(path, rows, names):
    with Path(path).open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=names);w.writeheader();w.writerows(rows)


def import_module(path):
    sp=importlib.util.spec_from_file_location('ws_linguistica_variantes',str(Path(path).resolve()))
    mod=importlib.util.module_from_spec(sp);sp.loader.exec_module(mod)
    return mod


def main():
    pa=argparse.ArgumentParser(description=__doc__)
    pa.add_argument('--chat',type=Path,default=Path('chat_scores.json'))
    pa.add_argument('--controle',type=Path,required=True,help='JSON de scores do experimento de controle (referencia, controle e reanalise)')
    pa.add_argument('--prof',type=Path,default=Path('professional_period_scores.json'))
    pa.add_argument('--prof-sens',type=Path,default=Path('sensibilidade_profissional_resultados.csv'))
    pa.add_argument('--chat-ind',type=Path,default=Path('indicadores_chat.json'))
    pa.add_argument('--chat-ind-controle',type=Path,required=True,help='JSON dos indicadores de chat da analise de controle')
    pa.add_argument('--chat-script',type=Path,default=Path('teste_sensibilidade_linguistica.py'))
    pa.add_argument('--limiar-chat',type=float,default=4.0)
    pa.add_argument('--limiar-prof',type=float,default=15.0)
    pa.add_argument('--saida',type=Path,default=Path('saida_sinalizacoes'))
    args=pa.parse_args();args.saida.mkdir(exist_ok=True,parents=True)

    chat, components, coverage=chat_aggregates(load(args.chat))
    prof=prof_aggregates(load(args.prof))
    record=[]; info={}
    for p in PROFILES:
        cb=mean(chat[(p,'baseline')]);cr=mean(chat[(p,'reanalise')]); cd=cr-cb
        pb=float(prof[(p,'baseline')]['score']); pr=float(prof[(p,'reanalise')]['score']);pd=pr-pb
        ct=sum(s<cb for s in chat[(p,'reanalise')])
        fchat=flag(cd,args.limiar_chat);fprof=flag(pd,args.limiar_prof)
        info[p]=dict(cb=cb,cr=cr,cd=cd,pb=pb,pr=pr,pd=pd,less=ct,fc=fchat,fp=fprof)
        record.append(dict(perfil=p,chat_baseline=round(cb,3),chat_reanalise=round(cr,3),delta_chat=round(cd,3),
                           prof_baseline=pb,prof_reanalise=pr,delta_prof=round(pd,3),
                           dias_chat_baseline=len(chat[(p,'baseline')]),dias_chat_reanalise=len(chat[(p,'reanalise')]),
                           dias_reanalise_abaixo_da_media_baseline=ct,
                           cobertura_chat_media=round(mean(coverage[(p,'reanalise')]),3),
                           cobertura_prof=prof[(p,'reanalise')]['evidenceCoverage'],
                           flag_chat=int(fchat),flag_prof=int(fprof),sinalizacao=state(fchat,fprof),
                           avisos_prof='; '.join(prof[(p,'reanalise')].get('warnings',[]))))
    write_csv(args.saida/'resultado_exemplo.csv',record,list(record[0]))

    # Matriz de limiares sem declarar qualquer ponto ótimo.
    grid=[]
    for tc in [1,2,3,4,5,6,7]:
        for tp in [5,10,15,18,20,25,30]:
            out={p:state(flag(info[p]['cd'],tc),flag(info[p]['pd'],tp)) for p in PROFILES}
            grid.append(dict(limiar_comunicacional=tc,limiar_profissional=tp,**out,
                             q_com=sum(flag(info[p]['cd'],tc) for p in PROFILES),
                             q_prof=sum(flag(info[p]['pd'],tp) for p in PROFILES)))
    write_csv(args.saida/'grade_limiares.csv',grid,list(grid[0]))

    # Controle interno: corte de 10 dias sem cenário de mudança planejada.
    dc,cc,cv=chat_aggregates(load(args.controle))
    ctrl=[]
    for p in PROFILES:
        ref=mean(dc[(p,'referencia')]);base=mean(dc[(p,'controle')]);rean=mean(dc[(p,'reanalise')]);
        ctrl.append(dict(perfil=p,referencia=round(ref,3),controle=round(base,3),reanalise=round(rean,3),
                         delta_controle_referencia=round(base-ref,3),delta_reanalise_controle=round(rean-base,3),
                         flag_falsa_no_controle=int(flag(base-ref,args.limiar_chat))))
    write_csv(args.saida/'controle_interno.csv',ctrl,list(ctrl[0]))

    # Sensibilidade dos parâmetros comunicacionais já reavaliados; variação de uma variável por vez.
    sens=import_module(args.chat_script)
    src=sens.prepare(sens.load(args.chat_ind),control=False)
    sc=[]; sc_controls=[]
    src_control=sens.prepare(sens.load(args.chat_ind_controle),control=True)
    for name,changes in sens.configs():
        _, means, _=sens.compute(src,**changes)
        _, means_control, _=sens.compute(src_control,**changes)
        for uid,p in sens.USER_NAMES.items():
            delta=means[(uid,'reanalise')]-means[(uid,'baseline')]
            sc.append(dict(dimensao='Comunicacional',parametro=name,perfil=p,delta=round(delta,4),
                           limiar=args.limiar_chat,sinaliza=int(flag(delta,args.limiar_chat))))
            d_control=means_control[(uid,'controle')]-means_control[(uid,'referencia')]
            sc_controls.append(dict(parametro=name,perfil=p,delta_referencia_controle=round(d_control,4),
                                    limiar=args.limiar_chat,flag_no_controle=int(flag(d_control,args.limiar_chat))))
    write_csv(args.saida/'sensibilidade_sinalizacao_comunicacional.csv',sc,list(sc[0]))
    write_csv(args.saida/'sensibilidade_sinalizacao_controle.csv',sc_controls,list(sc_controls[0]))

    # Profissional: variações calculadas no teste precedente.
    pc=[]
    with args.prof_sens.open(encoding='utf-8-sig',newline='') as f:
        for item in csv.DictReader(f):
            d=float(item['variacao'])
            pc.append(dict(dimensao='Profissional',parametro=item['configuracao'],familia=item['teste'],
                           perfil=item['perfil'],delta=d,limiar=args.limiar_prof,sinaliza=int(flag(d,args.limiar_prof))))
    write_csv(args.saida/'sensibilidade_sinalizacao_profissional.csv',pc,list(pc[0]))

    status_count=defaultdict(lambda: defaultdict(lambda:[0,0]))
    for t,rows in [('Comunicacional',sc),('Profissional',pc)]:
        for row in rows:
            v=status_count[t][row['perfil']];v[0]+=int(row['sinaliza']);v[1]+=1
    report=['# Regras de sinalização — teste exploratório do WorkSense','','## Critério demonstrativo',
            f'- Δ = média da reanálise menos média do baseline (chat) ou score por período (profissional).',
            f'- Sinalizar queda no ciclo mais recente se Δcom <= -{args.limiar_chat:g} pontos ou Δprof <= -{args.limiar_prof:g} pontos, por dimensão.',
            '- Esse é um exemplo exploratório de limiares, **não uma regra validada ou aprovada**.',
            '- O gestor visualizaria a variação, os componentes e os avisos técnicos; histórico de sinalizações anteriores apenas como observação, nunca como alerta cumulativo.','','## Resultado demonstrativo','','| Perfil | ΔCom | ΔProf | Sinalização |','|---|---:|---:|---|']
    for p in PROFILES:
        i=info[p];report.append(f"| {p} | {i['cd']:+.2f} | {i['pd']:+.2f} | {state(i['fc'],i['fp'])} |")
    report+=['','## Dependência dos limiares','','### Dimensão comunicacional','','| Limiar de queda (pontos) | Perfis sinalizados |','|---:|---|']
    for tc in [1,2,3,4,5,6,7]:
        ps=', '.join(p for p in PROFILES if flag(info[p]['cd'],tc)) or 'Nenhum'
        report.append(f'| {tc} | {ps} |')
    report+=['','### Dimensão profissional','','| Limiar de queda (pontos) | Perfis sinalizados |','|---:|---|']
    for tp in [5,10,15,18,20,25,30]:
        ps=', '.join(p for p in PROFILES if flag(info[p]['pd'],tp)) or 'Nenhum'
        report.append(f'| {tp} | {ps} |')
    report+=['','## Verificação de controle (componente comunicacional)','','| Perfil | Referência -> controle | Controle -> reanálise |','|---|---:|---:|']
    for r in ctrl:
        report.append(f"| {r['perfil']} | {r['delta_controle_referencia']:+.2f} | {r['delta_reanalise_controle']:+.2f} |")
    report+=['','## Sensibilidade das decisões aos parâmetros (limiares apenas demonstrativos)','','| Dimensão | Perfil | Número de variantes sinalizando / total |','|---|---|---:|']
    for dim in ('Comunicacional','Profissional'):
        for p in PROFILES:
            yes,total=status_count[dim][p]
            report.append(f'| {dim} | {p} | {yes}/{total} |')
    flags_controle=sum(row['flag_no_controle'] for row in sc_controls)
    report+=['',f'No controle interno, {flags_controle}/{len(sc_controls)} avaliações perfil-variante ultrapassaram o limiar comunicacional demonstrativo de {args.limiar_chat:g} pontos.',
      'Este número é específico do experimento e não representa uma taxa de falso positivo em produção.',
      '', '## Limitações',
        '- Os limiares foram explorados **depois** de conhecermos os scores e os perfis. A correspondência com os rótulos simulados não valida os limites para uso real.',
        '- O controle interno contém apenas uma divisão temporal e usa referência de dez dias úteis. Não fornece taxa de falso positivo populacional.',
        '- A simulação tem apenas quatro perfis, scores profissionais de A/B no teto (100) e progressão do workflow sem variação. Isso limita o estudo de alertas indevidos.',
        '- A regra demonstrativa sinaliza quedas. Crescimentos do score, mesmo grandes, não são avaliados como alteração aqui; uma regra de mudanças bidirecionais exigiria avaliação complementar.',
        '- Scores ausentes ou insuficiência de registros devem gerar estado "dados insuficientes", não uma pontuação zero nem "nenhuma alteração".',
        '- Avisos técnicos (como cartões vencidos abertos) são informações contextuais, não gatilhos automáticos adicionais neste teste.',
        '- Somente o último ciclo deve determinar a sinalização exibida. Eventual recorrência de sinalizações anteriores cabe no máximo em observação separada.',
        '']
    (args.saida/'relatorio.md').write_text('\n'.join(report),encoding='utf-8')
    print('\n'.join(report[:40]));print('\nSensitivity summary:')
    for dim in ('Comunicacional','Profissional'):
        print(dim, {p: '/'.join(map(str,status_count[dim][p])) for p in PROFILES})
    print('Arquivos em:',args.saida.resolve())

if __name__=='__main__': main()
