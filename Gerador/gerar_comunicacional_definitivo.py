"""Liberação oficial controlada. Reutiliza plano, prompts e funções V4 intactos.
Loop de geração extraído da main V4, com parâmetro de saída em vez de global OUT.
"""
from gerar_comunicacional_estilo_v4 import *
from controle_comunicacional import authorize, require


def run_generation(plan, output, selected):
    key = os.environ.get('CEREBRAS_API_KEY', '').strip()
    if not key:
        print('Defina CEREBRAS_API_KEY no terminal.')
        return 1
    limiter = RateLimiter()
    for profile in plan['profiles']:
        pid = profile['id']
        if pid not in selected:
            continue
        blocks = []
        for b in range(6):
            directory = output / pid / f'bloco_{b+1:02}'
            directory.mkdir(parents=True, exist_ok=True)
            days = profile['days'][b*5:b*5+5]
            accepted, invalid, attempts = audit_block(directory, profile, b,
                blocks[-1] if blocks else None, blocks[0]['descricao_escrita'] if blocks else None)
            retries_429 = 0
            pending_wait = 0.0
            while accepted is None:
                if invalid >= MAX_INVALID:
                    print(f'{pid} bloco {b+1}: limite de respostas estruturalmente inválidas. Revisar registros.')
                    return 1
                request = make_request(
                    profile, b, blocks[-1] if blocks else None, invalid,
                    initial_style=blocks[0]['descricao_escrita'] if blocks else None
                )
                try:
                    quota_wait, estimate = limiter.wait_before()
                except RuntimeError as e:
                    print(str(e), flush=True)
                    return 1
                path = directory / f'tentativa_{len(attempts)+1:04}.json'
                record = {'request': request, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                          'python': sys.version, 'provider': PROVIDER, 'endpoint': ENDPOINT, 'transport': 'urllib.request',
                          'timing': {'quota_wait_seconds': round(quota_wait, 3),
                                     'prior_429_wait_seconds': round(pending_wait, 3)},
                          'estimated_tokens': estimate}
                pending_wait = 0.0
                dump(path, record)
                attempts.append(path)
                started = time.monotonic()
                try:
                    headers, resp = call_api(key, request)
                except APIStatusError as e:
                    headers = e.headers
                    record['headers'] = headers
                    record['timing']['api_wall_seconds'] = round(time.monotonic()-started, 3)
                    record['error'] = {'status': e.status_code, 'body': e.body}
                    if e.status_code == 429:
                        retries_429 += 1
                        delay = retry_delay(headers, e.body, retries_429)
                        record['retry_429'] = {'number': retries_429, 'planned_wait_seconds': delay,
                                               'will_retry': delay is not None and retries_429 <= MAX_429}
                        dump(path, record)
                        if delay is not None and retries_429 <= MAX_429:
                            print(f'{pid} bloco {b+1}: HTTP 429; aguardando {delay:.1f}s e repetindo a mesma semente.', flush=True)
                            # A resposta rejeitada não é uma geração inválida.
                            # Atualizar os cabeçalhos, sem contabilizar tokens fictícios.
                            limiter.headers = headers
                            limiter.header_time = limiter.clock()
                            t = time.monotonic()
                            time.sleep(delay)
                            pending_wait = time.monotonic()-t
                            continue
                    dump(path, record)
                    print(f'{pid} bloco {b+1}: HTTP {e.status_code}. Registro: {path}. Retome após resolver o erro/cota.', flush=True)
                    return 1
                except APIConnectionError as e:
                    record['timing']['api_wall_seconds'] = round(time.monotonic()-started, 3)
                    record['error'] = {'type': type(e).__name__}
                    dump(path, record)
                    print(f'{pid} bloco {b+1}: conexão interrompida. Retome posteriormente.', flush=True)
                    return 1
                record['headers'] = headers
                record['timing']['api_wall_seconds'] = round(time.monotonic()-started, 3)
                record['response'] = resp
                limiter.observe(started, headers, record['response'].get('usage'), estimate)
                retries_429 = 0
                try:
                    accepted = parse_response(record['response'], days)
                    record['validation'] = {'valid': True}
                except ValueError as e:
                    record['validation'] = {'valid': False, 'reason': str(e)}
                    invalid += 1
                dump(path, record)
                if record['response'].get('model') != MODEL:
                    print(f'{pid} bloco {b+1}: modelo retornado diferente ou ausente; geração suspensa.')
                    return 1
                usage = record['response'].get('usage') or {}
                print(f'{pid} bloco {b+1}: válido={accepted is not None}; tokens={usage.get("total_tokens")}; fingerprint={record["response"].get("system_fingerprint")}', flush=True)
            blocks.append(accepted)
            if not (directory / 'mensagens.json').exists():
                dump(directory / 'mensagens.json', accepted)
        rows = export_profile(profile, blocks)
        seen = set()
        diagnostics = []
        for i, obj in enumerate(blocks, 1):
            texts = [m for d in obj['dias'] for m in d['mensagens']]
            repeated = sum(t in seen for t in texts)
            diagnostics.append({'block': i, 'count': len(texts),
                                'repeated_from_previous_blocks': repeated,
                                'duplicates_within_block': len(texts)-len(set(texts))})
            seen.update(texts)
        dump(output / pid / 'diagnostico_repeticoes.json', {
            'total': len(rows), 'distinct': len(seen),
            'repeated_occurrences': len(rows)-len(seen),
            'blocks': diagnostics})
        profile_output = output / pid / 'mensagens.json'
        if profile_output.exists() and load(profile_output) != rows:
            raise ValueError(f'Exportação existente incompatível: {profile_output}')
        if not profile_output.exists():
            dump(profile_output, rows)
        print(f'{pid}: {len(rows)-len(seen)} ocorrências repetidas (diagnóstico, sem descarte).')
        print(f'{pid}: {len(rows)} mensagens exportadas.', flush=True)
    # Resumo de todas as tentativas persistidas, inclusive as anteriores à retomada.
    stats = []
    for profile in plan['profiles']:
        records = [load(p) for p in sorted((output / profile['id']).glob('bloco_*/tentativa_*.json'))]
        if not records:
            continue
        stats.append({'profile': profile['id'], 'attempts': len(records),
                      'responses': sum('response' in r for r in records),
                      'invalid_responses': sum(r.get('validation', {}).get('valid') is False for r in records),
                      'http_429': sum(r.get('error', {}).get('status') == 429 for r in records),
                      'total_tokens_reported': sum((r.get('response', {}).get('usage') or {}).get('total_tokens') or 0 for r in records),
                      'api_wall_seconds': round(sum(r.get('timing', {}).get('api_wall_seconds', 0) for r in records), 3),
                      'quota_wait_seconds': round(sum(r.get('timing', {}).get('quota_wait_seconds', 0) for r in records), 3),
                      'prior_429_wait_seconds': round(sum(r.get('timing', {}).get('prior_429_wait_seconds', 0) for r in records), 3)})
    dump(output / 'diagnostico_execucao.json', stats)
    print('Saída:', output)
    return 0



def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--base',choices=['calibracao','teste'],required=True)
    p.add_argument('--congelamento',type=Path,required=True)
    p.add_argument('--saida',type=Path,required=True,help='Pasta privada, acesso exclusivo do responsável')
    p.add_argument('--seed-atribuicao',type=int)
    p.add_argument('--planejar',action='store_true');p.add_argument('--perfis',nargs='+')
    a=p.parse_args();authorize(a.base,a.congelamento)
    require((a.seed_atribuicao is None)==(a.base=='calibracao'),'Semente privada obrigatória somente no teste')
    plan=make_plan(a.base,a.seed_atribuicao)
    seeds=[seed(x['id'],'estilo_v4','block',b,'invalid',i) for x in plan['profiles'] for b in range(6) for i in range(MAX_INVALID)]
    require(len(seeds)==len(set(seeds)),'Colisão de sementes')
    selected=set(a.perfis or [x['id'] for x in plan['profiles']]);require(selected<={x['id'] for x in plan['profiles']},'IDs desconhecidos')
    output=a.saida.resolve(); path=output/'plano_privado.json'
    if path.exists():require(load(path)==plan,'Plano diferente do registrado; não sobrescrever')
    else:
        require(not output.exists() or not any(output.iterdir()),'Pasta privada não vazia, sem plano')
        dump(path,plan)
    if a.planejar:print('Plano privado registrado; nenhuma API.');return 0
    return run_generation(plan,output,selected)
if __name__=='__main__':raise SystemExit(main())
