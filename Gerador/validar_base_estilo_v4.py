"""Valida dados e prepara revisão sem executar PLN ou consultar scores.
O relatório privado e os arquivos para revisão ficam separados. Não libera
uma base incompleta ou estruturalmente incompatível.
"""
import argparse
import hashlib
from collections import defaultdict
from pathlib import Path
import gerar_comunicacional_estilo_v4 as g


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(source):
    source = Path(source)
    plans = [source / n for n in ('plano_piloto.json', 'plano_privado.json') if (source / n).is_file()]
    if len(plans) != 1:
        raise ValueError('Esperado exatamente um plano privado ou de piloto.')
    plan = g.load(plans[0])
    if plan != g.make_plan(plan['base'], plan.get('private_assignment_seed')):
        raise ValueError('Plano não corresponde à versão, parâmetros ou sementes do gerador.')
    profiles = plan['profiles']
    if {p.name for p in source.iterdir() if p.is_dir()} != {p['id'] for p in profiles}:
        raise ValueError('Diretórios de perfis incompletos ou inesperados.')
    rows, warnings, distribution, attempts_count = [], [], [], 0
    for p in profiles:
        pid = p['id']; blocks = []
        if {x.name for x in (source/pid).iterdir() if x.is_dir()} != {f'bloco_{b:02}' for b in range(1,7)}:
            raise ValueError(f'{pid}: conjunto de blocos incompleto ou inesperado.')
        for b in range(6):
            directory = source/pid/f'bloco_{b+1:02}'
            accepted, invalid, attempts = g.audit_block(directory,p,b,blocks[-1] if blocks else None,blocks[0]['descricao_escrita'] if blocks else None)
            if accepted is None or not (directory/'mensagens.json').is_file():
                raise ValueError(f'{pid}: bloco {b+1} incompleto.')
            attempts_count += len(attempts)
            for f in attempts:
                rec = g.load(f)
                if 'response' not in rec and 'error' not in rec:
                    warnings.append(dict(type='tentativa_interrompida', profile=pid, block=b+1, file=str(f.relative_to(source))))
            for k, max_words in [('estado_rotina',120),('descricao_escrita',40)]:
                if len(accepted[k].split()) > max_words:
                    warnings.append(dict(type='memoria_acima_da_extensao_solicitada', profile=pid, block=b+1, field=k))
            blocks.append(accepted)
        expected = g.export_profile(p, blocks)
        if g.load(source/pid/'mensagens.json') != expected:
            raise ValueError(f'{pid}: mensagens exportadas não correspondem às primeiras respostas válidas.')
        rows.extend(expected)
        for period, days in [('referencia',p['days'][:20]),('comparacao',p['days'][20:])]:
            distribution.append(dict(profile=pid, period=period, active_days=len(days), messages=sum(d['count'] for d in days), min_daily=min(d['count'] for d in days), max_daily=max(d['count'] for d in days)))
    if len({r['messageId'] for r in rows}) != len(rows):
        raise ValueError('IDs globais duplicados.')
    # Igualdade literal, sem normalização ou limiar de similaridade escolhido após a geração.
    by_text = defaultdict(list)
    for r in rows:
        by_text[r['text']].append(dict(id=r['messageId'], userId=r['userId'], date=r['createdAt'][:10]))
    duplicates = [dict(text=t, occurrences=loc, scope='entre_perfis' if len({x['userId'] for x in loc})>1 else 'dentro_do_perfil') for t,loc in by_text.items() if len(loc)>1]
    alert_ids = {x['id'] for dup in duplicates for x in dup['occurrences']}
    # Alertas de duplicação acrescentam dias completos, não apenas a mensagem isolada.
    review_days = {p['id']:set(plan['review_plan']['profiles'][p['id']]['dates']) for p in profiles}
    uid_to_pid = {('pilot-'+p['id'] if p['id'].startswith('P') else p['id']):p['id'] for p in profiles}
    for r in rows:
        if r['messageId'] in alert_ids:
            review_days[uid_to_pid[r['userId']]].add(r['createdAt'][:10])
    sample = []
    for uid,pid in uid_to_pid.items():
        days = sorted(review_days[pid])
        records = [r for r in rows if r['userId']==uid and r['createdAt'][:10] in days]
        sample.append(dict(userId=uid, dates=days, messages=records,
            review_alert_message_ids=[r['messageId'] for r in records if r['messageId'] in alert_ids]))
    report = dict(valid=True, base=plan['base'], profiles=len(profiles), messages=len(rows), attempts=attempts_count,
                  distribution=distribution, warnings=warnings, duplicates=duplicates,
                  planned_review_messages=plan['review_plan']['message_count'],
                  actual_review_messages=sum(len(x['messages']) for x in sample),
                  source_sha256={f.relative_to(source).as_posix():sha(f) for f in sorted(source.rglob('*')) if f.is_file()})
    return plan,rows,sample,report


def write_outputs(source, destination):
    source,destination=Path(source).resolve(),Path(destination).resolve()
    if destination==source or source in destination.parents or destination in source.parents:
        raise ValueError('Use saída separada da pasta privada de origem (nem ancestral nem descendente).')
    if destination.exists() and any(destination.iterdir()):
        raise ValueError('Saída já existente; use nova pasta para preservar a auditoria anterior.')
    try:
        plan,rows,sample,report=validate(source)
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as e:
        g.dump(destination/'relatorio_privado'/'validacao.json',dict(valid=False,error=str(e)))
        raise
    private=destination/'relatorio_privado'; public=destination/'para_analise'; review=destination/'para_revisao'
    g.dump(public/'mensagens.json',rows)
    # A pasta de revisão contém somente dias, identificadores, textos e IDs de alertas.
    for entry in sample:
        uid=entry['userId']; g.dump(review/f'{uid}.json',entry)
        lines=[f'# Revisão — {uid}', '', 'Compare os períodos. Registre exemplos com os IDs. Não consulte scores, prompts ou rótulos.', '']
        if entry['review_alert_message_ids']:
            lines += ['Alertas de duplicação literal (revisar contexto, sem descarte automático): ' + ', '.join(entry['review_alert_message_ids']), '']
        last_period=None; last_date=None
        for r in entry['messages']:
            date=r['createdAt'][:10]; period='Referência' if date<'2026-05-31' else 'Comparação'
            if period!=last_period: lines+=['',f'## {period}']; last_period=period
            if date!=last_date: lines+=['',f'### {date}']; last_date=date
            lines += [f"- `{r['messageId']}` {r['createdAt'][11:16]} — {r['text'].replace(chr(10), ' ')}"]
        lines+=['','## Registro','', '- Revisor e data:', '- Adequação ao contexto e destinatário:', '- Continuidade temporal:', '- Plausibilidade:', '- Mudança percebida (recorrente / pontual / não percebida / inconclusiva):', '- Características, exemplos e contraevidências:', '- Alterações nas atividades relatadas:', '- Inconsistências e impacto:', '- Limites da avaliação:', '- Data de fixação da revisão:','']
        (review/f'{uid}.md').write_text('\n'.join(lines),encoding='utf-8')
    report['export_sha256']={f.relative_to(destination).as_posix():sha(f) for directory in (public,review) for f in sorted(directory.rglob('*')) if f.is_file()}
    report['validator_sha256']=sha(Path(__file__))
    g.dump(private/'validacao.json',report)
    return report


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origem',type=Path,required=True)
    parser.add_argument('--saida',type=Path,required=True)
    args=parser.parse_args()
    try: r=write_outputs(args.origem,args.saida)
    except (ValueError,KeyError,TypeError,AttributeError,OSError) as e:
        print('VALIDAÇÃO INTERROMPIDA:',e); return 1
    print(f"Validação estrutural: {r['profiles']} perfis, {r['messages']} mensagens, {r['attempts']} tentativas.")
    print(f"Revisão: {r['actual_review_messages']} mensagens; {len(r['duplicates'])} grupos de duplicações; {len(r['warnings'])} alertas técnicos.")
    print('Saída:',args.saida,'— revisão humana ainda pendente.')
    return 0

if __name__=='__main__':
    raise SystemExit(main())
