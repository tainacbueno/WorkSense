"""Piloto exploratório WorkSense. Não usar estes perfis na calibração/teste.
Executar com python -B Gerador/gerar_piloto_comunicacional_v3.py.
"""
import argparse
import hashlib
import importlib.metadata
import json
import random
import re
import math
from collections import deque
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'piloto' / 'perfis_v3'
MASTER_SEED = 20261128
MODEL = 'openai/gpt-oss-120b'
MAX_INVALID = 3
PARAMS = dict(model=MODEL, temperature=0.8, reasoning_effort='low',
              max_completion_tokens=3000)
CONTEXTS = {
    'tecnico': 'O colaborador participa da manutenção e evolução de um sistema interno de atendimento. Suas atividades envolvem investigar chamados, esclarecer dúvidas técnicas, corrigir inconsistências nos relatórios, testar alterações e preparar atualizações do sistema.',
    'administrativo': 'O colaborador acompanha pedidos de compra e documentos de fornecedores. Suas atividades envolvem conferir informações, organizar solicitações internas, acompanhar pendências e preparar relatórios de acompanhamento.',
    'atendimento': 'O colaborador acompanha solicitações de clientes sobre um serviço digital. Suas atividades envolvem esclarecer dúvidas, verificar informações de atendimento, encaminhar ocorrências a outras equipes e acompanhar casos ainda em aberto.',
}
# Condições provisórias para avaliar o gerador, não rótulos A/B/C/D.
PROFILES = [
    ('P01', 'tecnico', 'estavel'),
    ('P02', 'administrativo', 'estavel'),
    ('P03', 'tecnico', 'alteracao_moderada'),
    ('P04', 'administrativo', 'alteracao_acentuada'),
]
INTERVENTIONS = {
    'alteracao_moderada': ('Nesta etapa da rotina, o colaborador passa a demonstrar uma mudança perceptível na maneira de interagir com o assistente. Demonstra menos paciência com sugestões que não funcionam e, em algumas interações, tem menos disposição para desenvolver explicações ou continuar uma conversa. A mudança aparece de forma intermitente, sem eliminar interações habituais nem impedir que as atividades avancem. Não invente uma alteração sistemática na quantidade de tarefas, prazos ou entregas.'),
    'alteracao_acentuada': ('Nesta etapa da rotina, o colaborador passa a demonstrar uma mudança mais pronunciada na maneira de interagir com o assistente. A impaciência diante de sugestões que não funcionam e a menor disposição para desenvolver explicações ou continuar uma conversa aparecem de modo mais recorrente em diferentes situações e dias. Ainda há interações habituais, momentos tranquilos e atividades que avançam normalmente. Não invente uma alteração sistemática na quantidade de tarefas, prazos ou entregas.'),
}
# Limites informados na conta gratuita; o servidor continua sendo a autoridade.
TPM = 8000
LOCAL_TPM = 7600  # margem de segurança, consumo estimado
RPM = 30
MAX_429 = 3
MAX_WAIT_429 = 120  # pausas maiores exigem retomada manual
HEADER_NAMES = ('retry-after', 'x-ratelimit-limit-requests',
                'x-ratelimit-remaining-requests', 'x-ratelimit-reset-requests',
                'x-ratelimit-limit-tokens', 'x-ratelimit-remaining-tokens',
                'x-ratelimit-reset-tokens', 'x-request-id')


def closed_object(properties):
    return {'type': 'object', 'properties': properties,
            'required': list(properties), 'additionalProperties': False}


def make_schema(days):
    # Objetos fechados com campos obrigatórios, sem depender de minItems/maxItems.
    return closed_object({
        'dias': closed_object({
            f'dia_{i:02}': closed_object({
                f'msg_{j:02}': {'type': 'string'}
                for j in range(1, d['count']+1)
            }) for i, d in enumerate(days, 1)
        }),
        'estado_rotina': {'type': 'string'},
        'descricao_escrita': {'type': 'string'},
    })


def safe_headers(headers):
    return {k: headers.get(k) for k in HEADER_NAMES if headers.get(k) is not None}


def duration_seconds(value):
    """Groq retorna, por exemplo, 7.66s ou 2m59.56s; retry-after em segundos."""
    if value is None:
        return None
    value = str(value).strip().lower()
    try:
        n = float(value)
        return n if math.isfinite(n) and n >= 0 else None
    except ValueError:
        pass
    parts = re.findall(r'(\d+(?:\.\d+)?)(ms|s|m|h|d)', value)
    if not parts or ''.join(n+u for n,u in parts) != value:
        return None
    return sum(float(n)*{'ms':.001,'s':1,'m':60,'h':3600,'d':86400}[u]
               for n,u in parts)


def header_int(headers, key):
    try:
        return int(headers[key])
    except (KeyError, TypeError, ValueError):
        return None


class RateLimiter:
    """Serial, com estimativa local móvel e cabeçalhos TPM/RPD da Groq.
    Não supõe conhecer o consumo de outras aplicações nem o limite diário restante.
    """
    def __init__(self, clock=time.monotonic, sleeper=time.sleep):
        self.clock, self.sleep = clock, sleeper
        self.calls = deque()
        self.recent = deque(maxlen=12)
        self.headers = {}
        self.header_time = 0

    def estimate(self):
        # Estimativa empírica inicial, não reserva garantida pelo provedor.
        return max(3200, math.ceil(max(self.recent, default=0)*1.25))

    def observe(self, started, headers, usage=None, estimate=None):
        total = (usage or {}).get('total_tokens')
        if isinstance(total, int) and total > 0:
            self.recent.append(total)
        else:
            total = estimate or self.estimate()
        self.calls.append((started, total))
        self.headers = headers
        self.header_time = self.clock()

    def wait_before(self):
        start = self.clock()
        estimate = self.estimate()
        limit = header_int(self.headers, 'x-ratelimit-limit-tokens')
        cap = min(LOCAL_TPM, limit) if limit and limit > 0 else LOCAL_TPM
        if estimate > cap:
            # Não há garantia de que uma chamada caiba: parar, sem loop infinito.
            raise RuntimeError('Estimativa de tokens acima da cota por minuto; revisar antes de retomar.')
        while True:
            now = self.clock()
            while self.calls and now-self.calls[0][0] >= 60:
                self.calls.popleft()
            daily = header_int(self.headers, 'x-ratelimit-remaining-requests')
            if daily is not None and daily <= 0:
                reset = duration_seconds(self.headers.get('x-ratelimit-reset-requests'))
                if reset is None or now-self.header_time < reset:
                    raise RuntimeError('Cota diária de requisições esgotada; retome após a renovação.')
            wait = 0.0
            remaining = header_int(self.headers, 'x-ratelimit-remaining-tokens')
            reset = duration_seconds(self.headers.get('x-ratelimit-reset-tokens'))
            if remaining is not None and remaining < estimate:
                wait = max(wait, (reset if reset is not None else 60)+0.5-(now-self.header_time))
            if self.calls and (sum(t for _,t in self.calls)+estimate > cap or len(self.calls)>=RPM):
                wait = max(wait, 60.1-(now-self.calls[0][0]))
            if wait <= 0:
                return self.clock()-start, estimate
            if wait > MAX_WAIT_429:
                raise RuntimeError('Espera de cota longa; retome posteriormente.')
            print(f'Cota: aguardando {wait:.1f}s.', flush=True)
            self.sleep(wait)


def retry_delay(headers, body, retry_number):
    """None significa parar; não tentar indefinidamente contra a cota diária."""
    text = str(body).lower()
    if re.search(r'\b(tpd|rpd)\b|tokens per day|requests per day|daily (token|request|limit|quota)', text):
        return None
    if header_int(headers, 'x-ratelimit-remaining-requests') == 0:
        return None
    delay = duration_seconds(headers.get('retry-after'))
    if delay is None:
        delay = duration_seconds(headers.get('x-ratelimit-reset-tokens'))
    if delay is None:
        delay = min(60, 15*2**(retry_number-1))
    delay += 1
    return delay if delay <= MAX_WAIT_429 else None


def seed(*parts):
    raw = '|'.join(map(str, (MASTER_SEED, *parts))).encode()
    return int.from_bytes(hashlib.sha256(raw).digest()[:4], 'big') % (2**31 - 1)


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + '.tmp')
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    tmp.replace(path)


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def make_plan():
    dates = [date(2026, 5, 4) + timedelta(days=7*b+d) for b in range(6) for d in range(5)]
    profiles = []
    for pid, context, condition in PROFILES:
        rng = random.Random(seed(pid, 'schedule'))
        while True:
            counts = [rng.randint(4, 10) for _ in dates]
            if sum(counts) == 200:
                break
        days = []
        for dt, n in zip(dates, counts):
            minutes = sorted(rng.sample(range(8*60, 18*60), n))
            days.append({'date': dt.isoformat(), 'count': n,
                         'times': [f'{m//60:02d}:{m%60:02d}:00' for m in minutes]})
        profiles.append({'id': pid, 'context': context, 'condition': condition,
                         'schedule_seed': seed(pid, 'schedule'), 'days': days})
    return {'purpose': 'piloto_exploratorio', 'version': 3, 'master_seed': MASTER_SEED,
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'parameters': PARAMS, 'rate_policy': {'tpm': TPM, 'local_tpm': LOCAL_TPM, 'rpm': RPM, 'max_429_retries': MAX_429, 'max_retry_wait_seconds': MAX_WAIT_429}, 'timezone': 'America/Sao_Paulo', 'profiles': profiles}


def make_request(profile, block, previous, invalid_count, initial_style=None):
    days = profile['days'][block*5:(block+1)*5]
    context = CONTEXTS[profile['context']]
    history = ''
    if previous is not None:
        history = (
            '\nESTADO DA ROTINA AO FINAL DO BLOCO ANTERIOR\n'
            + previous['estado_rotina']
            + '\n\nDESCRIÇÃO GERAL DA ESCRITA NO INÍCIO DO PERFIL\n'
            + initial_style
            + '\n'
        )
    change = INTERVENTIONS.get(profile['condition'], '') if block >= 4 else ''
    distribution = '\n'.join(f"Dia {i+1} ({d['date']}): {d['count']} mensagens." for i,d in enumerate(days))
    prompt = f'''Simule registros de mensagens enviadas por um mesmo colaborador a um assistente virtual durante cinco dias de sua rotina de trabalho, de {days[0]['date']} a {days[-1]['date']}.

CONTEXTO DE TRABALHO
{context}
Essas atividades podem apresentar avanços, dificuldades, interrupções, mudanças de prioridade e descobertas ao longo dos dias. Outras demandas relacionadas ao contexto de trabalho também podem surgir.
{history}
DINÂMICA DAS INTERAÇÕES
Gere mensagens que poderiam ser encontradas no histórico real de utilização do assistente por esse colaborador. Quando houver um estado anterior da rotina, use-o como contexto factual, sem transformar suas informações em uma lista de solicitações. Dê continuidade apenas aos assuntos pertinentes e introduza novas demandas compatíveis. Não reinicie atividades já concluídas como se fossem novas; acompanhamentos e tarefas recorrentes são possíveis quando fizerem sentido. Quando houver uma descrição inicial da escrita, use-a como referência flexível, permitindo variações naturais; eventuais instruções explícitas de mudança nesta etapa têm precedência.
Considere que o assistente responde entre as mensagens, embora suas respostas não devam aparecer. O colaborador pode comentar uma resposta, esclarecer uma dúvida anterior, corrigir uma informação, complementar uma solicitação ou retomar um assunto de outro dia. As mensagens são dirigidas ao próprio assistente; não narre a conversa para um terceiro.
As mensagens podem conter perguntas, comentários, explicações, confirmações, relatos e reações espontâneas. Permita variações naturais conforme as situações vivenciadas. Evite transformar cada mensagem em um exemplo isolado de tarefa. Não estabeleça proporções fixas de sentimentos, tipos de frase, formalidade ou extensão.
{change}
Respeite a coerência temporal e escreva em português brasileiro. Use apenas informações fictícias.

DISTRIBUIÇÃO DAS MENSAGENS
O campo "dias" é um objeto com as chaves dia_01 a dia_05, correspondentes às posições 1 a 5 do bloco, não ao dia do mês. Dentro de cada dia, preencha os campos obrigatórios msg_01, msg_02 e assim por diante, em ordem cronológica. Cada campo contém uma única mensagem.
{distribution}
Respeite exatamente as quantidades solicitadas. No campo "dias", gere somente as mensagens enviadas pelo colaborador, sem incluir respostas do assistente.

MEMÓRIA PARA A PRÓXIMA ETAPA
Além dos dias, preencha dois campos separados das mensagens:
- "estado_rotina": síntese factual curta da situação ao final destes cinco dias, indicando atividades em andamento, pendências, conclusões recentes e compromissos futuros relevantes. No máximo 120 palavras. Não transcreva mensagens, não simule falas e não invente acontecimentos adicionais. Atualize o estado anterior quando pertinente.
- "descricao_escrita": descrição breve de como o colaborador escreveu neste bloco, em até 40 palavras. Descreva a linguagem de forma geral e qualitativa, sem citar mensagens, definir metas, contar características ou atribuir traços psicológicos. Este campo não é uma instrução para alterar a escrita.

Os dois campos são metadados de continuidade e não fazem parte das mensagens do colaborador.'''
    return dict(PARAMS, messages=[{'role': 'user', 'content': prompt}],
                seed=seed(profile['id'], 'block', block, 'invalid', invalid_count),
                response_format={'type': 'json_schema', 'json_schema': {
                    'name': 'bloco_comunicacional', 'strict': True, 'schema': make_schema(days)}})


def parse_response(response, days):
    try:
        choice = response['choices'][0]
        if choice['finish_reason'] != 'stop':
            raise ValueError('finalização incompleta')
        obj = json.loads(choice['message']['content'])
        if set(obj) != {'dias', 'estado_rotina', 'descricao_escrita'}:
            raise ValueError('campos do bloco inválidos')
        ds = obj['dias']
        keys = [f'dia_{i:02}' for i in range(1, 6)]
        if not isinstance(ds, dict) or set(ds) != set(keys):
            raise ValueError('identificadores de dia inválidos')
        normalized = []
        for i, (key, expected) in enumerate(zip(keys, days), 1):
            messages = ds[key]
            msg_keys = [f'msg_{j:02}' for j in range(1, expected['count']+1)]
            if not isinstance(messages, dict) or set(messages) != set(msg_keys):
                raise ValueError(f'quantidade ou identificadores de mensagens inválidos no dia {i}')
            ms = [messages[k] for k in msg_keys]
            if any(not isinstance(m, str) or not m.strip() for m in ms):
                raise ValueError('mensagem vazia ou inválida')
            normalized.append({'dia': i, 'mensagens': ms})
        obj['dias'] = normalized
        for key in ('estado_rotina', 'descricao_escrita'):
            if not isinstance(obj[key], str) or not obj[key].strip():
                raise ValueError(f'metadado de continuidade inválido: {key}')
        return obj
    except (ValueError, KeyError, IndexError, TypeError, AttributeError) as e:
        raise ValueError(str(e)) from e


def export_profile(profile, blocks):
    rows = []
    for b, obj in enumerate(blocks):
        for d, dt in zip(obj['dias'], profile['days'][b*5:b*5+5]):
            for m, t in zip(d['mensagens'], dt['times']):
                pid = profile['id']
                rows.append({'messageId': f'pilot-{pid}-{len(rows)+1:04}',
                             'userId': f'pilot-{pid}', 'userName': f'Piloto {pid}',
                             'createdAt': dt['date']+'T'+t, 'text': m})
    assert len(rows) == 200
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--perfis', nargs='+', choices=[p[0] for p in PROFILES], default=[p[0] for p in PROFILES])
    parser.add_argument('--planejar', action='store_true', help='Salva plano sem chamar API.')
    args = parser.parse_args()
    plan = make_plan()
    plan_path = OUT / 'plano_piloto.json'
    if plan_path.exists() and load(plan_path) != plan:
        raise SystemExit('Plano ou script diferente do registrado. Preserve a pasta existente e utilize nova versão do piloto.')
    dump(plan_path, plan)
    for p in plan['profiles']:
        print(p['id'], p['context'], p['condition'], 'totais por bloco:', [sum(d['count'] for d in p['days'][i:i+5]) for i in range(0,30,5)])
    if args.planejar:
        print('Plano salvo; nenhuma chamada à API.')
        return 0
    from groq import Groq, APIStatusError, APIConnectionError
    client = Groq(max_retries=0)
    limiter = RateLimiter()
    for profile in plan['profiles']:
        pid = profile['id']
        if pid not in args.perfis:
            continue
        blocks = []
        for b in range(6):
            directory = OUT / pid / f'bloco_{b+1:02}'
            directory.mkdir(parents=True, exist_ok=True)
            days = profile['days'][b*5:b*5+5]
            attempts = sorted(directory.glob('tentativa_*.json'))
            invalid = 0
            accepted = None
            for f in attempts:
                a = load(f)
                if 'response' not in a:
                    continue
                try:
                    accepted = parse_response(a['response'], days)
                    break
                except ValueError:
                    invalid += 1
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
                          'python': sys.version, 'groq_version': importlib.metadata.version('groq'),
                          'timing': {'quota_wait_seconds': round(quota_wait, 3),
                                     'prior_429_wait_seconds': round(pending_wait, 3)},
                          'estimated_tokens': estimate}
                pending_wait = 0.0
                dump(path, record)
                attempts.append(path)
                started = time.monotonic()
                try:
                    raw = client.chat.completions.with_raw_response.create(**request)
                    headers = safe_headers(raw.headers)
                    resp = raw.parse()
                except APIStatusError as e:
                    headers = safe_headers(e.response.headers)
                    record['headers'] = headers
                    record['timing']['api_wall_seconds'] = round(time.monotonic()-started, 3)
                    record['error'] = {'status': e.status_code, 'body': e.response.text}
                    if e.status_code == 429:
                        retries_429 += 1
                        delay = retry_delay(headers, e.response.text, retries_429)
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
                record['response'] = resp.model_dump(mode='json')
                limiter.observe(started, headers, record['response'].get('usage'), estimate)
                retries_429 = 0
                try:
                    accepted = parse_response(record['response'], days)
                    record['validation'] = {'valid': True}
                except ValueError as e:
                    record['validation'] = {'valid': False, 'reason': str(e)}
                    invalid += 1
                dump(path, record)
                usage = record['response'].get('usage') or {}
                print(f'{pid} bloco {b+1}: válido={accepted is not None}; tokens={usage.get("total_tokens")}; fingerprint={record["response"].get("system_fingerprint")}', flush=True)
            blocks.append(accepted)
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
        dump(OUT / pid / 'diagnostico_repeticoes.json', {
            'total': len(rows), 'distinct': len(seen),
            'repeated_occurrences': len(rows)-len(seen),
            'blocks': diagnostics})
        dump(OUT / pid / 'mensagens.json', rows)
        print(f'{pid}: {len(rows)-len(seen)} ocorrências repetidas (diagnóstico, sem descarte).')
        print(f'{pid}: {len(rows)} mensagens exportadas.', flush=True)
    # Resumo de todas as tentativas persistidas, inclusive as anteriores à retomada.
    stats = []
    for profile in plan['profiles']:
        records = [load(p) for p in sorted((OUT / profile['id']).glob('bloco_*/tentativa_*.json'))]
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
    dump(OUT / 'diagnostico_execucao.json', stats)
    print('Saída:', OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
