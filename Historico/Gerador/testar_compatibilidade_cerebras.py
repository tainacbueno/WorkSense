"""Teste isolado de um bloco real do gerador contextual v1 (sem alterar o piloto Groq)."""
import os
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
import gerar_comunicacional_contextual as g

ENDPOINT = 'https://api.cerebras.ai/v1/chat/completions'
MODEL = 'gpt-oss-120b'


def build_request():
    plan = g.make_plan('piloto')
    profile = next(p for p in plan['profiles'] if p['id'] == 'P05')
    payload = g.make_request(profile, 0, None, 0)
    payload['model'] = MODEL
    return payload, profile['days'][:5], plan['script_sha256']


def safe_headers(headers):
    return {k.lower(): v for k, v in headers.items()
            if 'ratelimit' in k.lower() or k.lower() in ('retry-after', 'x-request-id', 'date', 'request-id')}


def main():
    key = os.environ.get('CEREBRAS_API_KEY', '').strip()
    if not key:
        print('Defina CEREBRAS_API_KEY no terminal antes de executar.')
        return 1
    payload, days, sha = build_request()
    out = Path(__file__).resolve().parent / 'piloto' / 'compatibilidade_cerebras'
    path = out / ('teste_' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '.json')
    record = dict(provider='Cerebras', endpoint=ENDPOINT, purpose='compatibilidade_tecnica_nao_oficial',
                  profile='P05', block=1, generator_sha256=sha, python=sys.version,
                  started_at_utc=datetime.now(timezone.utc).isoformat(), request=payload)
    g.dump(path, record)
    req = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Accept':'application/json'}, method='POST')
    start = time.monotonic()
    print('Cerebras: P05, bloco 1, 32 mensagens planejadas.', flush=True)
    try:
        with urlopen(req, timeout=180) as resp:
            record['status'] = resp.status
            record['headers'] = safe_headers(resp.headers)
            record['response'] = json.loads(resp.read().decode('utf-8'))
        if record['response'].get('model') != MODEL:
            raise ValueError('Modelo retornado diferente do solicitado.')
        normalized = g.parse_response(record['response'], days)
        record['validation'] = {'valid': True, 'message_count': sum(len(d['mensagens']) for d in normalized['dias'])}
    except HTTPError as exc:
        record['status'] = exc.code
        record['headers'] = safe_headers(exc.headers)
        record['error'] = exc.read().decode('utf-8', errors='replace').replace(key, '[REDACTED]')
        print(f'HTTP {exc.code}: {record["error"]}', flush=True)
    except (URLError, TimeoutError, OSError, ValueError) as exc:
        record['validation'] = {'valid': False, 'reason': str(exc).replace(key, '[REDACTED]')}
        print(record['validation']['reason'], flush=True)
    finally:
        record['api_wall_seconds'] = round(time.monotonic()-start, 3)
        g.dump(path, record)
    if record.get('validation', {}).get('valid'):
        r = record['response']
        print(f'Modelo: {r.get("model")}')
        print(f'Mensagens válidas: {record["validation"]["message_count"]}')
        print(f'Tokens: {r.get("usage")}')
        print(f'Fingerprint: {r.get("system_fingerprint")}')
    print(f'Registro: {path}')
    return 0 if record.get('validation', {}).get('valid') else 1


if __name__ == '__main__':
    raise SystemExit(main())
