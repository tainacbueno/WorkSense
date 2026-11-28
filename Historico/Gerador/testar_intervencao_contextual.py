"""Piloto exploratório pareado: P03, duas ramificações, apenas blocos 5 e 6.
Não altera o gerador candidato nem os dados originais.
"""
import argparse
import hashlib
import importlib.metadata
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import gerar_comunicacional as g

HERE = Path(__file__).resolve().parent
SOURCE = HERE / 'piloto' / 'condicao_unica'
OUT = HERE / 'piloto' / 'intervencao_contextual'
CONDITIONS = ('estavel', 'alterada')
# Posições fixadas antes da geração; o contexto concreto fica a cargo do modelo.
OPPORTUNITIES = {
    4: [(1, 2, 'Uma sugestão do assistente não resolveu a dúvida ou necessidade.'),
        (3, 3, 'O assistente pediu uma informação já fornecida.'),
        (5, 2, 'O assistente respondeu com detalhes além dos necessários.')],
    5: [(1, 2, 'O assistente interpretou incorretamente parte da solicitação.'),
        (3, 3, 'Uma sugestão do assistente não resolveu a dúvida ou necessidade.'),
        (5, 2, 'O assistente pediu uma informação já fornecida.')],
}
COMMON = '''OPORTUNIDADES DE INTERAÇÃO NESTE BLOCO
As situações abaixo ocorrem durante conversas sobre demandas compatíveis com a rotina. Elas são oportunidades de interação, não novos problemas operacionais. Na posição indicada, escreva uma mensagem do colaborador que reaja à situação. A mensagem imediatamente anterior do mesmo dia deve dar contexto plausível à conversa. Imagine a resposta intermediária do assistente, mas não a inclua no JSON. Não anuncie o cenário, nem escreva rótulos, explicações externas ou falas do assistente. Não é necessário resolver a demanda nessa interação. As demais mensagens seguem a rotina, com liberdade para outras interações e reações naturais. A reação deve seguir as orientações comportamentais aplicáveis a esta etapa, sem impor tamanho, palavras ou pontuação específicos. Preserve a coerência temporal e não reinicie tarefas concluídas sem motivo.'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def prepare(source):
    plan = g.load(source / 'plano_piloto.json')
    if plan['script_sha256'] != sha(Path(g.__file__)):
        raise ValueError('O hash do gerar_comunicacional.py difere do registrado no piloto original.')
    profile = next(p for p in plan['profiles'] if p['id'] == 'P03')
    if profile != next(p for p in g.make_plan()['profiles'] if p['id'] == 'P03'):
        raise ValueError('Planejamento de P03 difere do original.')
    blocks, hashes = [], {}
    for b in range(4):
        directory = source / 'P03' / f'bloco_{b+1:02}'
        path = directory / 'mensagens.json'
        obj = g.load(path)
        accepted = []
        for f in sorted(directory.glob('tentativa_*.json')):
            rec = g.load(f)
            if rec.get('validation', {}).get('valid') is True:
                accepted.append(g.parse_response(rec['response'], profile['days'][b*5:b*5+5]))
                hashes[str(f.relative_to(source))] = sha(f)
        if accepted != [obj]:
            raise ValueError(f'Bloco {b+1}: memória ou mensagens não correspondem à resposta aceita.')
        hashes[str(path.relative_to(source))] = sha(path)
        blocks.append(obj)
    for b, opportunities in OPPORTUNITIES.items():
        for day, pos, _ in opportunities:
            if not 2 <= pos <= profile['days'][b*5+day-1]['count']:
                raise ValueError('Posição de oportunidade incompatível com o plano.')
    manifest = {'purpose': 'piloto_exploratorio_pareado', 'source_plan_sha256': sha(source/'plano_piloto.json'),
                'source_files_sha256': hashes, 'generator_sha256': sha(Path(g.__file__)),
                'test_script_sha256': sha(Path(__file__)), 'profile': profile,
                'conditions': list(CONDITIONS), 'opportunities': {str(b+1): [{'day':d,'message_position':p,'situation':s} for d,p,s in items] for b,items in OPPORTUNITIES.items()},
                'parameters': g.PARAMS, 'seed_policy': 'Mesma semente nominal por bloco e índice de tentativa nas duas condições.',
                'execution_order': ['B5 estavel','B5 alterada','B6 estavel','B6 alterada']}
    return profile, blocks, manifest


def make_request(profile, condition, b, previous, style, invalid):
    req = g.make_request(dict(profile, condition=condition), b, previous, invalid, style)
    slots = '\n'.join(f'Dia {d}, mensagem {p}: {s}' for d,p,s in OPPORTUNITIES[b])
    common = COMMON + '\n' + slots + '\n'
    marker = '\nDISTRIBUIÇÃO DAS MENSAGENS\n'
    text = req['messages'][0]['content']
    if text.count(marker) != 1:
        raise ValueError('Marcador de prompt inesperado.')
    req['messages'][0]['content'] = text.replace(marker, '\n' + common + marker)
    # Namespace específico do piloto, sem reutilizar as sementes dos testes anteriores.
    req['seed'] = g.seed('intervencao_contextual', profile['id'], b, invalid)
    return req


def generate(client, limiter, profile, condition, b, previous, style, out, status_error, connection_error):
    directory = out / condition / f'bloco_{b+1:02}'
    directory.mkdir(parents=True, exist_ok=True)
    days = profile['days'][b*5:b*5+5]
    attempts = sorted(directory.glob('tentativa_*.json'))
    invalid = 0
    for path in attempts:
        record = g.load(path)
        expected = make_request(profile, condition, b, previous, style, invalid)
        if record['request'] != expected:
            raise RuntimeError(f'Requisição anterior incompatível: {path}')
        if 'response' not in record:
            continue
        try:
            obj = g.parse_response(record['response'], days)
        except ValueError:
            invalid += 1
            continue
        g.dump(directory/'mensagens.json', obj)
        print(f'{condition} B{b+1}: resposta existente reutilizada.', flush=True)
        return obj
    retries = 0
    prior_wait = 0.0
    while invalid < g.MAX_INVALID:
        req = make_request(profile, condition, b, previous, style, invalid)
        waited, estimate = limiter.wait_before()
        path = directory / f'tentativa_{len(attempts)+1:04}.json'
        record = {'request': req, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                  'python': sys.version, 'groq_version': importlib.metadata.version('groq'),
                  'estimated_tokens': estimate, 'timing': {'quota_wait_seconds': waited, 'prior_429_wait_seconds': prior_wait}}
        g.dump(path, record)
        attempts.append(path)
        started = time.monotonic()
        try:
            raw = client.chat.completions.with_raw_response.create(**req)
            headers = g.safe_headers(raw.headers)
            resp = raw.parse().model_dump(mode='json')
        except status_error as e:
            headers = g.safe_headers(e.response.headers)
            record.update(headers=headers, error={'status':e.status_code,'body':e.response.text})
            record['timing']['api_wall_seconds'] = time.monotonic()-started
            delay = None
            if e.status_code == 429:
                retries += 1
                delay = g.retry_delay(headers, e.response.text, retries)
                record['retry_429'] = {'number':retries,'planned_wait_seconds':delay, 'will_retry':delay is not None and retries <= g.MAX_429}
            g.dump(path, record)
            if delay is not None and retries <= g.MAX_429:
                limiter.headers = headers
                limiter.header_time = limiter.clock()
                print(f'{condition} B{b+1}: HTTP 429; aguardando {delay:.1f}s.', flush=True)
                t = time.monotonic(); time.sleep(delay); prior_wait = time.monotonic()-t
                continue
            raise RuntimeError(f'HTTP {e.status_code}. Progresso salvo em {path}; retome após resolver a causa.') from e
        except connection_error as e:
            record['error'] = {'type':type(e).__name__}
            record['timing']['api_wall_seconds'] = time.monotonic()-started
            g.dump(path, record)
            raise RuntimeError('Conexão interrompida; progresso salvo.') from e
        record.update(response=resp, headers=headers)
        record['timing']['api_wall_seconds'] = time.monotonic()-started
        limiter.observe(started, headers, resp.get('usage'), estimate)
        retries = 0
        prior_wait = 0.0
        try:
            obj = g.parse_response(resp, days)
        except ValueError as e:
            invalid += 1
            record['validation'] = {'valid':False,'reason':str(e)}
            g.dump(path, record)
            print(f'{condition} B{b+1}: resposta estruturalmente inválida ({invalid}/{g.MAX_INVALID}).', flush=True)
            continue
        record['validation'] = {'valid':True}
        g.dump(path, record)
        g.dump(directory/'mensagens.json', obj)
        print(f'{condition} B{b+1}: válido=True; tokens={resp.get("usage",{}).get("total_tokens")}; fingerprint={resp.get("system_fingerprint")}', flush=True)
        return obj
    raise RuntimeError(f'{condition} B{b+1}: limite de respostas inválidas; revisar registros.')


def export(profile, reference, branches, out):
    # Código de revisão separado dos rótulos. Não é cegamento de quem gera.
    order = list(CONDITIONS)
    import random
    random.Random(g.seed('revisao_intervencao_contextual')).shuffle(order)
    key = {f'R{i+1}':c for i,c in enumerate(order)}
    review = {'instructions':'Leia o período de referência comum e compare as duas continuações. Avalie reações nas oportunidades e fora delas, coerência, continuidade e eventual piora operacional. Não use scores, contagens linguísticas ou expectativas de detecção.',
              'reference': g.export_profile(profile, reference+branches[order[0]])[:sum(d['count'] for d in profile['days'][:20])],
              'branches': {}, 'opportunities': {str(b+1): [{'day':d,'message_position':p,'situation':s} for d,p,s in items] for b,items in OPPORTUNITIES.items()}}
    n_ref = len(review['reference'])
    stats = []
    for label, condition in key.items():
        rows = g.export_profile(profile, reference+branches[condition])
        # Dados completos permanecem separados por ramificação; não combinar como perfis independentes.
        g.dump(out/condition/'mensagens.json', rows)
        comparison = rows[n_ref:]
        review['branches'][label] = comparison
        texts = [r['text'] for r in rows]
        records = [g.load(p) for p in sorted((out/condition).glob('bloco_*/tentativa_*.json'))]
        stats.append({'condition':condition, 'reference_messages':n_ref,'new_messages':len(comparison),
                      'exact_repeat_occurrences_full_profile':len(texts)-len(set(texts)),
                      'attempts':len(records),'invalid_responses':sum(r.get('validation',{}).get('valid') is False for r in records),
                      'total_tokens_reported':sum((r.get('response',{}).get('usage') or {}).get('total_tokens') or 0 for r in records)})
    g.dump(out/'revisao_sem_rotulos.json', review)
    g.dump(out/'chave_revisao.json', key)
    g.dump(out/'diagnostico_execucao.json', stats)
    return stats


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--origem',type=Path,default=SOURCE)
    parser.add_argument('--saida',type=Path,default=OUT)
    parser.add_argument('--planejar',action='store_true')
    args = parser.parse_args(argv)
    if args.saida.resolve() == args.origem.resolve() or args.origem.resolve() in args.saida.resolve().parents:
        parser.error('Use uma pasta de saída separada da origem.')
    try:
        profile, reference, manifest = prepare(args.origem)
        manifest_path = args.saida/'plano_teste.json'
        if manifest_path.exists() and g.load(manifest_path) != manifest:
            raise RuntimeError('Plano ou código mudou. Preserve a saída e use outra pasta.')
        g.dump(manifest_path, manifest)
        g.dump(args.saida/'referencia_comum.json', reference)
        n = sum(d['count'] for d in profile['days'][20:])
        print(f'Referência reutilizada: {200-n} mensagens. Novas: {n} por condição; 4 respostas válidas previstas.', flush=True)
        if args.planejar:
            print('Plano salvo; nenhuma chamada à API.'); return 0
        from groq import Groq, APIStatusError, APIConnectionError
        client, limiter = Groq(max_retries=0), g.RateLimiter()
        branches = {c:[] for c in CONDITIONS}
        for b in (4,5):
            for c in CONDITIONS:
                previous = branches[c][-1] if branches[c] else reference[-1]
                branches[c].append(generate(client, limiter, profile, c, b, previous, reference[0]['descricao_escrita'], args.saida, APIStatusError, APIConnectionError))
        for s in export(profile,reference,branches,args.saida): print(s)
        print('Saída:',args.saida)
        return 0
    except (ValueError, RuntimeError, OSError, KeyError, StopIteration) as e:
        print(f'Interrompido: {e}', file=sys.stderr); return 1


if __name__ == '__main__':
    raise SystemExit(main())
