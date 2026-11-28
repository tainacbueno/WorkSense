"""Piloto exploratório WorkSense. Não usar estes perfis na calibração/teste.
"""
import argparse
import hashlib
import importlib.metadata
import json
import random
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / 'piloto' / 'perfis_v1'
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
SCHEMA = {
    'type': 'object', 'properties': {'dias': {'type': 'array', 'items': {
        'type': 'object', 'properties': {'dia': {'type': 'integer'},
        'mensagens': {'type': 'array', 'items': {'type': 'string'}}},
        'required': ['dia', 'mensagens'], 'additionalProperties': False}}},
    'required': ['dias'], 'additionalProperties': False,
}

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
    return {'purpose': 'piloto_exploratorio', 'version': 1, 'master_seed': MASTER_SEED,
            'script_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            'parameters': PARAMS, 'timezone': 'America/Sao_Paulo', 'profiles': profiles}


def make_request(profile, block, previous, invalid_count):
    days = profile['days'][block*5:(block+1)*5]
    context = CONTEXTS[profile['context']]
    history = ''
    if previous is not None:
        old_dates = profile['days'][(block-1)*5:block*5]
        history = '\nHISTÓRICO RECENTE\n' + json.dumps([
            {'data': dt['date'], 'mensagens': d['mensagens']}
            for dt, d in zip(old_dates, previous['dias'])], ensure_ascii=False) + '\n'
    change = INTERVENTIONS.get(profile['condition'], '') if block >= 4 else ''
    distribution = '\n'.join(f"Dia {i+1} ({d['date']}): {d['count']} mensagens." for i,d in enumerate(days))
    prompt = f'''Simule registros de mensagens enviadas por um mesmo colaborador a um assistente virtual durante cinco dias de sua rotina de trabalho, de {days[0]['date']} a {days[-1]['date']}.

CONTEXTO DE TRABALHO
{context}
Essas atividades podem apresentar avanços, dificuldades, interrupções, mudanças de prioridade e descobertas ao longo dos dias. Outras demandas relacionadas ao contexto de trabalho também podem surgir.
{history}
DINÂMICA DAS INTERAÇÕES
Gere mensagens que poderiam ser encontradas no histórico real de utilização do assistente por esse colaborador. Quando houver histórico recente, considere-o para manter a continuidade das atividades e as características gerais da comunicação, sem copiar ou reformular superficialmente as mensagens. As atividades podem ser retomadas, concluídas, interrompidas ou permanecer pendentes; não é necessário retomar todos os assuntos.
Considere que o assistente responde entre as mensagens, embora suas respostas não devam aparecer. O colaborador pode comentar uma resposta, esclarecer uma dúvida anterior, corrigir uma informação, complementar uma solicitação ou retomar um assunto de outro dia. As mensagens são dirigidas ao próprio assistente; não narre a conversa para um terceiro.
As mensagens podem conter perguntas, comentários, explicações, confirmações, relatos e reações espontâneas. Permita variações naturais conforme as situações vivenciadas. Evite transformar cada mensagem em um exemplo isolado de tarefa. Não estabeleça proporções fixas de sentimentos, tipos de frase, formalidade ou extensão.
{change}
Respeite a coerência temporal e escreva em português brasileiro. Use apenas informações fictícias.

DISTRIBUIÇÃO DAS MENSAGENS
O campo "dia" representa a posição dentro do bloco, não o dia do mês. Retorne os identificadores 1, 2, 3, 4 e 5, nessa ordem.
{distribution}
Respeite exatamente as quantidades solicitadas. Gere somente as mensagens enviadas pelo colaborador, sem incluir as respostas do assistente.'''
    return dict(PARAMS, messages=[{'role': 'user', 'content': prompt}],
                seed=seed(profile['id'], 'block', block, 'invalid', invalid_count),
                response_format={'type': 'json_schema', 'json_schema': {
                    'name': 'bloco_comunicacional', 'strict': True, 'schema': SCHEMA}})


def parse_response(response, days):
    try:
        choice = response['choices'][0]
        if choice['finish_reason'] != 'stop':
            raise ValueError('finalização incompleta')
        obj = json.loads(choice['message']['content'])
        ds = obj['dias']
        if not isinstance(ds, list) or len(ds) != 5:
            raise ValueError('quantidade de dias inválida')
        for i, (d, expected) in enumerate(zip(ds, days), 1):
            if type(d['dia']) is not int or d['dia'] != i:
                raise ValueError('identificador de dia inválido')
            ms = d['mensagens']
            if not isinstance(ms, list) or len(ms) != expected['count']:
                raise ValueError('quantidade de mensagens inválida')
            if any(not isinstance(m, str) or not m.strip() for m in ms):
                raise ValueError('mensagem vazia ou inválida')
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
    last_call = None
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
            while accepted is None:
                if invalid >= MAX_INVALID:
                    print(f'{pid} bloco {b+1}: limite de respostas estruturalmente inválidas. Revisar registros.')
                    return 1
                request = make_request(profile, b, blocks[-1] if blocks else None, invalid)
                if last_call is not None:
                    time.sleep(max(0, 35 - (time.monotonic()-last_call)))
                last_call = time.monotonic()
                path = directory / f'tentativa_{len(attempts)+1:04}.json'
                record = {'request': request, 'started_at_utc': datetime.now(timezone.utc).isoformat(),
                          'python': sys.version, 'groq_version': importlib.metadata.version('groq')}
                # Persistir a requisição antes de enviar; nunca registrar cabeçalhos de autenticação.
                dump(path, record)
                attempts.append(path)
                try:
                    resp = client.chat.completions.create(**request)
                except APIStatusError as e:
                    record['error'] = {'status': e.status_code, 'body': e.response.text,
                                       'retry_after': e.response.headers.get('retry-after')}
                    dump(path, record)
                    print(f'{pid} bloco {b+1}: HTTP {e.status_code}. Registro: {path}. Retome após resolver o erro/cota.')
                    return 1
                except APIConnectionError as e:
                    record['error'] = {'type': type(e).__name__}
                    dump(path, record)
                    print(f'{pid} bloco {b+1}: conexão interrompida. Retome posteriormente.')
                    return 1
                record['response'] = resp.model_dump(mode='json')
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
        dump(OUT / pid / 'mensagens.json', rows)
        print(f'{pid}: {len(rows)} mensagens exportadas.', flush=True)
    print('Saída:', OUT)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
