"""WorkSense — gerador de estilos predefinidos v4 — Cerebras.
Versão candidata ao congelamento; geração oficial bloqueada.
"""
import argparse
import hashlib
import os
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
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
OUT = HERE / 'piloto' / 'estilo_cerebras_v4' / 'privado'
BASE = 'piloto'
N_CALIBRACAO = 40
N_POR_CONDICAO = 10
MASTER_SEED = 20261128
MODEL = 'gpt-oss-120b'
PROVIDER = 'Cerebras'
ENDPOINT = 'https://api.cerebras.ai/v1/chat/completions'
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
    ('P07', 'tecnico', 'estavel'),
    ('P08', 'tecnico', 'alterada'),
    ('P09', 'tecnico', 'estavel'),
    ('P10', 'tecnico', 'alterada'),
]
OPPORTUNITY_POSITIONS = ((1, 2), (3, 3), (5, 2))
SITUATIONS = (
    'Uma sugestão do assistente não resolveu a dúvida ou necessidade.',
    'O assistente pediu uma informação já fornecida.',
    'O assistente respondeu com detalhes além dos necessários.',
    'O assistente interpretou incorretamente parte da solicitação.',
)
COMMON = 'OPORTUNIDADES DE INTERAÇÃO NESTE BLOCO\nAs situações abaixo ocorrem durante conversas sobre demandas compatíveis com a rotina. Elas são oportunidades de interação, não novos problemas operacionais. Na posição indicada, escreva uma mensagem do colaborador que reaja à situação. A mensagem imediatamente anterior do mesmo dia deve dar contexto plausível à conversa. Imagine a resposta intermediária do assistente, mas não a inclua no JSON. Não anuncie o cenário, nem escreva rótulos, explicações externas ou falas do assistente. Não é necessário resolver a demanda nessa interação. As demais mensagens seguem a rotina, com liberdade para outras interações e reações naturais. A reação deve seguir as orientações comportamentais aplicáveis a esta etapa, sem impor tamanho, palavras ou pontuação específicos. Preserve a coerência temporal e não reinicie tarefas concluídas sem motivo.'
INTERVENTIONS = {
    'alterada': (
        'Nesta etapa da rotina, a maneira de interagir do colaborador com o assistente muda em relação ao início do perfil. '
        'Em diferentes dias e situações, ele demonstra menos paciência com respostas que não ajudam, com a necessidade de repetir informações ou com interações que se prolongam. '
        'Quando isso ocorre, pode interromper uma explicação, pedir uma resposta mais direta, contestar uma sugestão ou preferir resolver algo sem continuar a conversa. '
        'Represente essa mudança nas próprias interações, sem narrar ou anunciar que o comportamento mudou. '
        'Ela pode oscilar: preserve também interações habituais e momentos tranquilos, sem transformar toda dificuldade em irritação. '
        'As atividades profissionais continuam no contexto habitual, com dificuldades e avanços cotidianos. '
        'Não introduza uma piora sistemática nas tarefas, nos prazos ou nas entregas para justificar a mudança na comunicação.'
    ),
}
# Limites da conta informados pelo usuário; servidor prevalece.
TPM = 30000
LOCAL_TPM = 28500
RPM = 5
MAX_429 = 3
MAX_WAIT_429 = 120

class APIStatusError(Exception):
    def __init__(self, status, headers, body):
        self.status_code, self.headers, self.body = status, headers, body

class APIConnectionError(Exception):
    pass


def call_api(key, payload):
    req = Request(ENDPOINT, data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
                  headers={'Authorization': 'Bearer ' + key, 'Content-Type': 'application/json', 'Accept': 'application/json'}, method='POST')
    try:
        with urlopen(req, timeout=180) as resp:
            headers = safe_headers(resp.headers)
            data = json.loads(resp.read().decode('utf-8'))
            if not isinstance(data, dict):
                raise ValueError('Resposta não é objeto JSON')
            return headers, data
    except HTTPError as e:
        raise APIStatusError(e.code, safe_headers(e.headers), e.read().decode('utf-8', errors='replace').replace(key, '[REDACTED]')) from None
    except (URLError, TimeoutError, OSError, ValueError) as e:
        raise APIConnectionError(type(e).__name__) from None


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
    return {k.lower(): v for k, v in headers.items()
            if 'ratelimit' in k.lower() or k.lower() in ('retry-after', 'x-request-id', 'date', 'request-id')}


def duration_seconds(value):
    """Interpreta duração numérica em segundos ou com unidades ms/s/m/h/d."""
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
    """Serial; janela local conservadora e cabeçalhos Cerebras por período.
    Tokens totais são usados como aproximação conservadora dos não cacheados;
    reserva do servidor pode superar o consumo final. Não presume cota exclusiva.
    """
    def __init__(self, clock=time.monotonic, sleeper=time.sleep):
        self.clock, self.sleep = clock, sleeper
        self.calls = deque()
        self.recent = deque(maxlen=12)
        self.headers = {}
        self.header_time = 0

    def estimate(self):
        return max(5000, math.ceil(max(self.recent, default=0)*1.25))

    def observe(self, started, headers, usage=None, estimate=None):
        total = (usage or {}).get('total_tokens')
        if isinstance(total, int) and total > 0:
            self.recent.append(total)
        self.calls.append((started, max(estimate or self.estimate(), total or 0)))
        self.headers = headers
        self.header_time = self.clock()

    def wait_before(self):
        start = self.clock()
        estimate = self.estimate()
        limit = header_int(self.headers, 'x-ratelimit-limit-tokens-minute')
        cap = min(LOCAL_TPM, limit) if limit and limit > 0 else LOCAL_TPM
        request_cap = header_int(self.headers, 'x-ratelimit-limit-requests-minute')
        rpm = min(RPM, request_cap) if request_cap and request_cap > 0 else RPM
        if estimate > cap:
            raise RuntimeError('Estimativa de tokens acima da cota por minuto; revisar antes de retomar.')
        for period in ('hour', 'day'):
            reqs = header_int(self.headers, f'x-ratelimit-remaining-requests-{period}')
            tokens = header_int(self.headers, f'x-ratelimit-remaining-tokens-{period}')
            if (reqs is not None and reqs <= 0) or (tokens is not None and tokens < estimate):
                raise RuntimeError(f'Cota horária/diária insuficiente ({period}); retome após renovação.')
        while True:
            now = self.clock()
            while self.calls and now-self.calls[0][0] >= 60:
                self.calls.popleft()
            wait = 0.0
            rem = header_int(self.headers, 'x-ratelimit-remaining-tokens-minute')
            reqs = header_int(self.headers, 'x-ratelimit-remaining-requests-minute')
            if (rem is not None and rem < estimate) or reqs == 0:
                wait = max(wait, 60.5-(now-self.header_time))
            if self.calls and (sum(t for _,t in self.calls)+estimate > cap or len(self.calls)>=rpm):
                wait = max(wait, 60.5-(now-self.calls[0][0]))
            if wait <= 0:
                return self.clock()-start, estimate
            if wait > MAX_WAIT_429:
                raise RuntimeError('Espera de cota longa; retome posteriormente.')
            print(f'Cota: aguardando {wait:.1f}s.', flush=True)
            self.sleep(wait)


def retry_delay(headers, body, retry_number):
    text = str(body).lower()
    if re.search(r'\b(tpd|rpd|tph|rph)\b|(?:tokens|requests) per (?:day|hour)|(?:daily|hourly) (?:token|request|limit|quota)', text):
        return None
    for period in ('day', 'hour'):
        if any(header_int(headers, f'x-ratelimit-remaining-{kind}-{period}') == 0 for kind in ('tokens', 'requests')):
            return None
    delay = duration_seconds(headers.get('retry-after'))
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


def profile_specs(base, assignment_seed=None):
    if base == 'piloto':
        return [(pid, context, condition, None) for pid, context, condition in PROFILES]
    if base == 'calibracao':
        labels = [None] * N_CALIBRACAO
        prefix = 'CAL'
    elif base == 'teste':
        if assignment_seed is None:
            raise ValueError('A atribuição de condições do teste exige uma semente privada.')
        labels = [label for label in 'ABCD' for _ in range(N_POR_CONDICAO)]
        random.Random(assignment_seed).shuffle(labels)
        prefix = 'TST'
    else:
        raise ValueError('Base inválida')
    result = []
    for i, label in enumerate(labels, 1):
        pid = f'{prefix}{i:03}'
        context = random.Random(seed(pid, 'context')).choice(sorted(CONTEXTS))
        condition = 'alterada' if label in ('B', 'D') else 'estavel'
        result.append((pid, context, condition, label))
    return result


def opportunities(pid, block):
    rng = random.Random(seed(pid, 'opportunities', block))
    return [dict(day=d, message_position=p, situation=t) for (d,p),t in
            zip(OPPORTUNITY_POSITIONS, rng.sample(SITUATIONS, 3))]


def review_plan(base, profiles):
    ids = [p['id'] for p in profiles]
    full_seed = seed(base, 'review_full_profiles')
    # Piloto de quatro perfis: todos integrais. Bases oficiais: quatro.
    full = sorted(random.Random(full_seed).sample(ids, min(4, len(ids))))
    entries = {}
    for p in profiles:
        pid = p['id']
        samples = []
        for b in range(6):
            k = 1 if b < 4 else 2
            rng = random.Random(seed(pid, 'review_days', b))
            selected = sorted(rng.sample([d['date'] for d in p['days'][b*5:b*5+5]], k))
            samples.append(dict(block=b+1, seed=seed(pid, 'review_days', b), dates=selected))
        dates = [d['date'] for d in p['days']] if pid in full else [d for b in samples for d in b['dates']]
        entries[pid] = dict(full=pid in full, blocks=samples, dates=dates,
                            message_count=sum(d['count'] for d in p['days'] if d['date'] in dates))
    return dict(full_seed=full_seed, full_profiles=full, profiles=entries,
                message_count=sum(p['message_count'] for p in entries.values()))


# Hábitos comunicacionais, sem metas numéricas, polaridade ou rótulo experimental.
STYLE_OPTIONS = {
    'registro': (
        'Usa português cotidiano e conversacional, com construções espontâneas comuns em conversas de trabalho; admite contrações naturais quando cabem.',
        'Usa registro profissional cotidiano, com linguagem clara de conversa entre colegas e vocabulário técnico quando pertinente.',
        'Usa registro mais formal e cuidadoso, com formulações completas e terminologia precisa, mantendo a interação dirigida ao assistente.',
    ),
    'organizacao': (
        'Geralmente apresenta primeiro o que precisa e acrescenta o contexto pertinente conforme a conversa avança.',
        'Costuma situar o problema ou a atividade em andamento antes de explicitar o que precisa do assistente.',
        'Costuma organizar a solicitação em torno do resultado desejado, das condições relevantes e do que precisa ser esclarecido.',
    ),
    'conducao': (
        'Tende a conduzir a interação por perguntas sucessivas e complementos conforme as respostas, sem repetir informações desnecessariamente.',
        'Tende a expor o raciocínio ou tentativa anterior e conversar sobre alternativas com o assistente.',
        'Tende a delegar ações específicas ao assistente e acompanhar o retorno com confirmações e ajustes de requisitos.',
    ),
    'esclarecimento': (
        'Quando precisa esclarecer algo, costuma indicar o ponto que ficou em dúvida e pedir um ajuste específico.',
        'Quando precisa esclarecer algo, costuma explicar o sentido pretendido e contrastá-lo com a interpretação recebida.',
        'Quando precisa esclarecer algo, costuma reformular a solicitação em termos do resultado ou das condições necessárias.',
    ),
    'marcas_conversacionais': (
        'Usa marcas de interlocução cotidianas e retomadas espontâneas; os cumprimentos e confirmações aparecem quando a situação pede.',
        'Costuma conectar mensagens por referências ao que acabou de acontecer na conversa, sem repetir a contextualização inteira.',
        'Costuma tornar explícito a que solicitação ou resultado se refere, com transições profissionais e fechamento quando pertinente.',
    ),
}
# Piloto cruzado: dois estilos contrastantes, cada qual em ambas as condições.
PILOT_STYLE = {'P07': (0,0,0,0,0), 'P08': (0,0,0,0,0),
               'P09': (2,2,2,2,2), 'P10': (2,2,2,2,2)}
STABILITY = ('Preserve os hábitos comunicacionais individuais descritos nesta referência ao longo dos dias e dos blocos. '
             'Admita reações pontuais e adaptações à demanda, sem introduzir mudanças persistentes não previstas.')
STYLE_GUIDANCE = ('A referência descreve hábitos de escrita, não acontecimentos nem traços psicológicos. '
                  'Mantenha essas características reconhecíveis desde a primeira mensagem. '
                  'Não transforme os hábitos em frases repetidas, quotas ou regras de comprimento, pontuação ou sentimento. '
                  'Quando houver intervenção explícita, ela tem precedência nos aspectos comportamentais que pretende alterar; '
                  'preserve os demais hábitos individuais.')

def individual_style(pid, base):
    if base == 'piloto':
        indices = PILOT_STYLE[pid]
        style_seed = None
    else:
        style_seed = seed(pid, 'individual_style_v4')
        rng = random.Random(style_seed)
        indices = tuple(rng.randrange(len(options)) for options in STYLE_OPTIONS.values())
    return dict(seed=style_seed, indices=list(indices), characteristics={
        name: options[i] for (name, options), i in zip(STYLE_OPTIONS.items(), indices)})

def make_plan(base=None, assignment_seed=None):
    base = BASE if base is None else base
    dates = [date(2026, 5, 4) + timedelta(days=7*b+d) for b in range(6) for d in range(5)]
    profiles = []
    for pid, context, condition, label in profile_specs(base, assignment_seed):
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
                         'individual_style': individual_style(pid, base), 'schedule_seed': seed(pid, 'schedule'), 'context_seed': seed(pid, 'context') if base != 'piloto' else None, 'days': days,
                         'opportunities': [dict(block=b+1, seed=seed(pid, 'opportunities', b), slots=opportunities(pid,b)) for b in range(6)]})
        if label is not None:
            profiles[-1]['experimental_condition'] = label
    return {'purpose': {'piloto': 'piloto_tecnico_estilo_cerebras_v4', 'calibracao': 'calibracao', 'teste': 'teste_independente'}[base], 'version': 'estilo_cerebras_v4_candidato', 'provider': PROVIDER, 'endpoint': ENDPOINT, 'base': base, 'master_seed': MASTER_SEED,
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'parameters': PARAMS, 'rate_policy': {'tpm': TPM, 'local_tpm': LOCAL_TPM, 'rpm': RPM, 'max_429_retries': MAX_429, 'max_retry_wait_seconds': MAX_WAIT_429}, 'timezone': 'America/Sao_Paulo', 'profiles': profiles,
            'private_assignment_seed': assignment_seed if base == 'teste' else None,
            'review_plan': review_plan(base, profiles), 'style_policy': {'source': 'preassigned_before_block_1', 'axes': {k:list(v) for k,v in STYLE_OPTIONS.items()}, 'official_sampling': 'independent_uniform_with_replacement', 'pilot': 'two_styles_crossed_with_conditions', 'seed_namespace': 'individual_style_v4'}}


def make_request(profile, block, previous, invalid_count, initial_style=None):
    # Argumento legado mantido para compatibilidade do auditor; não influencia o prompt.
    days = profile['days'][block*5:(block+1)*5]
    context = CONTEXTS[profile['context']]
    history = '' if previous is None else ('\nESTADO DA ROTINA AO FINAL DO BLOCO ANTERIOR\n' + previous['estado_rotina'] + '\n')
    style = '\n'.join(f'- {name}: {text}' for name,text in profile['individual_style']['characteristics'].items())
    change = INTERVENTIONS.get(profile['condition'], '') if block >= 4 else ''
    behavior = change or STABILITY
    distribution = '\n'.join(f"Dia {i+1} ({d['date']}): {d['count']} mensagens." for i,d in enumerate(days))
    prompt = f'''Simule registros de mensagens enviadas por um mesmo colaborador a um assistente virtual durante cinco dias de sua rotina de trabalho, de {days[0]['date']} a {days[-1]['date']}.

CONTEXTO DE TRABALHO
{context}
Essas atividades podem apresentar avanços, dificuldades, interrupções, mudanças de prioridade e descobertas ao longo dos dias. Outras demandas relacionadas ao contexto de trabalho também podem surgir.
{history}
REFERÊNCIA INDIVIDUAL DE ESCRITA (FIXA DESDE O PRIMEIRO BLOCO)
{style}
{STYLE_GUIDANCE}

DINÂMICA DAS INTERAÇÕES
Gere mensagens que poderiam ser encontradas no histórico real de utilização do assistente por esse colaborador. Quando houver um estado anterior da rotina, use-o como contexto factual, sem transformar suas informações em uma lista de solicitações. Dê continuidade apenas aos assuntos pertinentes e introduza novas demandas compatíveis. Não reinicie atividades já concluídas como se fossem novas; acompanhamentos e tarefas recorrentes são possíveis quando fizerem sentido. Use a referência individual de escrita definida acima desde o primeiro bloco.
Considere que o assistente responde entre as mensagens, embora suas respostas não devam aparecer. O colaborador pode comentar uma resposta, esclarecer uma dúvida anterior, corrigir uma informação, complementar uma solicitação ou retomar um assunto de outro dia. As mensagens são dirigidas ao próprio assistente; não narre a conversa para um terceiro.
As mensagens podem conter perguntas, comentários, explicações, confirmações, relatos e reações espontâneas. Permita variações naturais conforme as situações vivenciadas. Evite transformar cada mensagem em um exemplo isolado de tarefa. Não estabeleça proporções fixas de sentimentos, tipos de frase, formalidade ou extensão.
{behavior}
Respeite a coerência temporal e escreva em português brasileiro. Use apenas informações fictícias.

DISTRIBUIÇÃO DAS MENSAGENS
O campo "dias" é um objeto com as chaves dia_01 a dia_05, correspondentes às posições 1 a 5 do bloco, não ao dia do mês. Dentro de cada dia, preencha os campos obrigatórios msg_01, msg_02 e assim por diante, em ordem cronológica. Cada campo contém uma única mensagem.
{distribution}
Respeite exatamente as quantidades solicitadas. No campo "dias", gere somente as mensagens enviadas pelo colaborador, sem incluir respostas do assistente.

MEMÓRIA PARA A PRÓXIMA ETAPA
Além dos dias, preencha dois campos separados das mensagens:
- "estado_rotina": síntese factual curta da situação ao final destes cinco dias, indicando atividades em andamento, pendências, conclusões recentes e compromissos futuros relevantes. No máximo 120 palavras. Não transcreva mensagens, não simule falas e não invente acontecimentos adicionais. Atualize o estado anterior quando pertinente.
- "descricao_escrita": descrição breve de como o colaborador escreveu neste bloco, em até 40 palavras. Descreva a linguagem de forma geral e qualitativa, sem citar mensagens, definir metas, contar características ou atribuir traços psicológicos. Este campo é apenas um registro descritivo para diagnóstico e não será usado como instrução nos blocos seguintes.

Os dois campos são metadados de continuidade e não fazem parte das mensagens do colaborador.'''
    slots = '\n'.join(f"Dia {o['day']}, mensagem {o['message_position']}: {o['situation']}" for o in profile['opportunities'][block]['slots'])
    marker = '\nDISTRIBUIÇÃO DAS MENSAGENS\n'
    prompt = prompt.replace(marker, '\n' + COMMON + '\n' + slots + '\n' + marker, 1)
    return dict(PARAMS, messages=[{'role': 'user', 'content': prompt}],
                seed=seed(profile['id'], 'estilo_v4', 'block', block, 'invalid', invalid_count),
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
                uid = f'pilot-{pid}' if pid.startswith('P') else pid
                rows.append({'messageId': f'{uid}-{len(rows)+1:04}',
                             'userId': uid, 'userName': f'Colaborador {pid}',
                             'createdAt': dt['date']+'T'+t, 'text': m})
    assert len(rows) == 200
    return rows


def audit_block(directory, profile, b, previous, initial_style):
    days = profile['days'][b*5:b*5+5]
    attempts = sorted(directory.glob('tentativa_*.json'))
    invalid = 0
    accepted = None
    for i, path in enumerate(attempts, 1):
        if path.name != f'tentativa_{i:04}.json':
            raise ValueError(f'Tentativas fora de sequência: {path}')
        if accepted is not None or invalid >= MAX_INVALID:
            raise ValueError(f'Tentativa posterior ao encerramento do bloco: {path}')
        record = load(path)
        if record.get('request') != make_request(profile,b,previous,invalid,initial_style):
            raise ValueError(f'Requisição incompatível com plano/memória: {path}')
        if not isinstance(record.get('python'), str) or record.get('provider') != PROVIDER or record.get('endpoint') != ENDPOINT or not record.get('started_at_utc'):
            raise ValueError(f'Metadados ausentes: {path}')
        if 'response' not in record:
            if 'validation' in record:
                raise ValueError(f'Validação sem resposta: {path}')
            continue
        if 'error' in record:
            raise ValueError(f'Resposta e erro simultâneos: {path}')
        if record['response'].get('model') != MODEL:
            raise ValueError(f'Modelo retornado diferente ou ausente: {path}')
        try:
            obj = parse_response(record['response'], days)
        except ValueError as e:
            if record.get('validation',{}).get('valid') is not False:
                raise ValueError(f'Registro de validação incompatível: {path}') from e
            invalid += 1
        else:
            if record.get('validation',{}).get('valid') is not True:
                raise ValueError(f'Registro de validação incompatível: {path}')
            accepted = obj
    saved = directory / 'mensagens.json'
    if saved.exists() and (accepted is None or load(saved) != accepted):
        raise ValueError(f'Bloco exportado incompatível: {saved}')
    return accepted, invalid, attempts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base', choices=['piloto', 'calibracao', 'teste'], default='piloto')
    parser.add_argument('--perfis', nargs='+', help='Identificadores a gerar; no piloto, todos se omitido.')
    parser.add_argument('--planejar', action='store_true', help='Salva plano sem chamar API.')
    args = parser.parse_args()
    global BASE, OUT
    BASE = args.base
    if BASE == 'teste':
        raise SystemExit('Planejamento e geração do teste bloqueados até o congelamento do método e a atribuição privada das condições.')
    if BASE != 'piloto' and not args.planejar:
        raise SystemExit('Geração oficial bloqueada nesta versão candidata. Aguarde validação e congelamento do protocolo.')
    if BASE != 'piloto':
        OUT = HERE / 'planejamento_estilo_cerebras_v4' / BASE / 'privado'
    plan = make_plan()
    seeds = [seed(p['id'], 'estilo_v4', 'block', b, 'invalid', i) for p in plan['profiles'] for b in range(6) for i in range(MAX_INVALID)]
    if len(seeds) != len(set(seeds)):
        raise SystemExit('Colisão de sementes de conteúdo; revisar antes de gerar.')
    available = {p['id'] for p in plan['profiles']}
    if args.perfis and not set(args.perfis) <= available:
        parser.error('Identificador de perfil inexistente nesta base.')
    selected = set(args.perfis or available)
    plan_path = OUT / 'plano_piloto.json' if BASE == 'piloto' else OUT / 'plano_privado.json'
    if plan_path.exists() and load(plan_path) != plan:
        raise SystemExit('Plano ou script diferente do registrado. Preserve a pasta existente e utilize nova versão do piloto.')
    if not plan_path.exists():
        dump(plan_path, plan)
    for p in plan['profiles']:
        print(p['id'], *( [p['context'], p['condition'], p['individual_style']['indices']] if BASE == 'piloto' else []), 'totais por bloco:', [sum(d['count'] for d in p['days'][i:i+5]) for i in range(0,30,5)])
    if args.planejar:
        print('Plano salvo; nenhuma chamada à API.')
        return 0
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
            directory = OUT / pid / f'bloco_{b+1:02}'
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
        dump(OUT / pid / 'diagnostico_repeticoes.json', {
            'total': len(rows), 'distinct': len(seen),
            'repeated_occurrences': len(rows)-len(seen),
            'blocks': diagnostics})
        output = OUT / pid / 'mensagens.json'
        if output.exists() and load(output) != rows:
            raise ValueError(f'Exportação existente incompatível: {output}')
        if not output.exists():
            dump(output, rows)
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
